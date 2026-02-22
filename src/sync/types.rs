//! Sync data types: Message, Thread, SyncState.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: String,
    pub thread_id: String,
    pub from: String,
    pub date: String,
    pub subject: String,
    pub body: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Thread {
    pub id: String,
    pub subject: String,
    #[serde(default)]
    pub labels: Vec<String>,
    #[serde(default)]
    pub accounts: Vec<String>,
    #[serde(default)]
    pub messages: Vec<Message>,
    #[serde(default)]
    pub last_date: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LabelState {
    pub uidvalidity: u32,
    pub last_uid: u32,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AccountSyncState {
    #[serde(default)]
    pub labels: HashMap<String, LabelState>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SyncState {
    #[serde(default)]
    pub accounts: HashMap<String, AccountSyncState>,
}

pub fn load_state(data: &[u8]) -> anyhow::Result<SyncState> {
    let state: SyncState = serde_json::from_slice(data)?;
    Ok(state)
}
