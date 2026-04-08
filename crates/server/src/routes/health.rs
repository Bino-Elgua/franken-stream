use axum::{extract::State, Json};
use serde_json::{json, Value};

use crate::state::AppState;

/// GET /api/health — server liveness + provider health from sidecar.
pub async fn health_check(State(state): State<AppState>) -> Json<Value> {
    match state.sidecar.call("get_health", json!({})).await {
        Ok(providers) => Json(json!({
            "status": "ok",
            "sidecar": "connected",
            "providers": providers,
        })),
        Err(e) => Json(json!({
            "status": "degraded",
            "sidecar": "error",
            "error": e.to_string(),
        })),
    }
}
