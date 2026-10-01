# M.6 -- minimal Hypothesis model. A Hypothesis is NOT a single stored explanation: it carries
# supporting/contradicting evidence and alternative explanations as separate arrays, and its
# status is only ever one of HYPOTHESIS_STATUSES, set deterministically from those arrays --
# never asserted directly by a caller or an LLM.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HYPOTHESES_PATH = HERE / "hypotheses.json"

HYPOTHESIS_STATUSES = (
    "OPEN", "SUPPORTED", "PARTIALLY_SUPPORTED", "CONTESTED", "WEAKENED",
    "INSUFFICIENT_EVIDENCE", "REJECTED",
)


def _hypothesis_id(topic, statement):
    return f"hyp_{hashlib.sha256(f'{topic}|{statement}'.encode()).hexdigest()[:16]}"


def new_hypothesis(topic, statement, scope=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "hypothesis_id": _hypothesis_id(topic, statement), "topic": topic, "statement": statement,
        "scope": scope, "supporting_evidence": [], "contradicting_evidence": [],
        "alternative_explanations": [], "status": "OPEN", "uncertainty": [],
        "last_updated": now,
    }


def classify_status(supporting_evidence, contradicting_evidence):
    """Deterministic, never an LLM judgment. No evidence at all -> INSUFFICIENT_EVIDENCE (never
    OPEN once evaluated -- OPEN is only the initial pre-evaluation state)."""
    if not supporting_evidence and not contradicting_evidence:
        return "INSUFFICIENT_EVIDENCE"
    if supporting_evidence and not contradicting_evidence:
        return "SUPPORTED"
    if contradicting_evidence and not supporting_evidence:
        return "REJECTED"
    if len(supporting_evidence) > len(contradicting_evidence):
        return "PARTIALLY_SUPPORTED"
    if len(contradicting_evidence) > len(supporting_evidence):
        return "WEAKENED"
    return "CONTESTED"


def _load():
    return json.loads(HYPOTHESES_PATH.read_text(encoding="utf-8")) if HYPOTHESES_PATH.exists() else {}


def _save(data):
    HYPOTHESES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_hypothesis(hyp, new_counterevidence_id=None, new_support_id=None, new_alternative=None):
    """The ONLY function permitted to write hypotheses.json. Appends evidence rather than
    overwriting (counterevidence is never deleted or averaged away), recomputes status
    deterministically, and re-stamps last_updated."""
    hyps = _load()
    if new_counterevidence_id and new_counterevidence_id not in hyp["contradicting_evidence"]:
        hyp["contradicting_evidence"].append(new_counterevidence_id)
    if new_support_id and new_support_id not in hyp["supporting_evidence"]:
        hyp["supporting_evidence"].append(new_support_id)
    if new_alternative and new_alternative not in hyp["alternative_explanations"]:
        hyp["alternative_explanations"].append(new_alternative)
    hyp["status"] = classify_status(hyp["supporting_evidence"], hyp["contradicting_evidence"])
    hyp["last_updated"] = datetime.now(timezone.utc).isoformat()
    hyps[hyp["hypothesis_id"]] = hyp
    _save(hyps)
    return hyp


def load_hypotheses():
    return _load()
