# PHASE M.5E -- first slice, item 1: legacy corpus audit (READ-ONLY).
#
# Scans the real 577-document canonical corpus (intel/documents.json) and scores every
# document against the M.5E priority criteria for enrichment:
#   - repeated events across articles (near-duplicate title clusters covering the same event)
#   - policy/regulatory changes (document_type == POLICY)
#   - major tech releases (keyword match: launch/release/unveil/...)
#   - labor market shifts (keyword match + field == 사회·노동)
#   - large investment/industry changes (keyword match: billion/investment/funding/buyback/...)
#   - high social impact (keyword match: lawsuit/ban/regulation/protest/...)
#   - high longitudinal-tracking value (documents that are both policy-flagged AND part of a
#     repeated-event cluster -- the two signals most likely to recur over time)
#
# This module NEVER writes intel/documents.json (read-only), and never fabricates a score
# component it cannot compute from real fields already on the document (title/document_type/
# field/source_id/canonical_url/published). It writes only its own sidecar report:
# intel/legacy_enrichment/priority_candidates.json.
#
# Near-duplicate clustering (the "repeated events" signal) is intentionally simple and
# deterministic -- normalized-title token-overlap (Jaccard) above a threshold -- not an LLM
# call and not a new dedup framework: intel/event_matching/ already does real event-merge
# clustering for the pipeline's own EVENT layer, but this module only needs a coarse "does
# this title recur across N other documents" signal for prioritization, so it computes its
# own lightweight overlap here rather than importing/duplicating the full event-matching
# pipeline (which requires additional per-run state this read-only audit does not have).
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "priority_candidates.json"

TOP_N = 20

_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is", "are", "with",
    "at", "by", "as", "its", "it", "this", "that", "new", "says", "how", "why", "what",
}

_TOKEN_RE = re.compile(r"[a-z0-9가-힣]+")


def _tokens(title):
    if not title:
        return set()
    return {t for t in _TOKEN_RE.findall(title.lower()) if t not in _STOPWORDS and len(t) > 2}


# Keyword sets per criterion. All are literal, human-reviewable term lists -- no LLM, no
# fuzzy semantic matching.
_TECH_RELEASE_KEYWORDS = (
    "launch", "launches", "launched", "release", "released", "unveil", "unveils",
    "unveiled", "debut", "announces", "announced", "rollout", "ships", "출시", "공개",
)
_LABOR_KEYWORDS = (
    "job", "jobs", "layoff", "layoffs", "hiring", "workforce", "union", "worker",
    "workers", "employment", "노동", "일자리", "해고", "고용",
)
_INVESTMENT_KEYWORDS = (
    "billion", "million", "invest", "investment", "funding", "buyback", "valuation",
    "ipo", "acquisition", "acquires", "merger", "투자", "인수", "억원", "조원",
)
_SOCIAL_IMPACT_KEYWORDS = (
    "lawsuit", "sue", "sues", "ban", "banned", "regulation", "regulator", "protest",
    "privacy", "bias", "discrimination", "safety", "risk", "제재", "규제", "소송",
)


def _load_documents():
    data = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in data if isinstance(d, dict) and "document_id" in d}


def _keyword_hits(title_lower, keywords):
    """Word-boundary match only -- a plain substring check would false-positive on e.g. "sues"
    matching inside "issues". Korean keywords have no word-boundary concept in \\b (non-ASCII),
    so they fall back to substring match, which is acceptable for short, specific Korean terms
    (규제/소송/etc. are not common substrings of unrelated words)."""
    hits = []
    for kw in keywords:
        if re.search(r"[a-z0-9]", kw):
            if re.search(r"\b" + re.escape(kw) + r"\b", title_lower):
                hits.append(kw)
        elif kw in title_lower:
            hits.append(kw)
    return hits


def build_title_clusters(documents, jaccard_threshold=0.5, min_cluster_size=2):
    """Groups document_ids whose normalized titles overlap heavily (repeated-event proxy).
    O(n^2) token-set comparison -- fine for a 577-document, one-off audit script; not intended
    to run per-request. Returns {document_id: cluster_size} for every doc in a qualifying
    cluster (size >= min_cluster_size); docs with no cluster are simply absent (cluster size 1
    implied)."""
    ids = list(documents.keys())
    tok = {did: _tokens(documents[did].get("title")) for did in ids}
    parent = {did: did for did in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    n = len(ids)
    for i in range(n):
        ti = tok[ids[i]]
        if not ti:
            continue
        for j in range(i + 1, n):
            tj = tok[ids[j]]
            if not tj:
                continue
            union_size = len(ti | tj)
            if union_size == 0:
                continue
            jaccard = len(ti & tj) / union_size
            if jaccard >= jaccard_threshold:
                union(ids[i], ids[j])

    groups = Counter(find(did) for did in ids)
    cluster_size = {did: groups[find(did)] for did in ids}
    return {did: size for did, size in cluster_size.items() if size >= min_cluster_size}


def score_document(doc, cluster_size):
    """Returns (score, reasons: [str]) -- every point on the score is traceable to one named
    criterion, so nothing here is an opaque black-box number."""
    reasons = []
    score = 0
    title = doc.get("title") or ""
    title_lower = title.lower()
    doc_type = doc.get("document_type")
    field = doc.get("field")

    if cluster_size and cluster_size >= 2:
        pts = min(cluster_size, 5)
        score += pts
        reasons.append(f"REPEATED_EVENT: title recurs across {cluster_size} corpus documents (+{pts})")

    if doc_type == "POLICY":
        score += 4
        reasons.append("POLICY_REGULATORY: document_type == POLICY (+4)")

    tech_hits = _keyword_hits(title_lower, _TECH_RELEASE_KEYWORDS)
    if tech_hits:
        score += 2
        reasons.append(f"TECH_RELEASE: title matches {tech_hits} (+2)")

    labor_hits = _keyword_hits(title_lower, _LABOR_KEYWORDS)
    labor_field = field == "사회·노동"
    if labor_hits or labor_field:
        score += 3
        basis = (labor_hits or []) + (["field=사회·노동"] if labor_field else [])
        reasons.append(f"LABOR_MARKET_SHIFT: {basis} (+3)")

    invest_hits = _keyword_hits(title_lower, _INVESTMENT_KEYWORDS)
    if invest_hits:
        score += 3
        reasons.append(f"LARGE_INVESTMENT: title matches {invest_hits} (+3)")

    social_hits = _keyword_hits(title_lower, _SOCIAL_IMPACT_KEYWORDS)
    if social_hits:
        score += 3
        reasons.append(f"HIGH_SOCIAL_IMPACT: title matches {social_hits} (+3)")

    if doc_type == "POLICY" and cluster_size and cluster_size >= 2:
        score += 2
        reasons.append("LONGITUDINAL_TRACKING_VALUE: policy document that is also part of a "
                        "repeated-event cluster -- likely to recur/update over time (+2)")

    return score, reasons


def audit_corpus(documents=None, top_n=TOP_N):
    documents = documents if documents is not None else _load_documents()
    clusters = build_title_clusters(documents)

    scored = []
    for did, doc in documents.items():
        cluster_size = clusters.get(did, 1)
        score, reasons = score_document(doc, cluster_size)
        if score <= 0:
            continue
        scored.append({
            "document_id": did,
            "score": score,
            "reasons": reasons,
            "title": doc.get("title"),
            "document_type": doc.get("document_type"),
            "source_id": doc.get("source_id"),
            "canonical_url": doc.get("canonical_url"),
            "published": doc.get("published"),
            "cluster_size": cluster_size,
        })

    scored.sort(key=lambda x: (-x["score"], x["document_id"]))
    candidates = scored[:top_n]

    return {
        "documents_examined": len(documents),
        "documents_with_nonzero_score": len(scored),
        "top_n_requested": top_n,
        "candidates_returned": len(candidates),
        "candidates": candidates,
    }


def main():
    report = audit_corpus()
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {report['candidates_returned']} candidates "
          f"out of {report['documents_examined']} documents examined "
          f"({report['documents_with_nonzero_score']} scored > 0)")


if __name__ == "__main__":
    main()
