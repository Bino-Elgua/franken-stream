use axum::{
    extract::{Query, State},
    response::sse::{Event, KeepAlive, Sse},
};
use futures::stream::Stream;
use serde::Deserialize;
use serde_json::json;
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
        // Fire the search RPC call to the Python sidecar
        let search_params = json!({
            "query": params.q,
            "max_providers": params.max_providers.unwrap_or(5),
        });

        // Listen for streaming notifications from stderr
        let notify_rx = state.notify_rx.clone();
        let tx_stream = tx.clone();
        let stream_handle = tokio::spawn(async move {
            let mut rx = notify_rx.lock().await;
            while let Some(notif) = rx.recv().await {
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
        });

        // Send the RPC call (blocks until sidecar finishes searching)
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
