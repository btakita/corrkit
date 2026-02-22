//! Push a draft markdown file as an email draft, or send it directly.

use anyhow::{bail, Result};
use lettre::message::Mailbox;
use lettre::transport::smtp::authentication::Credentials;
use lettre::{Message, SmtpTransport, Transport};
use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::HashMap;
use std::path::Path;

use crate::accounts::{
    get_account_for_email, get_default_account, load_accounts_or_env, resolve_password,
};

static META_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"(?m)^\*\*(.+?)\*\*:\s*(.+)$").unwrap());

const VALID_SEND_STATUSES: &[&str] = &["review", "approved"];

/// Parse a draft markdown file. Returns (meta, subject, body).
pub fn parse_draft(path: &Path) -> Result<(HashMap<String, String>, String, String)> {
    let text = std::fs::read_to_string(path)?;
    let lines: Vec<&str> = text.split('\n').collect();

    let subject = lines
        .iter()
        .find_map(|line| {
            line.strip_prefix("# ")
                .map(|s| s.trim().to_string())
        })
        .unwrap_or_default();

    let mut meta = HashMap::new();
    for cap in META_RE.captures_iter(&text) {
        meta.insert(cap[1].to_string(), cap[2].trim().to_string());
    }

    if !meta.contains_key("To") {
        bail!("Draft is missing **To**: field: {}", path.display());
    }

    // Body is everything after the first ---
    let body_start = lines.iter().position(|line| line.trim() == "---");
    let Some(body_start) = body_start else {
        bail!("Draft is missing --- separator: {}", path.display());
    };

    let body = lines[body_start + 1..].join("\n").trim().to_string();
    Ok((meta, subject, body))
}

/// Compose an email from draft metadata.
fn compose_email(
    meta: &HashMap<String, String>,
    subject: &str,
    body: &str,
    from_addr: &str,
) -> Result<Message> {
    let from: Mailbox = from_addr.parse().map_err(|_| anyhow::anyhow!("Invalid from address: {}", from_addr))?;
    let to: Mailbox = meta["To"]
        .parse()
        .map_err(|_| anyhow::anyhow!("Invalid To address: {}", meta["To"]))?;

    let mut builder = Message::builder()
        .from(from)
        .to(to)
        .subject(subject);

    if let Some(cc) = meta.get("CC") {
        if !cc.is_empty() {
            let cc_box: Mailbox = cc.parse().map_err(|_| anyhow::anyhow!("Invalid CC address: {}", cc))?;
            builder = builder.cc(cc_box);
        }
    }

    if let Some(in_reply_to) = meta.get("In-Reply-To") {
        if !in_reply_to.is_empty() {
            builder = builder.in_reply_to(in_reply_to.to_string());
            builder = builder.references(in_reply_to.to_string());
        }
    }

    let email = builder.body(body.to_string())?;
    Ok(email)
}

/// Push draft to IMAP drafts folder.
fn push_to_drafts(
    email: &Message,
    imap_host: &str,
    imap_port: u16,
    starttls: bool,
    user: &str,
    password: &str,
    drafts_folder: &str,
) -> Result<()> {
    let mut tls_builder = native_tls::TlsConnector::builder();
    if starttls || imap_host == "127.0.0.1" || imap_host == "localhost" {
        tls_builder.danger_accept_invalid_certs(true);
        tls_builder.danger_accept_invalid_hostnames(true);
    }
    let tls = tls_builder.build()?;

    let client = if starttls {
        imap::connect_starttls((imap_host, imap_port), imap_host, &tls)?
    } else {
        imap::connect((imap_host, imap_port), imap_host, &tls)?
    };

    let mut session = client.login(user, password).map_err(|e| e.0)?;

    let email_bytes = email.formatted();
    session.append(drafts_folder, &email_bytes)?;
    session.logout()?;
    Ok(())
}

/// Send email via SMTP.
fn send_email(
    email: &Message,
    smtp_host: &str,
    smtp_port: u16,
    user: &str,
    password: &str,
) -> Result<()> {
    let creds = Credentials::new(user.to_string(), password.to_string());
    let mailer = SmtpTransport::relay(smtp_host)?
        .port(smtp_port)
        .credentials(creds)
        .build();
    mailer.send(email)?;
    Ok(())
}

/// Update the **Status** field in a draft file.
fn update_draft_status(path: &Path, new_status: &str) -> Result<()> {
    let text = std::fs::read_to_string(path)?;
    let re = Regex::new(r"(?m)^(\*\*Status\*\*:\s*).+$")?;
    let updated = re
        .replace(&text, format!("${{1}}{}", new_status))
        .to_string();
    std::fs::write(path, updated)?;
    Ok(())
}

/// Resolve sending account from draft metadata.
fn resolve_account(meta: &HashMap<String, String>) -> Result<(String, crate::accounts::Account, String)> {
    let accounts = load_accounts_or_env(None)?;

    // Try **Account** field first
    if let Some(acct_name) = meta.get("Account") {
        if !acct_name.is_empty() {
            if let Some(acct) = accounts.get(acct_name) {
                let pwd = resolve_password(acct)?;
                return Ok((acct_name.clone(), acct.clone(), pwd));
            }
        }
    }

    // Try **From** field to match by email
    if let Some(from_addr) = meta.get("From") {
        if !from_addr.is_empty() {
            if let Some((name, acct)) = get_account_for_email(&accounts, from_addr) {
                let pwd = resolve_password(&acct)?;
                return Ok((name, acct, pwd));
            }
        }
    }

    // Fall back to default
    let (name, acct) = get_default_account(&accounts)?;
    let pwd = resolve_password(&acct)?;
    Ok((name, acct, pwd))
}

/// corky push-draft FILE [--send]
pub fn run(file: &Path, send: bool) -> Result<()> {
    if !file.exists() {
        bail!("File not found: {}", file.display());
    }

    let (meta, subject, body) = parse_draft(file)?;

    // Validate Status for --send
    let status = meta
        .get("Status")
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    if send && !status.is_empty() && !VALID_SEND_STATUSES.contains(&status.as_str()) {
        bail!(
            "Cannot send: Status is '{}'. Must be one of: {}",
            meta.get("Status").unwrap_or(&String::new()),
            VALID_SEND_STATUSES.join(", ")
        );
    }

    let (acct_name, acct, password) = resolve_account(&meta)?;

    println!("Account: {} ({})", acct_name, acct.user);
    println!("To:      {}", meta["To"]);
    println!("Subject: {}", subject);
    if let Some(author) = meta.get("Author") {
        println!("Author:  {}", author);
    }
    if let Some(status) = meta.get("Status") {
        println!("Status:  {}", status);
    }
    if let Some(reply_to) = meta.get("In-Reply-To") {
        println!("Reply:   {}", reply_to);
    }
    let body_preview = if body.len() > 80 {
        format!("{}...", &body[..80])
    } else {
        body.clone()
    };
    println!("Body:    {}", body_preview);
    println!();

    let email = compose_email(&meta, &subject, &body, &acct.user)?;

    if send {
        send_email(&email, &acct.smtp_host, acct.smtp_port, &acct.user, &password)?;
        update_draft_status(file, "sent")?;
        println!("Email sent. Status updated to 'sent'.");
    } else {
        push_to_drafts(
            &email,
            &acct.imap_host,
            acct.imap_port,
            acct.imap_starttls,
            &acct.user,
            &password,
            &acct.drafts_folder,
        )?;
        println!("Draft created. Open your email drafts to review and send.");
    }

    Ok(())
}
