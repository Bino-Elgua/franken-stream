"""E1 — Vantage Health Check Cron Skill.

Periodically checks Vantage platform health and optionally publishes a
daily status briefing as a text post on the agent's channel.

Usage::

    from skills.vantage_health_cron import VantageHealthCronSkill

    skill = VantageHealthCronSkill(api_key="vantage_...")
    print(skill.run_health_check())
    skill.schedule(interval_minutes=60)   # background loop
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VantageHealthCronSkill:
    """Monitor Vantage platform health and broadcast daily briefings."""

    def __init__(
        self,
        base_url: str = "",
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        from skills.vantage_publish import VantagePublishSkill
        self._skill = VantagePublishSkill(
            base_url=base_url, api_key=api_key, timeout=timeout
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Core methods ──────────────────────────────────────────────────────────

    def run_health_check(self) -> Dict[str, Any]:
        """Fetch /api/health and return structured result with a diagnosis."""
        try:
            data = self._skill.health()
        except Exception as e:
            return {
                "status": "unreachable",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        diagnosis = []
        if data.get("db") != "ok":
            diagnosis.append("Database connection error")
        if data.get("ffmpeg") != "ok":
            diagnosis.append("FFmpeg not available — video transcoding will fail")
        if not diagnosis:
            diagnosis.append("All systems operational")

        return {
            **data,
            "diagnosis": diagnosis,
            "healthy": data.get("status") == "ok",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def format_briefing(self, health: Dict[str, Any]) -> str:
        """Render a markdown health briefing suitable for a Vantage text post."""
        ts = health.get("checked_at", datetime.now(timezone.utc).isoformat())
        status_icon = "✅" if health.get("healthy") else "⚠️"
        lines = [
            f"# {status_icon} Vantage Platform Briefing",
            f"*Generated: {ts}*",
            "",
            "## System Status",
            f"- **Overall**: `{health.get('status', 'unknown')}`",
            f"- **Database**: `{health.get('db', 'unknown')}`",
            f"- **FFmpeg**: `{health.get('ffmpeg', 'unknown')}`",
            f"- **Version**: `{health.get('version', 'unknown')}`",
            "",
            "## Diagnosis",
        ]
        for d in health.get("diagnosis", []):
            lines.append(f"- {d}")
        lines += [
            "",
            "---",
            "*Automated health check via VantageHealthCronSkill*",
        ]
        return "\n".join(lines)

    def publish_daily_briefing(self, model_name: str = "health-cron") -> Dict[str, Any]:
        """Run a health check and publish the result as a text post."""
        health = self.run_health_check()
        content = self.format_briefing(health)
        status_label = "OK" if health.get("healthy") else "DEGRADED"
        title = f"Platform Health: {status_label} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        result = self._skill.publish_text(
            title=title,
            content=content,
            tags='["health", "monitoring", "automated"]',
            model_name=model_name,
        )
        return {**result, "health": health}

    # ── Scheduling ────────────────────────────────────────────────────────────

    def schedule(
        self,
        interval_minutes: int = 1440,
        publish_briefing: bool = True,
        on_degraded_callback=None,
    ) -> threading.Thread:
        """Start a background thread that checks health every interval_minutes.

        Args:
            interval_minutes: How often to run. Default 1440 = daily.
            publish_briefing: If True, post a text briefing each cycle.
            on_degraded_callback: Optional callable(health_dict) called when status != 'ok'.

        Returns the Thread so callers can join() or stop() it.
        """
        self._stop_event.clear()

        def loop():
            logger.info("VantageHealthCronSkill started (interval=%dm)", interval_minutes)
            while not self._stop_event.is_set():
                try:
                    health = self.run_health_check()
                    logger.info("Health check: %s", health.get("status"))
                    if not health.get("healthy") and on_degraded_callback:
                        try:
                            on_degraded_callback(health)
                        except Exception as e:
                            logger.warning("on_degraded_callback error: %s", e)
                    if publish_briefing and self._skill.api_key:
                        try:
                            self.publish_daily_briefing()
                        except Exception as e:
                            logger.warning("Failed to publish briefing: %s", e)
                except Exception as e:
                    logger.error("Health cron error: %s", e)
                self._stop_event.wait(timeout=interval_minutes * 60)
            logger.info("VantageHealthCronSkill stopped")

        self._thread = threading.Thread(target=loop, daemon=True, name="vantage-health-cron")
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Stop the background scheduling loop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
