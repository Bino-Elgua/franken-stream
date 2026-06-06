"""Circuit breaker pattern for per-provider failure isolation."""

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict


class CircuitState(Enum):
    CLOSED = "closed"        # Normal — requests pass through
    OPEN = "open"            # Failing — skip this provider
    HALF_OPEN = "half_open"  # Probing — allow one request through


@dataclass
class _Breaker:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: float = 0.0
    success_count: int = 0  # successes in HALF_OPEN before closing


class CircuitBreaker:
    """
    Thread-safe per-provider circuit breaker.

    Transitions:
      CLOSED  → OPEN      after `failure_threshold` failures
      OPEN    → HALF_OPEN after `recovery_timeout` seconds
      HALF_OPEN → CLOSED  after `probe_successes` successes
      HALF_OPEN → OPEN    on any failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
        probe_successes: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.probe_successes = probe_successes
        self._breakers: Dict[str, _Breaker] = {}
        self._lock = Lock()

    def _get(self, provider: str) -> _Breaker:
        if provider not in self._breakers:
            self._breakers[provider] = _Breaker()
        return self._breakers[provider]

    def is_open(self, provider: str) -> bool:
        """Return True if requests to this provider should be skipped."""
        with self._lock:
            cb = self._get(provider)
            if cb.state == CircuitState.CLOSED:
                return False
            if cb.state == CircuitState.OPEN:
                if time.monotonic() - cb.last_failure >= self.recovery_timeout:
                    cb.state = CircuitState.HALF_OPEN
                    cb.success_count = 0
                    return False
                return True
            # HALF_OPEN: allow the probe through
            return False

    def record_success(self, provider: str) -> None:
        with self._lock:
            cb = self._get(provider)
            if cb.state == CircuitState.HALF_OPEN:
                cb.success_count += 1
                if cb.success_count >= self.probe_successes:
                    cb.state = CircuitState.CLOSED
                    cb.failure_count = 0
            elif cb.state == CircuitState.CLOSED:
                cb.failure_count = max(0, cb.failure_count - 1)

    def record_failure(self, provider: str) -> None:
        with self._lock:
            cb = self._get(provider)
            cb.failure_count += 1
            cb.last_failure = time.monotonic()
            if cb.state == CircuitState.HALF_OPEN or cb.failure_count >= self.failure_threshold:
                cb.state = CircuitState.OPEN

    def state_of(self, provider: str) -> CircuitState:
        with self._lock:
            return self._get(provider).state

    def reset(self, provider: str) -> None:
        with self._lock:
            self._breakers[provider] = _Breaker()
