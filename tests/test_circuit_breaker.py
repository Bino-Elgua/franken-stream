"""Tests for the circuit breaker state machine."""

import time

import pytest

from franken_stream.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerInitialState:
    def test_unknown_provider_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state_of("new_provider") == CircuitState.CLOSED

    def test_is_open_returns_false_for_new_provider(self):
        cb = CircuitBreaker()
        assert cb.is_open("p") is False

    def test_independent_providers_are_isolated(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("p1")
        assert cb.is_open("p1") is True
        assert cb.is_open("p2") is False


class TestClosedState:
    def test_single_failure_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("p")
        assert cb.state_of("p") == CircuitState.CLOSED

    def test_success_in_closed_decrements_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("p")
        cb.record_failure("p")
        cb.record_success("p")  # decrement by 1 → count = 1
        cb.record_failure("p")  # count = 2, still below threshold
        cb.record_failure("p")  # count = 3 → OPEN
        assert cb.state_of("p") == CircuitState.OPEN

    def test_reaching_threshold_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure("p")
        assert cb.state_of("p") == CircuitState.OPEN
        assert cb.is_open("p") is True

    def test_success_in_closed_does_not_open(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(5):
            cb.record_success("p")
        assert cb.state_of("p") == CircuitState.CLOSED


class TestOpenState:
    def test_open_circuit_blocks_requests(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure("p")
        assert cb.is_open("p") is True

    def test_open_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure("p")
        assert cb.state_of("p") == CircuitState.OPEN
        time.sleep(0.02)
        # is_open() triggers the OPEN → HALF_OPEN transition
        assert cb.is_open("p") is False
        assert cb.state_of("p") == CircuitState.HALF_OPEN

    def test_circuit_stays_open_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure("p")
        assert cb.is_open("p") is True
        assert cb.state_of("p") == CircuitState.OPEN


class TestHalfOpenState:
    def test_probe_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, probe_successes=2)
        cb.record_failure("p")
        time.sleep(0.02)
        cb.is_open("p")  # trigger OPEN → HALF_OPEN
        cb.record_success("p")
        cb.record_success("p")
        assert cb.state_of("p") == CircuitState.CLOSED

    def test_single_probe_success_does_not_close_when_threshold_is_2(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, probe_successes=2)
        cb.record_failure("p")
        time.sleep(0.02)
        cb.is_open("p")
        cb.record_success("p")
        assert cb.state_of("p") == CircuitState.HALF_OPEN

    def test_probe_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure("p")
        time.sleep(0.02)
        cb.is_open("p")
        cb.record_failure("p")
        assert cb.state_of("p") == CircuitState.OPEN

    def test_half_open_allows_probe_through(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure("p")
        time.sleep(0.02)
        cb.is_open("p")  # → HALF_OPEN
        assert cb.is_open("p") is False  # probe allowed


class TestReset:
    def test_reset_clears_open_circuit(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("p")
        assert cb.state_of("p") == CircuitState.OPEN
        cb.reset("p")
        assert cb.state_of("p") == CircuitState.CLOSED
        assert cb.is_open("p") is False

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("p")
        cb.record_failure("p")
        cb.reset("p")
        cb.record_failure("p")  # after reset, only 1 failure
        assert cb.state_of("p") == CircuitState.CLOSED

    def test_reset_unregistered_provider_does_not_raise(self):
        cb = CircuitBreaker()
        cb.reset("never_seen")  # should not raise

    def test_reset_one_provider_does_not_affect_another(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("p1")
        cb.record_failure("p2")
        cb.reset("p1")
        assert cb.state_of("p1") == CircuitState.CLOSED
        assert cb.state_of("p2") == CircuitState.OPEN
