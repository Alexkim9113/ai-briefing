import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import queue_model as m  # noqa: E402


def test_circuit_opens_after_threshold_failures():
    clock = [0.0]
    cb = m.CircuitBreaker(failure_threshold=3, cooldown_seconds=60, clock=lambda: clock[0])
    for _ in range(3):
        cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False


def test_circuit_half_opens_after_cooldown():
    clock = [0.0]
    cb = m.CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=lambda: clock[0])
    cb.record_failure()
    assert cb.state == "OPEN"
    clock[0] = 11.0
    assert cb.allow_request() is True
    assert cb.state == "HALF_OPEN"


def test_retry_backoff_stops_at_max_retries():
    delays = [m.retry_with_backoff(i, base_seconds=1, max_retries=4) for i in range(6)]
    assert delays[:4] == [1, 2, 4, 8]
    assert delays[4] is None and delays[5] is None, "must never retry forever"


def test_job_dispatch_is_idempotent_flagged():
    job = m.Job()
    calls = []
    fn = lambda: calls.append(1) or len(calls)
    r1, was_dup1 = job.dispatch("job-1", fn)
    r2, was_dup2 = job.dispatch("job-1", fn)
    assert was_dup1 is False
    assert was_dup2 is True


def test_unknown_queue_family_rejected():
    try:
        m.SourceFamilyQueue("NOT_A_FAMILY")
        assert False
    except AssertionError:
        pass


def test_queue_families_are_independent_instances():
    q1 = m.SourceFamilyQueue("NEWS_QUEUE")
    q2 = m.SourceFamilyQueue("RESEARCH_QUEUE")
    for _ in range(5):
        q1.breaker.record_failure()
    assert q1.breaker.state == "OPEN"
    assert q2.breaker.state == "CLOSED", "one family's failures must never affect another's queue"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
