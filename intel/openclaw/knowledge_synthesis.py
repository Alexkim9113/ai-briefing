# O-4B — KNOWLEDGE SYNTHESIS: domain/topic structuring, entity tags, event-level dedup,
# canonical-URL resolution attempts, and Korean synthesis (ko_title/ko_summary/why_it_matters).
# Operator-only. Reads/writes ONLY intel/openclaw/discoveries.json. Never imports or touches
# briefing.py, root sources.json, or anything under site/ -- same isolation contract as
# collector.py and relevance_gate.py.
#
# KOREAN SYNTHESIS -- FREE-FIRST RULE (client directive section 7): no new paid Search API is
# ever connected here (PAID SEARCH API stays 0). For ko_title/ko_summary/why_it_matters, this
# module reuses the GEMINI_KEY secret already registered in .github/workflows/daily.yml and
# already used by intel/evidence_supply (via intel/evidence_pipeline/gemini_extract.py's
# generativelanguage.googleapis.com call) -- the same approved, free-tier key, not a new paid
# API. If GEMINI_KEY is absent, or the call fails for any reason (including: this authoring
# sandbox has no outbound network to new hosts at all), ko_title/ko_summary/why_it_matters stay
# null and the document's status is PENDING_KOREAN_SYNTHESIS -- never a rule-based translation
# dressed up as if it were AI-written (explicitly forbidden).

import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import relevance_gate as rg  # noqa: E402

GEMINI_MODEL = os.environ.get("MX_MODEL", "gemini-flash-latest")
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


# ---------------------------------------------------------------------------
# 8. Primary/secondary domain + topics -- dynamic, keyword-driven, never a forced fixed slot.
# ---------------------------------------------------------------------------

# Each domain maps to patterns that, if found in title+description, vote for that domain.
# Order matters only as a tie-break (first match wins ties) -- otherwise all matching domains
# are collected and the one with the most/strongest hits becomes primary_domain, the rest
# become secondary_domains (directive section 8).
_DOMAIN_PATTERNS = {
    "저작권·지식재산": [r"copyright", r"intellectual property", "저작권", "지식재산", "版权", "著作权", "侵权"],
    "법·제도": [r"\bcourt\b", r"\bruling\b", r"\blawsuit\b", "판결", "소송", "법원", "案", "审理", r"guidelines?", r"regulation"],
    "정책·행정": [r"\bpolicy\b", r"\bconsultation\b", r"\bproposal\b", "정책", "의견수렴", "제안", "国家", "十五五", r"\back\b", r"\bact\b"],
    "모델·서비스": [r"large language model", r"\bllm\b", r"foundation model", "大模型", "모델", r"\bchatgpt\b", r"\bgemini\b", r"\bclaude\b"],
    "에이전트": [r"\bagent", "에이전트", "智能体"],
    "반도체·컴퓨팅": [r"\bchip\b", r"\bgpu\b", r"semiconductor", "반도체", "芯片"],
    "데이터센터": [r"data cent(er|re)", "데이터센터"],
    "산업·경제": [r"\binvest(ment)?\b", r"\bfund(ing)?\b", r"\bmillion\b", r"收费", r"分钱", "산업", "경제", "투자"],
    "국방·안보": [r"\bdefense\b", r"\bsecurity\b", r"\bmilitary\b", "국방", "안보", r"nuclear"],
    "사이버보안": [r"cybersecurity", "사이버보안"],
    "의료·헬스케어": [r"\bhealthcare?\b", r"\bmedical\b", "의료", "헬스케어"],
    "교육": [r"\beducation\b", "교육"],
    "안전·평가": [r"\bsafety\b", r"\bevaluation\b", "안전", "평가"],
    "사회": [r"\bchildren\b", r"\bsocial media\b", "아동", "사회", "플랫폼"],
    "문화·예술": [r"\bdrama\b", r"\bcreativ\w*\b", "창작", "연극", "剧", "예술"],
    "국제질서·지정학": [r"\bsummit\b", r"\binternational\b", "국제", "峰会"],
}

_TOPIC_PATTERNS = {
    "AI생성물": [r"generative ai", "生成式", "AI剧", "생성형"],
    "AI 학습데이터": [r"\btraining\b", "训练", "학습데이터"],
    "판결": [r"\bruling\b", r"\blawsuit\b", "판결", "案", "审理", "侵权"],
    "정책": [r"\bpolicy\b", r"\bconsultation\b", "정책", "규칙", "起草"],
    "저작권침해": ["侵权", r"infringement"],
    "AI규제": [r"\bregulation\b", r"\back\b", "규제", "법안"],
    "컨퍼런스": [r"\bsummit\b", r"\bconference\b", "峰会", "컨퍼런스"],
    "아동보호": [r"\bchildren\b", "아동"],
    "디지털신원": [r"\bidentity\b", r"\baccess token", "신원", "토큰"],
}

_ENTITY_PATTERNS = {
    "NIST": [r"\bNIST\b"],
    "European Commission": [r"European Commission"],
    "국가판권국(国家版权局)": ["国家版权局"],
    "상하이 법원": ["上海"],
    "후베이": ["湖北"],
}


def _hits(text, pattern_map):
    text = text or ""
    scored = {}
    for label, patterns in pattern_map.items():
        n = 0
        for p in patterns:
            try:
                if re.search(p, text, re.IGNORECASE):
                    n += 1
            except re.error:
                if p in text:
                    n += 1
        if n:
            scored[label] = n
    return scored


def assign_domains_and_topics(original_title, raw_description=""):
    text = f"{original_title or ''} {raw_description or ''}"
    domain_scores = _hits(text, _DOMAIN_PATTERNS)
    if not domain_scores:
        return {"primary_domain": "기타", "secondary_domains": [], "topics": [], "entities": []}
    # Tie-break order: when two domains score equally, prefer the one whose pattern list is
    # defined first in _DOMAIN_PATTERNS (an explicit editorial priority -- e.g. "저작권·지식재산"
    # before the more generic "문화·예술" -- rather than an arbitrary alphabetical sort).
    priority = {name: i for i, name in enumerate(_DOMAIN_PATTERNS)}
    ranked = sorted(domain_scores.items(), key=lambda kv: (-kv[1], priority.get(kv[0], 999)))
    primary = ranked[0][0]
    secondary = [d for d, _ in ranked[1:4]]  # cap secondary list, directive just says "structure"
    topics = sorted(_hits(text, _TOPIC_PATTERNS).keys())
    entities = sorted(_hits(text, _ENTITY_PATTERNS).keys())
    return {"primary_domain": primary, "secondary_domains": secondary, "topics": topics, "entities": entities}


# ---------------------------------------------------------------------------
# 10. DOCUMENT -> EVENT dedup. Every original item is preserved as a DOCUMENT; items that are
# really reports of the SAME real-world event (same region, near-identical normalized title)
# are grouped under one EVENT id. URL difference alone is never grounds to treat two documents
# as different events, but title similarity must be genuinely high (not just "same topic") --
# otherwise distinct CN court cases/policy items would be wrongly merged, which the quality bar
# explicitly forbids.
# ---------------------------------------------------------------------------

_STOPWORDS_RE = re.compile(r"[\s\-–—:·,.'\"“”‘’()\[\]|/]+")


def _normalize_title(title):
    t = (title or "").lower()
    t = _STOPWORDS_RE.sub(" ", t).strip()
    return t


def group_into_events(documents):
    """documents: list of item dicts (already carrying 'id', 'source_region', 'original_title').
    Returns list of {event_id, region, document_ids, representative_document_id}."""
    by_region = {}
    for d in documents:
        by_region.setdefault(d.get("source_region", "UNKNOWN"), []).append(d)

    events = []
    for region, docs in by_region.items():
        assigned = set()
        for i, d in enumerate(docs):
            if d["id"] in assigned:
                continue
            norm_i = _normalize_title(d["original_title"])
            group = [d]
            assigned.add(d["id"])
            for j in range(i + 1, len(docs)):
                other = docs[j]
                if other["id"] in assigned:
                    continue
                norm_j = _normalize_title(other["original_title"])
                ratio = difflib.SequenceMatcher(None, norm_i, norm_j).ratio()
                # High bar on purpose: only near-identical titles (the same wire story picked up
                # by two feeds, or an RSS title re-published with a trivial prefix) count as the
                # same event. Two different CN court cases or two different EU items about
                # different acts must NOT merge just for sharing "copyright" or "AI".
                if ratio >= 0.86:
                    group.append(other)
                    assigned.add(other["id"])
            event_id = f"evt_{group[0]['id']}"
            events.append({
                "event_id": event_id,
                "region": region,
                "document_ids": [g["id"] for g in group],
                "representative_document_id": group[0]["id"],
            })
    return events


# ---------------------------------------------------------------------------
# 11. Canonical URL resolution attempt. Google News search-result links are a discovery path,
# not the final source (directive section 11) -- this tries a real HEAD/GET to follow redirects
# to the publisher's own URL. It NEVER fabricates a resolved URL: on any failure (including the
# network-policy block this authoring sandbox always hits) it honestly reports
# CANONICAL_NOT_RESOLVED and keeps the original canonical_url untouched.
# ---------------------------------------------------------------------------

def resolve_canonical_url(url, timeout=8):
    if not url:
        return {"status": "CANONICAL_NOT_RESOLVED", "resolved_url": None}
    if "news.google.com" not in url:
        # Already a direct publisher/government/court URL -- nothing to resolve.
        return {"status": "ALREADY_CANONICAL", "resolved_url": url}
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "METAXIS-OpenClaw/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            if final_url and final_url != url:
                return {"status": "RESOLVED", "resolved_url": final_url}
            return {"status": "CANONICAL_NOT_RESOLVED", "resolved_url": None}
    except Exception:  # noqa: BLE001 -- any failure (incl. sandbox network policy) is honest, not fatal
        return {"status": "CANONICAL_NOT_RESOLVED", "resolved_url": None}


# ---------------------------------------------------------------------------
# 7. Korean synthesis via the already-approved GEMINI_KEY (free tier, reused -- not a new paid
# API). Separate prompt/contract from intel/evidence_pipeline/gemini_extract.py (that module
# extracts Claim candidates; this one writes ko_title/ko_summary/why_it_matters), but the same
# call shape (GEMINI_KEY env var, generativelanguage.googleapis.com, JSON-only response).
# ---------------------------------------------------------------------------

_KO_PROMPT = """다음은 해외 뉴스/공식 발표의 원문 제목과 설명이다. 아래 JSON 스키마로만 한국어로 답하라.

절대 규칙:
- 원문에 없는 사실을 추가하거나 과장하지 않는다 (예: 원문이 "의견수렴 착수"라고만 했다면 "전면
  개정 추진"이라고 쓰지 않는다).
- ko_title은 직역이 아니라 자연스러운 한국어 제목으로 쓰되 원문의 사실 범위를 넘지 않는다.
- ko_summary는 3~5문장으로 "무엇이 있었는가/누가 무엇을 했는가/무엇이 새롭거나 중요한가"에
  답한다. 전문 번역/복제 금지.
- why_it_matters는 ko_summary와 별도로 1~3문장, 구조적 의미를 설명하되 근거 없는 과잉 해석을
  하지 않는다 (판결 1건으로 "국가 전체 법리가 바뀌었다"고 쓰지 않는다).

원문 제목: {title}
원문 설명: {description}

JSON 스키마: {{"ko_title":"", "ko_summary":"", "why_it_matters":""}}
JSON만 출력하라."""


def gemini_available():
    return bool(os.environ.get("GEMINI_KEY", "").strip())


def call_gemini_korean_synthesis(title, description, timeout=20):
    """Real API call, reusing GEMINI_KEY. Returns dict or None -- NEVER raises, NEVER guesses.
    A None here means the caller must leave ko_title/ko_summary/why_it_matters as null and mark
    the document PENDING_KOREAN_SYNTHESIS; it must never fall back to a rule-based translation
    presented as if it were this function's output (directive section 7, explicitly forbidden)."""
    if not gemini_available():
        return None
    key = os.environ["GEMINI_KEY"].strip()
    prompt = _KO_PROMPT.format(title=title or "", description=description or "")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode("utf-8")
    req = urllib.request.Request(
        _GEMINI_ENDPOINT.format(model=GEMINI_MODEL) + f"?key={key}", body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        out = {k: (data.get(k) or None) for k in ("ko_title", "ko_summary", "why_it_matters")}
        if not out["ko_title"] or not out["ko_summary"]:
            return None
        return out
    except Exception:  # noqa: BLE001 -- network/parse/quota failure: honest None, never fabricated
        return None


# ---------------------------------------------------------------------------
# Orchestration: process_discoveries() is the one entrypoint synthesize.py calls. It mutates a
# loaded discoveries.json dict IN PLACE (adding new fields, never removing original_title/
# canonical_url/etc. -- directive section 3) and returns it plus a summary of what happened.
# ---------------------------------------------------------------------------

def process_discoveries(data, call_gemini=True):
    all_docs = []
    for region, items in data.get("regions", {}).items():
        for item in items:
            item["source_region"] = item.get("source_region", region)
            all_docs.append(item)

    relevance_counts = {"PASS": 0, "NEEDS_REVIEW": 0, "FAIL": 0}
    canonical_counts = {"RESOLVED": 0, "ALREADY_CANONICAL": 0, "CANONICAL_NOT_RESOLVED": 0}
    gemini_calls, gemini_successes = 0, 0

    for item in all_docs:
        title = item.get("original_title", "")
        desc = item.get("raw_description", "")

        verdict = rg.classify(title, desc)
        item["ai_relevance"] = verdict
        relevance_counts[verdict["status"]] += 1
        item["source_tier"] = rg.source_tier(item.get("source_type"))

        dom = assign_domains_and_topics(title, desc)
        item["primary_domain"] = dom["primary_domain"]
        item["secondary_domains"] = dom["secondary_domains"]
        item["topics"] = dom["topics"]
        item["entities"] = dom["entities"]

        canon = resolve_canonical_url(item.get("canonical_url"))
        item["canonical_resolution"] = canon
        canonical_counts[canon["status"]] += 1

        # Korean synthesis is attempted only for PASS/NEEDS_REVIEW (directive section 16: FAIL
        # stays in the data but is not the default surfaced content, so spending a Gemini call
        # on it brings no Operator value and would just burn free-tier budget for nothing).
        item.setdefault("ko_title", None)
        item.setdefault("ko_summary", None)
        item.setdefault("why_it_matters", None)
        if verdict["status"] in ("PASS", "NEEDS_REVIEW"):
            result = None
            if call_gemini:
                gemini_calls += 1
                result = call_gemini_korean_synthesis(title, desc)
            if result:
                gemini_successes += 1
                item["ko_title"] = result["ko_title"]
                item["ko_summary"] = result["ko_summary"]
                item["why_it_matters"] = result["why_it_matters"]
                item["status"] = "KO_SYNTHESIZED"
            else:
                item["status"] = "PENDING_KOREAN_SYNTHESIS"
        else:
            item["status"] = "NOT_SYNTHESIZED_FAIL_GATE"

    events = group_into_events(all_docs)

    data["ai_relevance_counts"] = relevance_counts
    data["canonical_resolution_counts"] = canonical_counts
    data["events"] = events
    data["structured_document_count"] = len(all_docs)
    data["korean_synthesis"] = {
        "gemini_key_present": gemini_available(),
        "calls_attempted": gemini_calls,
        "calls_succeeded": gemini_successes,
    }
    data["knowledge_synthesis_version"] = "O-4B"
    return data


def main():
    out_path = HERE / "discoveries.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    process_discoveries(data, call_gemini=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data.get("ai_relevance_counts", {}), ensure_ascii=False))


if __name__ == "__main__":
    main()
