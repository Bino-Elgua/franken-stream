use axum::{extract::State, response::Json};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::state::AppState;

#[derive(Debug, Deserialize)]
struct OpenClawRequest {
    intent: String,
    params: Option<Value>,
}

#[derive(Debug, Serialize)]
struct OpenClawResponse {
    status: String,
    action_taken: String,
    data: Value,
    message: String,
}

pub async fn handle_intent(
    State(state): State<AppState>,
    Json(payload): Json<OpenClawRequest>,
) -> Json<OpenClawResponse> {
    let params = payload.params.unwrap_or_default();
    match state.sidecar.call("openclaw", json!({
        "intent": payload.intent,
        "params": params,
    }))
    .await
    {
        Ok(result) => Json(OpenClawResponse {
            status: result.get("status").and_then(Value::as_str).unwrap_or("success").into(),
            action_taken: result
                .get("action_taken")
                .and_then(Value::as_str)
                .unwrap_or("none")
                .into(),
            data: result.get("data").cloned().unwrap_or_default(),
            message: result
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("OpenClaw request processed.")
                .into(),
        }),
        Err(e) => Json(OpenClawResponse {
            status: "error".into(),
            action_taken: "none".into(),
            data: json!({"error": e.to_string()}),
            message: "Failed to process OpenClaw intent.".into(),
        }),
    }
}
