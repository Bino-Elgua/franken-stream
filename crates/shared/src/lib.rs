use serde::{Deserialize, Serialize};

/// JSON-RPC request sent to the Python sidecar via stdin.
#[derive(Debug, Serialize)]
pub struct RpcRequest {
    pub jsonrpc: &'static str,
    pub method: String,
    pub params: serde_json::Value,
    pub id: i64,
}

impl RpcRequest {
    pub fn new(method: impl Into<String>, params: serde_json::Value, id: i64) -> Self {
        Self {
            jsonrpc: "2.0",
            method: method.into(),
            params,
            id,
        }
    }
}

/// JSON-RPC response received from the Python sidecar via stdout.
#[derive(Debug, Deserialize)]
pub struct RpcResponse {
    pub id: Option<i64>,
    pub result: Option<serde_json::Value>,
    pub error: Option<RpcError>,
}

#[derive(Debug, Deserialize)]
pub struct RpcError {
    pub code: i64,
    pub message: String,
}

/// Streaming notification from Python sidecar via stderr.
#[derive(Debug, Deserialize)]
pub struct RpcNotification {
    pub method: Option<String>,
    pub params: Option<serde_json::Value>,
}

/// A single search result from a provider.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub title: String,
    pub url: String,
    pub provider: String,
}

/// Provider health stats as reported by the Python sidecar.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderHealth {
    pub url: String,
    pub success_rate: f32,
    pub avg_ms: f32,
    pub consecutive_failures: u8,
}

/// SSE event types sent to the frontend.
#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum SsePayload {
    #[serde(rename = "result")]
    Result { provider: String, results: Vec<SearchResult> },
    #[serde(rename = "error")]
    Error { provider: String, message: String },
    #[serde(rename = "done")]
    Done { total: usize },
}
