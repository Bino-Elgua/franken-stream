"""E2 — Vantage Spike-to-Production Pipeline Skill.

Implements a multi-step workflow:
  1. Draft a research/spike post (text draft on Vantage)
  2. Send a DM to a reviewer agent for approval
  3. On approval, publish the draft immediately
  4. Optionally send a collab invite to a co-author

Designed to integrate with Hermes / OpenClaw agent workflows where spikes
are proposed, reviewed by another agent, then promoted to live content.

Usage::

    from skills.vantage_spike_pipeline import VantageSpikePipeline

    pipeline = VantageSpikePipeline(api_key="vantage_...")

    # Step 1: create a draft
    draft = pipeline.create_spike_draft(
        title="Spike: Distributed Inference",
        content="# Proposal\\n...",
        reviewer="Hermes",
    )
    broadcast_id = draft["broadcast_id"]

    # Step 2: poll until reviewer approves via DM
    result = pipeline.await_approval_and_publish(broadcast_id, timeout_seconds=3600)
    print(result)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VantageSpikePipeline:
    """Multi-step spike-to-production publishing workflow."""

    # DM subjects that indicate reviewer approval
    APPROVE_PATTERNS = [
        re.compile(r"\b(approved?|lgtm|ship\s*it|publish|go\s+ahead|looks?\s+good)\b", re.I),
    ]
    REJECT_PATTERNS = [
        re.compile(r"\b(reject(ed)?|nope|don'?t\s+publish|hold\s+off|needs?\s+work)\b", re.I),
    ]

    def __init__(
        self,
        base_url: str = "",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        from skills.vantage_publish import VantagePublishSkill
        self._skill = VantagePublishSkill(
            base_url=base_url, api_key=api_key, timeout=timeout
        )

    # ── Step 1 ────────────────────────────────────────────────────────────────

    def create_spike_draft(
        self,
        title: str,
        content: str,
        reviewer: Optional[str] = None,
        co_author: Optional[str] = None,
        tags: str = '["spike", "draft"]',
        model_name: str = "",
    ) -> Dict[str, Any]:
        """Create a text post as a draft and notify the reviewer via DM.

        Args:
            title: Post title (prepend 'Spike:' by convention).
            content: Markdown body of the spike.
            reviewer: Agent name to DM for review approval.
            co_author: Agent name to invite as collaborator (optional).
            tags: JSON array of string tags.
            model_name: Model that generated the spike.

        Returns:
            {broadcast_id, status, reviewer_notified, co_author_invited}
        """
        result = self._skill.publish_text(
            title=title,
            content=content,
            tags=tags,
            model_name=model_name,
            draft=True,
        )
        broadcast_id = result["broadcast_id"]
        reviewer_notified = False
        co_author_invited = False

        if reviewer:
            try:
                self._skill.send_message(
                    recipient=reviewer,
                    subject=f"Review requested: {title}",
                    content=(
                        f"Hi {reviewer},\n\n"
                        f"I've drafted a spike post and need your review:\n\n"
                        f"**Title:** {title}\n"
                        f"**Draft ID:** {broadcast_id}\n\n"
                        f"Reply with 'approved' or 'lgtm' to publish it, "
                        f"or 'reject' to keep it in draft.\n\n"
                        f"— Your pipeline"
                    ),
                )
                reviewer_notified = True
                logger.info("Notified reviewer %s about draft %d", reviewer, broadcast_id)
            except Exception as e:
                logger.warning("Could not notify reviewer %s: %s", reviewer, e)

        if co_author:
            try:
                self._skill.send_message(
                    recipient=co_author,
                    subject=f"Collab invite: {title}",
                    content=(
                        f"Hi {co_author},\n\n"
                        f"I'd love your collaboration on this spike:\n\n"
                        f"**Title:** {title}\n"
                        f"**Draft ID:** {broadcast_id}\n\n"
                        f"Reply to discuss!"
                    ),
                )
                co_author_invited = True
            except Exception as e:
                logger.warning("Could not invite co-author %s: %s", co_author, e)

        return {
            **result,
            "reviewer_notified": reviewer_notified,
            "co_author_invited": co_author_invited,
        }

    # ── Step 2 ────────────────────────────────────────────────────────────────

    def check_inbox_for_approval(self, broadcast_id: int) -> Optional[str]:
        """Scan the inbox for an approval/rejection DM about broadcast_id.

        Returns 'approved', 'rejected', or None if no decision yet.
        """
        try:
            inbox = self._skill.get_inbox()
        except Exception:
            return None

        id_pattern = re.compile(rf"\b{broadcast_id}\b")
        for msg in inbox:
            body = (msg.get("content") or "") + " " + (msg.get("subject") or "")
            if not id_pattern.search(body) and broadcast_id not in (msg.get("subject") or ""):
                # Fallback: check most recent messages without ID filter too
                pass
            for pat in self.APPROVE_PATTERNS:
                if pat.search(body):
                    return "approved"
            for pat in self.REJECT_PATTERNS:
                if pat.search(body):
                    return "rejected"
        return None

    def await_approval_and_publish(
        self,
        broadcast_id: int,
        timeout_seconds: float = 3600.0,
        poll_interval: float = 30.0,
    ) -> Dict[str, Any]:
        """Poll inbox until a reviewer approves or rejects the draft.

        On approval: publishes immediately and returns {ok, status, stream_url}.
        On rejection or timeout: returns {ok: False, reason}.
        """
        deadline = time.monotonic() + timeout_seconds
        logger.info("Awaiting approval for broadcast %d (timeout %.0fs)", broadcast_id, timeout_seconds)

        while time.monotonic() < deadline:
            decision = self.check_inbox_for_approval(broadcast_id)
            if decision == "approved":
                logger.info("Broadcast %d approved — publishing now", broadcast_id)
                result = self._skill._run(
                    self._skill._client().publish_now(broadcast_id)  # type: ignore[attr-defined]
                )
                return {"ok": True, "decision": "approved", **result}
            if decision == "rejected":
                logger.info("Broadcast %d rejected by reviewer", broadcast_id)
                return {"ok": False, "decision": "rejected", "broadcast_id": broadcast_id}

            remaining = deadline - time.monotonic()
            wait = min(poll_interval, max(0, remaining))
            logger.debug("No decision yet for %d, waiting %.0fs", broadcast_id, wait)
            time.sleep(wait)

        return {
            "ok": False,
            "decision": "timeout",
            "broadcast_id": broadcast_id,
            "message": f"No approval received within {timeout_seconds:.0f}s",
        }

    # ── Convenience ───────────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        title: str,
        content: str,
        reviewer: str,
        co_author: Optional[str] = None,
        tags: str = '["spike", "draft"]',
        model_name: str = "",
        approval_timeout: float = 3600.0,
    ) -> Dict[str, Any]:
        """Run the entire spike → draft → notify → await-approval → publish flow.

        Blocks until approval, rejection, or timeout.
        """
        draft = self.create_spike_draft(
            title=title,
            content=content,
            reviewer=reviewer,
            co_author=co_author,
            tags=tags,
            model_name=model_name,
        )
        broadcast_id = draft["broadcast_id"]
        result = self.await_approval_and_publish(
            broadcast_id, timeout_seconds=approval_timeout
        )
        return {**draft, **result}

    # ── Listing helpers ───────────────────────────────────────────────────────

    def list_pending_spikes(self) -> List[Dict[str, Any]]:
        """Return all draft broadcasts (i.e. spikes awaiting review)."""
        try:
            broadcasts = self._skill.my_broadcasts()
            return [b for b in broadcasts if b.get("status") == "draft"]
        except Exception as e:
            return [{"error": str(e)}]
