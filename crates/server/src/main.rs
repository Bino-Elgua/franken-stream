mod routes;
mod sidecar;
mod state;

use axum::{routing::{get, post}, Router};
use state::AppState;
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let python_module = std::env::var("SIDECAR_MODULE")
        .unwrap_or_else(|_| "franken_stream.sidecar_main".to_string());

    info!("spawning Python sidecar: {python_module}");
    let state = AppState::new(&python_module).await?;
    info!("sidecar connected");

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        // Legacy routes
        .route("/api/search", get(routes::search::search_stream))
        .route("/api/health", get(routes::health::health_check))
        .route("/api/openclaw", post(routes::openclaw::handle_intent))
        // v1 routes
        .route("/api/v1/skills/manifest", get(routes::v1::skills_manifest))
        .route("/api/v1/search", post(routes::v1::v1_search))
        .route("/api/v1/play", post(routes::v1::v1_play))
        .route("/api/v1/control", post(routes::v1::v1_control))
        .route("/api/v1/status", get(routes::v1::v1_status))
        .route("/api/v1/embed/:id", get(routes::v1::v1_embed))
        .route("/api/v1/providers", get(routes::v1::v1_providers))
        .route("/api/v1/ws", get(routes::v1::ws_handler))
        .layer(cors)
        .with_state(state);

    let addr = std::env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:3001".to_string());
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("franken-server listening on {addr}");

    axum::serve(listener, app).await?;
    Ok(())
}
