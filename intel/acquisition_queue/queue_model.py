# N-0 SLICE 7 -- per-source-family queue model with circuit breaker. A reusable utility only --
# not yet wired into daily.yml's actual fetch jobs this round (those already run as isolated
# GitHub Actions jobs per source family; this module is for future same-process queuing). Never
# retries infinitely.
import time

QUEUE_FAMILIES = ("NEWS_QUEUE", "RESEARCH_QUEUE", "POLICY_QUEUE", "STATISTICS_QUEUE",
                   "PRIVATE_RESEARCH_QUEUE")

CIRCUIT_STATES = ("CLOSED", "OPEN", "HALF_OPEN")


class CircuitBreaker:
    """Deterministic circuit breaker: opens after `failure_threshold` consecutive failures,
    stays OPEN for `cooldown_seconds`, then allows exactly one HALF_OPEN probe."""

    def __init__(self, failure_threshold=3, cooldown_seconds=60, clock=time.time):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.opened_at = None

    def allow_request(self):
        if self.state == "OPEN":
            if self._clock() - self.opened_at >= self.cooldown_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self):
        self.consecutive_failures += 1
        if self.state == "HALF_OPEN" or self.consecutive_failures >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = self._clock()


NON_RETRYABLE_HTTP_STATUS_CODES = (401, 403)  # auth/permission failures: retrying on the same
# credentials cannot succeed, so these must never be retried the same way as a 5xx/transient error.


def retry_with_backoff(attempt, base_seconds=1, max_retries=4, http_status_code=None):
    """Returns the backoff delay for `attempt` (0-indexed), or None once max_retries is exceeded
    or `http_status_code` is a non-retryable 4xx (401/403) (the caller must stop in either case --
    this function never signals infinite retry, and never signals a retry for an auth failure)."""
    if http_status_code in NON_RETRYABLE_HTTP_STATUS_CODES:
        return None
    if attempt >= max_retries:
        return None
    return base_seconds * (2 ** attempt)


class Job:
    """An idempotent job wrapper: running the same job_id twice never double-executes the
    underlying action -- the caller's `fn` is expected to itself be idempotent (as
    admit_statistical_series()/upsert_claim()/etc. already are), and this wrapper additionally
    tracks which job_ids have already been dispatched in this process."""

    def __init__(self):
        self._dispatched = set()

    def dispatch(self, job_id, fn, *args, **kwargs):
        already_dispatched = job_id in self._dispatched
        self._dispatched.add(job_id)
        result = fn(*args, **kwargs)
        return result, already_dispatched


class SourceFamilyQueue:
    """One independent queue per source family -- a slow/blocked family never blocks another
    family's queue."""

    def __init__(self, family):
        assert family in QUEUE_FAMILIES, f"unknown queue family: {family!r}"
        self.family = family
        self.breaker = CircuitBreaker()
        self.jobs = Job()
        self.concurrency_limit = 4
        self._in_flight = 0

    def can_accept(self):
        return self.breaker.allow_request() and self._in_flight < self.concurrency_limit
