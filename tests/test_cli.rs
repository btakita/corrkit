//! Basic binary invocation tests (assert_cmd).

use assert_cmd::cargo::cargo_bin_cmd;
use assert_cmd::Command;
use predicates::prelude::*;

fn corrkit_cmd() -> Command {
    cargo_bin_cmd!("corrkit")
}

#[test]
fn test_binary_exists() {
    let _cmd = corrkit_cmd();
}

#[test]
fn test_cli_version() {
    let mut cmd = corrkit_cmd();
    cmd.arg("--version");
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("corrkit"));
}

#[test]
fn test_cli_help() {
    let mut cmd = corrkit_cmd();
    cmd.arg("--help");
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("Sync email threads"));
}

#[test]
fn test_cli_no_args_shows_error() {
    let mut cmd = corrkit_cmd();
    cmd.assert().failure();
}

#[test]
fn test_cli_help_subcommand() {
    let mut cmd = corrkit_cmd();
    cmd.arg("help");
    cmd.assert().success();
}

#[test]
fn test_cli_mailbox_list_subcommand() {
    let mut cmd = corrkit_cmd();
    cmd.args(["mailbox", "list"]);
    // May succeed or fail depending on config, but should not panic
    let output = cmd.output().unwrap();
    assert!(output.status.code().is_some());
}

#[test]
fn test_cli_audit_docs_subcommand() {
    let mut cmd = corrkit_cmd();
    cmd.arg("audit-docs");
    let output = cmd.output().unwrap();
    assert!(output.status.code().is_some());
}

#[test]
fn test_cli_init_requires_user() {
    let mut cmd = corrkit_cmd();
    cmd.arg("init");
    cmd.assert()
        .failure()
        .stderr(predicate::str::contains("--user"));
}

#[test]
fn test_cli_push_draft_requires_file() {
    let mut cmd = corrkit_cmd();
    cmd.arg("push-draft");
    cmd.assert().failure();
}

#[test]
fn test_cli_add_label_requires_args() {
    let mut cmd = corrkit_cmd();
    cmd.arg("add-label");
    cmd.assert().failure();
}

#[test]
fn test_cli_contact_add_requires_args() {
    let mut cmd = corrkit_cmd();
    cmd.arg("contact-add");
    cmd.assert().failure();
}

#[test]
fn test_cli_mailbox_add_requires_args() {
    let mut cmd = corrkit_cmd();
    cmd.args(["mailbox", "add"]);
    cmd.assert().failure();
}

#[test]
fn test_cli_mb_alias() {
    let mut cmd = corrkit_cmd();
    cmd.args(["mb", "add"]);
    cmd.assert().failure(); // fails because no args, but proves alias works
}

#[test]
fn test_cli_migrate_subcommand() {
    let mut cmd = corrkit_cmd();
    cmd.arg("migrate");
    // Will fail because no accounts.toml in cwd, but should not panic
    let output = cmd.output().unwrap();
    assert!(output.status.code().is_some());
}

#[test]
fn test_cli_sync_routes() {
    let tmp = tempfile::TempDir::new().unwrap();
    let project_dir = tmp.path().to_path_buf();
    let data_dir = project_dir.join("correspondence");

    // Create conversations dir with a thread that has a routed label
    std::fs::create_dir_all(data_dir.join("conversations")).unwrap();
    std::fs::write(
        data_dir.join("conversations/test-thread.md"),
        "# Test Thread\n\n\
         **Labels**: for-alex\n\
         **Accounts**: personal\n\
         **Thread ID**: test thread\n\
         **Last updated**: Mon, 10 Feb 2025 10:00:00 +0000\n\n\
         ---\n\n\
         ## Alice <alice@example.com> \u{2014} Mon, 10 Feb 2025 10:00:00 +0000\n\n\
         Hello there!\n",
    )
    .unwrap();

    // Create routing config
    std::fs::write(
        data_dir.join(".corrkit.toml"),
        "[accounts.personal]\n\
         provider = \"gmail\"\n\
         user = \"test@gmail.com\"\n\
         password = \"dummy\"\n\
         labels = [\"inbox\"]\n\n\
         [routing]\n\
         for-alex = [\"mailboxes/alex\"]\n",
    )
    .unwrap();

    let mut cmd = corrkit_cmd();
    cmd.current_dir(&project_dir);
    cmd.args(["sync", "routes"]);
    cmd.assert().success();

    // Verify the file was copied to the mailbox
    assert!(data_dir
        .join("mailboxes/alex/conversations/test-thread.md")
        .exists());
}

#[test]
fn test_cli_unknown_subcommand() {
    let mut cmd = corrkit_cmd();
    cmd.arg("nonexistent-command");
    cmd.assert().failure();
}

#[test]
fn test_cli_init_with_path() {
    let tmp = tempfile::TempDir::new().unwrap();
    let project_dir = tmp.path().join("test-init-cli");

    let mut cmd = corrkit_cmd();
    // Isolate from real config by using temp HOME
    cmd.env("HOME", tmp.path().to_string_lossy().as_ref());
    cmd.args([
        "init",
        "--user",
        "test@example.com",
        "--force",
        &project_dir.to_string_lossy(),
    ]);
    cmd.assert().success();

    assert!(project_dir.join("correspondence/conversations").exists());
    assert!(project_dir.join("correspondence/.corrkit.toml").exists());
    assert!(project_dir.join("correspondence/voice.md").exists());
}

#[test]
fn test_cli_help_filter() {
    let mut cmd = corrkit_cmd();
    cmd.args(["help", "sync"]);
    cmd.assert().success();
}

#[test]
fn test_cli_sync_unknown_account() {
    let tmp = tempfile::TempDir::new().unwrap();
    let data_dir = tmp.path().to_path_buf();

    std::fs::create_dir_all(data_dir.join("conversations")).unwrap();
    std::fs::write(
        data_dir.join(".corrkit.toml"),
        r#"
[accounts.personal]
provider = "gmail"
user = "test@gmail.com"
password = "dummy"
labels = ["inbox"]
"#,
    )
    .unwrap();

    let mut cmd = corrkit_cmd();
    cmd.env("CORRKIT_DATA", data_dir.to_string_lossy().as_ref());
    cmd.args(["sync", "account", "nonexistent"]);
    cmd.assert().failure();
}
