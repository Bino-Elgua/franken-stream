use crate::sidecar::PythonSidecar;
use std::sync::Arc;
use tokio::sync::broadcast;

/// Shared application state passed to all Axum handlers.
#[derive(Clone)]
pub struct AppState {
    pub sidecar: Arc<PythonSidecar>,
    /// Broadcast channel for sidecar stderr notifications (search results, etc.)
    pub notify_tx: broadcast::Sender<String>,
}

impl AppState {
    pub async fn new(python_module: &str) -> anyhow::Result<Self> {
        let (sidecar, notify_tx) = PythonSidecar::spawn(python_module).await?;
        Ok(Self {
            sidecar: Arc::new(sidecar),
            notify_tx,
        })
    }
}
