//! OAuth2 authorization code flow with PKCE for social platforms.

use anyhow::{bail, Context, Result};
use chrono::{Duration, Utc};

use super::platform::Platform;
use super::token_store::{StoredToken, TokenStore};
use super::profiles::{PlatformEntry, ProfilesFile};
use crate::config::corky_config;

const REDIRECT_URI: &str = "http://127.0.0.1:8484/callback";
const CALLBACK_TIMEOUT_SECS: u64 = 120;

/// LinkedIn OAuth scopes.
const LINKEDIN_SCOPES: &[&str] = &["openid", "profile", "w_member_social"];

/// Client credentials resolved from .corky.toml or env vars.
struct ClientCredentials {
    client_id: String,
    client_secret: String,
}

/// Resolve client credentials for a platform.
///
/// Resolution order per field: inline value > `_cmd` (shell command) > env var.
fn resolve_credentials(platform: Platform) -> Result<ClientCredentials> {
    match platform {
        Platform::LinkedIn => {
            // Try .corky.toml first (inline or _cmd)
            if let Some(cfg) = corky_config::try_load_config(None) {
                if let Some(li) = &cfg.linkedin {
                    let has_config = !li.client_id.is_empty()
                        || !li.client_id_cmd.is_empty()
                        || !li.client_secret.is_empty()
                        || !li.client_secret_cmd.is_empty();
                    if has_config {
                        let client_id = crate::util::resolve_secret(
                            &li.client_id,
                            &li.client_id_cmd,
                            "LinkedIn client_id (check [linkedin] in .corky.toml)",
                        )?;
                        let client_secret = crate::util::resolve_secret(
                            &li.client_secret,
                            &li.client_secret_cmd,
                            "LinkedIn client_secret (check [linkedin] in .corky.toml)",
                        )?;
                        return Ok(ClientCredentials {
                            client_id,
                            client_secret,
                        });
                    }
                }
            }
            // Fall back to env vars
            let client_id = std::env::var("CORKY_LINKEDIN_CLIENT_ID")
                .context("LinkedIn client_id not found.\nSet [linkedin] in .corky.toml or CORKY_LINKEDIN_CLIENT_ID env var.")?;
            let client_secret = std::env::var("CORKY_LINKEDIN_CLIENT_SECRET")
                .context("LinkedIn client_secret not found.\nSet [linkedin] in .corky.toml or CORKY_LINKEDIN_CLIENT_SECRET env var.")?;
            Ok(ClientCredentials {
                client_id,
                client_secret,
            })
        }
        _ => bail!("OAuth not yet implemented for {}", platform),
    }
}

/// Generate a random state parameter for CSRF protection.
fn generate_state() -> String {
    use std::time::SystemTime;
    let nonce = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{:x}", nonce)
}

/// Build the authorization URL for a platform.
pub fn build_auth_url(platform: Platform) -> Result<(String, String)> {
    let creds = resolve_credentials(platform)?;
    let state = generate_state();

    match platform {
        Platform::LinkedIn => {
            let scopes = LINKEDIN_SCOPES.join("%20");
            let url = format!(
                "https://www.linkedin.com/oauth/v2/authorization\
                 ?response_type=code\
                 &client_id={}\
                 &redirect_uri={}\
                 &state={}\
                 &scope={}",
                urlencode(&creds.client_id),
                urlencode(REDIRECT_URI),
                urlencode(&state),
                scopes,
            );
            Ok((url, state))
        }
        _ => bail!("Auth URL generation not yet implemented for {}", platform),
    }
}

/// Percent-encode a string for use in application/x-www-form-urlencoded bodies.
fn urlencode(s: &str) -> String {
    let mut out = String::with_capacity(s.len() * 2);
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char);
            }
            _ => {
                out.push_str(&format!("%{:02X}", b));
            }
        }
    }
    out
}

/// Parse callback query string, returning (code, state).
pub fn parse_callback(query: &str) -> Result<(String, String)> {
    let mut code = None;
    let mut state = None;
    let mut error = None;

    for pair in query.split('&') {
        let mut parts = pair.splitn(2, '=');
        let key = parts.next().unwrap_or("");
        let val = parts.next().unwrap_or("");
        match key {
            "code" => code = Some(val.to_string()),
            "state" => state = Some(val.to_string()),
            "error" => error = Some(val.to_string()),
            "error_description" => {
                if error.is_some() {
                    error = Some(format!("{}: {}", error.unwrap(), val.replace('+', " ")));
                }
            }
            _ => {}
        }
    }

    if let Some(err) = error {
        bail!("OAuth error: {}", err);
    }

    let code = code.ok_or_else(|| anyhow::anyhow!("Callback missing 'code' parameter"))?;
    let state = state.ok_or_else(|| anyhow::anyhow!("Callback missing 'state' parameter"))?;

    Ok((code, state))
}

/// Exchange authorization code for tokens.
fn exchange_code(platform: Platform, code: &str) -> Result<StoredToken> {
    let creds = resolve_credentials(platform)?;

    match platform {
        Platform::LinkedIn => {
            let body_str = format!(
                "grant_type=authorization_code&code={}&redirect_uri={}&client_id={}&client_secret={}",
                urlencode(code),
                urlencode(REDIRECT_URI),
                urlencode(&creds.client_id),
                urlencode(&creds.client_secret),
            );
            let resp = match ureq::post("https://www.linkedin.com/oauth/v2/accessToken")
                .set("Content-Type", "application/x-www-form-urlencoded")
                .send_string(&body_str)
            {
                Ok(r) => r,
                Err(ureq::Error::Status(status, resp)) => {
                    let err_body = resp.into_string().unwrap_or_default();
                    bail!("Token exchange failed (HTTP {}): {}", status, err_body);
                }
                Err(e) => return Err(e.into()),
            };

            let body: serde_json::Value = resp.into_json()?;
            let access_token = body["access_token"]
                .as_str()
                .ok_or_else(|| anyhow::anyhow!("Missing access_token in response"))?
                .to_string();
            let expires_in = body["expires_in"].as_i64().unwrap_or(3600);
            let refresh_token = body["refresh_token"].as_str().map(|s| s.to_string());

            Ok(StoredToken {
                access_token,
                refresh_token,
                expires_at: Utc::now() + Duration::seconds(expires_in),
                scopes: LINKEDIN_SCOPES.iter().map(|s| s.to_string()).collect(),
                platform: platform.to_string(),
            })
        }
        _ => bail!("Token exchange not yet implemented for {}", platform),
    }
}

/// Run the full OAuth flow: open browser, wait for callback, exchange code, store token.
pub fn run(platform: Platform, profile_name: Option<&str>) -> Result<()> {
    let (auth_url, expected_state) = build_auth_url(platform)?;

    println!("Opening browser for {} authorization...", platform);
    println!("If the browser doesn't open, visit:\n  {}\n", auth_url);

    if open::that(&auth_url).is_err() {
        eprintln!("Could not open browser automatically.");
    }

    // Start local callback server
    println!("Waiting for callback on {}...", REDIRECT_URI);
    let server = tiny_http::Server::http("127.0.0.1:8484")
        .map_err(|e| anyhow::anyhow!("Failed to start callback server: {}", e))?;

    let request = server
        .recv_timeout(std::time::Duration::from_secs(CALLBACK_TIMEOUT_SECS))
        .map_err(|e| anyhow::anyhow!("Callback server error: {}", e))?
        .ok_or_else(|| anyhow::anyhow!("Timed out waiting for OAuth callback ({}s)", CALLBACK_TIMEOUT_SECS))?;

    // Parse callback
    let url = request.url().to_string();
    let query = url.split('?').nth(1).unwrap_or("");
    let (code, state) = parse_callback(query)?;

    // Respond to the browser
    let response = tiny_http::Response::from_string(
        "Authorization successful! You can close this tab."
    );
    let _ = request.respond(response);

    // Verify state (CSRF protection)
    if state != expected_state {
        bail!(
            "State mismatch (CSRF protection). Expected '{}', got '{}'",
            expected_state,
            state
        );
    }

    // Exchange code for token
    println!("Exchanging authorization code...");
    let token = exchange_code(platform, &code)?;

    // Get user URN (for LinkedIn)
    let urn = match platform {
        Platform::LinkedIn => {
            let urn = super::linkedin::get_user_urn(&token.access_token)?;
            println!("Authenticated as URN: {}", urn);
            urn
        }
        _ => bail!("URN retrieval not yet implemented for {}", platform),
    };

    // Update profiles.toml if profile name given
    if let Some(name) = profile_name {
        update_profile_urn(name, platform, &urn)?;
    }

    // Store token
    let mut store = TokenStore::load()?;
    store.upsert(urn.clone(), token);
    store.save()?;

    println!("Token stored for URN: {}", urn);
    Ok(())
}

/// Update the URN in profiles.toml for a given profile/platform.
fn update_profile_urn(profile_name: &str, platform: Platform, urn: &str) -> Result<()> {
    let path = crate::resolve::profiles_toml();
    let mut profiles = if path.exists() {
        ProfilesFile::load_from(&path)?
    } else {
        ProfilesFile::default()
    };

    let profile = profiles.profiles.entry(profile_name.to_string()).or_insert_with(|| {
        super::profiles::Profile {
            linkedin: None,
            bluesky: None,
            mastodon: None,
            twitter: None,
        }
    });

    // Update or create the platform entry
    let entry = match platform {
        Platform::LinkedIn => profile.linkedin.get_or_insert_with(|| PlatformEntry {
            handle: String::new(),
            urn: None,
        }),
        Platform::Bluesky => profile.bluesky.get_or_insert_with(|| PlatformEntry {
            handle: String::new(),
            urn: None,
        }),
        Platform::Mastodon => profile.mastodon.get_or_insert_with(|| PlatformEntry {
            handle: String::new(),
            urn: None,
        }),
        Platform::Twitter => profile.twitter.get_or_insert_with(|| PlatformEntry {
            handle: String::new(),
            urn: None,
        }),
    };
    entry.urn = Some(urn.to_string());

    let content = toml::to_string_pretty(&profiles)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, content)?;
    println!("Updated profiles.toml: {}.{}.urn = {}", profile_name, platform, urn);
    Ok(())
}
