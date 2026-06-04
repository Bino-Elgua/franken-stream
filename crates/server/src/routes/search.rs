use axum::{
    extract::{Query, State},
    response::sse::{Event, KeepAlive, Sse},
};
use futures::stream::Stream;
use serde::Deserialize;
use serde_json::json;
use shared::RpcNotification;
use std::convert::Infallible;
use tokio_stream::wrappers::ReceiverStream;
use tracing::error;

use crate::state::AppState;

#[derive(Debug, Deserialize)]
pub struct SearchParams {
    pub q: String,
    pub max_providers: Option<usize>,
}

/// GET /api/search?q=inception — SSE stream of search results.
pub async fn search_stream(
    State(state): State<AppState>,
    Query(params): Query<SearchParams>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let (tx, rx) = tokio::sync::mpsc::channel::<Result<Event, Infallible>>(64);

    tokio::spawn(async move {
        let search_params = json!({
            "query": params.q,
            "max_providers": params.max_providers.unwrap_or(5),
        });

        // Subscribe to sidecar notifications before firing the RPC call
        let mut notify_rx = state.notify_tx.subscribe();
        let tx_stream = tx.clone();

        let stream_handle = tokio::spawn(async move {
            loop {
                match notify_rx.recv().await {
                    Ok(line) => {
                        if let Ok(notif) = serde_json::from_str::<RpcNotification>(&line) {
                            if notif.method.as_deref() == Some("search.result") {
                                let event = Event::default()
                                    .event("result")
                                    .data(
                                        notif
                                            .params
                                            .map(|p| p.to_string())
                                            .unwrap_or_default(),
                                    );
                                if tx_stream.send(Ok(event)).await.is_err() {
                                    break;
                                }
                            }
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        });

        match state.sidecar.call("search", search_params).await {
            Ok(result) => {
                let done_event = Event::default()
                    .event("done")
                    .data(result.to_string());
                let _ = tx.send(Ok(done_event)).await;
            }
            Err(e) => {
                error!("search RPC error: {e}");
                let err_event = Event::default()
                    .event("error")
                    .data(json!({"message": e.to_string()}).to_string());
                let _ = tx.send(Ok(err_event)).await;
            }
        }

        stream_handle.abort();
    });

    Sse::new(ReceiverStream::new(rx)).keep_alive(KeepAlive::default())
}
