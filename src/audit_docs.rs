//! Audit instruction files against the codebase.
//!
//! Delegates to the shared `instruction_files` crate with corky-specific config.

use anyhow::Result;
use instruction_files::AuditConfig;

pub fn run() -> Result<()> {
    instruction_files::run(&AuditConfig::corky(), None)
}
