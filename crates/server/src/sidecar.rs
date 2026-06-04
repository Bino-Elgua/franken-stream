use anyhow::{Context, Result};
use serde_json::{json, Value};
use shared::{RpcNotification, RpcRequest, RpcResponse};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{broadcast, Mutex};
use tracing::{info, warn};

/// Manages the Python sidecar process and JSON-RPC communication.
pub struct PythonSidecar {
    _process: Child,
    stdin: Arc<Mutex<tokio::process::ChildStdin>>,
    request_id: Arc<Mutex<i64>>,
    pending: Arc<Mutex<HashMap<i64, tokio::sync::oneshot::Sender<RpcResponse>>>>,
}

impl PythonSidecar {
    /// Spawn the Python sidecar and return (sidecar, notification_broadcast_tx).
    pub async fn spawn(python_module: &str) -> Result<(Self, broadcast::Sender<String>)> {
        let mut process = Command::new("python")
            .arg("-m")
            .arg(python_module)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .context("Failed to spawn Python sidecar")?;

        let stdin = Arc::new(Mutex::new(
            process.stdin.take().context("No stdin on child")?,
        ));
        let stdout = BufReader::new(process.stdout.take().context("No stdout on child")?);
        let stderr = BufReader::new(process.stderr.take().context("No stderr on child")?);

        let (notify_tx, _) = broadcast::channel::<String>(256);
        let notify_tx_clone = notify_tx.clone();

        let pending: Arc<Mutex<HashMap<i64, tokio::sync::oneshot::Sender<RpcResponse>>>> =
            Arc::new(Mutex::new(HashMap::new()));

        // Stdout reader: JSON-RPC responses (keyed by id)
        let pending_clone = pending.clone();
        tokio::spawn(async move {
            let mut lines = stdout.lines();
            while let Ok(Some(line)) = lines.next_line().await {
                match serde_json::from_str::<RpcResponse>(&line) {
                    Ok(resp) => {
                        if let Some(id) = resp.id {
                            if let Some(sender) = pending_clone.lock().await.remove(&id) {
                                let _ = sender.send(resp);
                            }
                        }
                    }
                    Err(e) => warn!("sidecar stdout parse error: {e} | line: {line}"),
                }
            }
            info!("sidecar stdout closed");
        });

        // Stderr reader: broadcast raw notification lines to all subscribers
        tokio::spawn(async move {
            let mut lines = stderr.lines();
            while let Ok(Some(line)) = lines.next_line().await {
                // Only broadcast lines that look like JSON notifications
                if line.starts_with('{') {
                    if let Ok(_) = serde_json::from_str::<RpcNotification>(&line) {
                        let _ = notify_tx_clone.send(line);
                    }
                }
            }
            info!("sidecar stderr closed");
        });

        Ok((
            Self {
                _process: process,
                stdin,
                request_id: Arc::new(Mutex::new(0)),
                pending,
            },
            notify_tx,
        ))
    }

    /// Send a JSON-RPC call and await the response.
    pub async fn call(&self, method: &str, params: Value) -> Result<Value> {
        let id = {
            let mut counter = self.request_id.lock().await;
            *counter += 1;
            *counter
        };

        let req = RpcRequest::new(method, params, id);
        let req_json =
            serde_json::to_string(&req).context("Failed to serialize RPC request")?;

        let (tx, rx) = tokio::sync::oneshot::channel();
        self.pending.lock().await.insert(id, tx);

        {
            let mut stdin = self.stdin.lock().await;
            stdin
                .write_all(req_json.as_bytes())
                .await
                .context("Failed to write to sidecar stdin")?;
            stdin.write_all(b"\n").await?;
            stdin.flush().await?;
        }

        let resp = rx.await.context("Sidecar response channel closed")?;

        if let Some(err) = resp.error {
            anyhow::bail!("Sidecar RPC error {}: {}", err.code, err.message);
        }

        Ok(resp.result.unwrap_or(Value::Null))
    }

    /// Fire-and-forget notification (no response expected).
    pub async fn notify(&self, method: &str, params: Value) -> Result<()> {
        let msg = json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        });
        let msg_json = serde_json::to_string(&msg)?;

        let mut stdin = self.stdin.lock().await;
        stdin.write_all(msg_json.as_bytes()).await?;
        stdin.write_all(b"\n").await?;
        stdin.flush().await?;
        Ok(())
    }
}
