use crate::sidecar::PythonSidecar;
use shared::RpcNotification;
use std::sync::Arc;
use tokio::sync::{mpsc, Mutex};

/// Shared application state passed to all Axum handlers.
#[derive(Clone)]
pub struct AppState {
    pub sidecar: Arc<PythonSidecar>,
    pub notify_rx: Arc<Mutex<mpsc::Receiver<RpcNotification>>>,
}

impl AppState {
    pub async fn new(python_module: &str) -> anyhow::Result<Self> {
        let (sidecar, notify_rx) = PythonSidecar::spawn(python_module).await?;
        Ok(Self {
            sidecar: Arc::new(sidecar),
            notify_rx: Arc::new(Mutex::new(notify_rx)),
        })
    }
}
