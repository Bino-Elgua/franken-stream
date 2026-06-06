use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Path, State,
    },
    response::IntoResponse,
    Json,
};
use serde_json::{json, Value};
use shared::RpcNotification;

use crate::state::AppState;

/// GET /api/v1/skills/manifest — agent capability discovery.
pub async fn skills_manifest(State(state): State<AppState>) -> Json<Value> {
    match state.sidecar.call("providers", json!({})).await {
        Ok(_) => {}
        Err(_) => {}
    }
    Json(json!({
        "skill": {
            "id": "franken-stream",
            "name": "Franken-Stream Media Player",
            "version": "2.0.0",
            "description": "Search and stream movies/TV shows via multiple providers"
        },
        "endpoints": {
            "search": "POST /api/v1/search",
            "play": "POST /api/v1/play",
            "control": "POST /api/v1/control",
            "status": "GET /api/v1/status",
            "providers": "GET /api/v1/providers",
            "websocket": "GET /api/v1/ws"
        }
    }))
}

/// POST /api/v1/search — structured search forwarded to Python sidecar.
pub async fn v1_search(State(state): State<AppState>, Json(body): Json<Value>) -> Json<Value> {
    match state.sidecar.call("search", body).await {
        Ok(result) => Json(json!({"status": "ok", "data": result})),
        Err(e) => Json(json!({"status": "error", "message": e.to_string()})),
    }
}

/// POST /api/v1/play — launch playback via Python sidecar.
pub async fn v1_play(State(state): State<AppState>, Json(body): Json<Value>) -> Json<Value> {
    match state.sidecar.call("play", body).await {
        Ok(result) => Json(result),
        Err(e) => Json(json!({"status": "error", "message": e.to_string()})),
    }
}

/// POST /api/v1/control — control playback via Python sidecar.
pub async fn v1_control(State(state): State<AppState>, Json(body): Json<Value>) -> Json<Value> {
    match state.sidecar.call("control", body).await {
        Ok(result) => Json(result),
        Err(e) => Json(json!({"status": "error", "message": e.to_string()})),
    }
}

/// GET /api/v1/status — playback status from Python sidecar.
pub async fn v1_status(State(state): State<AppState>) -> Json<Value> {
    match state.sidecar.call("status", json!({})).await {
        Ok(result) => Json(result),
        Err(e) => Json(json!({"is_playing": false, "error": e.to_string()})),
    }
}

/// GET /api/v1/embed/:id — get embed URL from Python sidecar.
pub async fn v1_embed(
    State(state): State<AppState>,
    Path(media_id): Path<String>,
) -> Json<Value> {
    match state.sidecar.call("get_embed", json!({"id": media_id})).await {
        Ok(result) => Json(result),
        Err(e) => Json(json!({"status": "error", "message": e.to_string()})),
    }
}

/// GET /api/v1/providers — provider list and health.
pub async fn v1_providers(State(state): State<AppState>) -> Json<Value> {
    match state.sidecar.call("providers", json!({})).await {
        Ok(result) => Json(result),
        Err(e) => Json(json!({"status": "error", "message": e.to_string()})),
    }
}

/// GET /api/v1/ws — WebSocket upgrade for real-time sidecar notifications.
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_ws(socket, state))
}

async fn handle_ws(mut socket: WebSocket, state: AppState) {
    let mut rx = state.notify_tx.subscribe();

    // Send welcome
    let welcome = r#"{"type":"connected","message":"Franken-Stream WebSocket ready"}"#;
    if socket.send(Message::Text(welcome.to_string())).await.is_err() {
        return;
    }

    loop {
        tokio::select! {
            // Forward sidecar notifications to the WebSocket client
            result = rx.recv() => {
                match result {
                    Ok(line) => {
                        if socket.send(Message::Text(line)).await.is_err() {
                            break;
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
            // Handle incoming messages from the WebSocket client
            msg = socket.recv() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Ok(cmd) = serde_json::from_str::<Value>(&text) {
                            if cmd.get("action").and_then(|a| a.as_str()) == Some("ping") {
                                let _ = socket.send(Message::Text(r#"{"type":"pong"}"#.to_string())).await;
                            }
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => break,
                    _ => {}
                }
            }
        }
    }
}
