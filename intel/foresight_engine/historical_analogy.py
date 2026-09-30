# STAGE 7 PHASE M — Historical Analogy (Te spec section 19-22). Deterministic only: this
# module never invents a historical case. It first audits whether the corpus contains any
# evidence old enough to plausibly ground a historical comparison; if not, the honest result
# is HISTORICAL_EVIDENCE_GAP, per Te's explicit instruction in the section 22 directive.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from foresight_schema import new_historical_analogy_shell, validate_analogy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"

# A document must be at least this many days older than the newest document in the corpus to
# even count as "historical" background for an analogy. This is a conservative, documented
# threshold - not tuned to force a non-gap result.
HISTORICAL_AGE_DAYS = 365


def _load_documents(documents=None):
    if documents is not None:
        return documents
    if not DOCUMENTS_PATH.exists():
        return {}
    return json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))


def _parse_date(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def audit_historical_evidence(documents=None):
    """Returns whether the corpus has ANY document old enough to ground a real historical
    analogy, plus the concrete age spread found. This is the honest gap-detection Te's spec
    section 22 asks for, run BEFORE any analogy is ever built."""
    documents = _load_documents(documents)
    dates = [d for d in (_parse_date(doc.get("published", "")) for doc in documents.values())
             if d is not None]
    if not dates:
        return {"has_historical_evidence": False, "oldest_document_age_days": None,
                "documents_with_dates": 0}
    newest = max(dates)
    oldest = min(dates)
    age_days = (newest - oldest).days
    return {
        "has_historical_evidence": age_days >= HISTORICAL_AGE_DAYS,
        "oldest_document_age_days": age_days,
        "documents_with_dates": len(dates),
    }


def _analogy_id(topic):
    return "analogy_" + hashlib.sha1(topic.encode("utf-8")).hexdigest()[:16]


def build_historical_analogy(topic, historical_case=None, similarities=None, differences=None,
                              evidence_document_ids=None, documents=None):
    """Builds a historical analogy candidate for `topic`. If the corpus audit shows no real
    historical evidence, or the caller supplies no historical_case/differences, this returns a
    HISTORICAL_EVIDENCE_GAP / ANALOGY_REJECTED_INCOMPLETE record - never a fabricated analogy.
    This module supplies no historical_case data itself (that is a human/analyst input, per
    Te's no-fabrication rule); it only validates and gates."""
    audit = audit_historical_evidence(documents)
    shell = new_historical_analogy_shell(
        _analogy_id(topic), topic, historical_case=historical_case,
        similarities=similarities, differences=differences,
        evidence_document_ids=evidence_document_ids,
    )
    if not audit["has_historical_evidence"]:
        shell["status"] = "HISTORICAL_EVIDENCE_GAP"
        shell["gap_reason"] = (
            f"corpus spans only {audit['oldest_document_age_days']} days across "
            f"{audit['documents_with_dates']} dated documents - insufficient historical depth"
            if audit["documents_with_dates"] else "no dated documents found in corpus"
        )
        return shell
    return validate_analogy(shell)
