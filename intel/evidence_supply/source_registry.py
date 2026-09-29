# PRODUCTION EVIDENCE SUPPLY v1.0 — SUBSTEP C (섹션 15-16). Source Registry sidecar:
# 실제 발행사/기관 정체성을 source_id로 정리한다. 기존 intel/sources.json 구조를 건드리지
# 않고(섹션 69: sidecar 패턴) 별도 파일(source_registry.json)에 저장한다.
#
# 절대 규칙(섹션 16): 이름이 비슷하다는 이유만으로 자동 병합하지 않는다 — 병합 근거
# (basis)를 EXACT/DOMAIN_VERIFIED/KNOWN_ALIAS/HUMAN_CONFIRMED 중 하나로 반드시 남긴다.
# "SEARCH BROAD, REGISTRY STRICT"(섹션 41) — 공식처럼 보인다고 레지스트리에 넣지 않는다.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "source_registry.json"

SOURCE_TYPES = (
    "GOVERNMENT", "COURT", "LEGISLATURE", "REGULATOR", "INTERNATIONAL_ORGANIZATION",
    "UNIVERSITY", "RESEARCH_INSTITUTE", "JOURNAL", "COMPANY", "WIRE", "MEDIA",
    "SPECIALIST_MEDIA", "REPUBLISHER", "DISCOVERY_PLATFORM",
)
ALIAS_BASIS_VALUES = ("EXACT", "DOMAIN_VERIFIED", "KNOWN_ALIAS", "HUMAN_CONFIRMED")

# 이 세션에서 실제로 확인 가능한 것만 시드로 넣는다: intel/documents.json 실제 corpus에서
# 관찰된 도메인 중, 도메인 자체가 발행사 정체성을 명확히 드러내는 것만(섹션 42: 기존
# 수집에서 반복적으로 등장하는 기관부터 점진적으로 확장 — 전 세계 정부를 미리 나열하지
# 않는다). GOOGLE_NEWS/arXiv 두 건은 이미 코드에서 특별 취급되므로 최소 필요한 것만 시드.
_SEED_SOURCES = (
    {"source_id": "src_google_news", "canonical_name": "Google News", "domain": "news.google.com",
     "source_type": "DISCOVERY_PLATFORM", "official_status": None},
    {"source_id": "src_arxiv", "canonical_name": "arXiv", "domain": "arxiv.org",
     "source_type": "RESEARCH_INSTITUTE", "official_status": "OFFICIAL"},
)


def _load(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def load_registry():
    reg = _load(REGISTRY_PATH, {"sources": {}, "aliases": []})
    if "sources" not in reg:
        reg["sources"] = {}
    if "aliases" not in reg:
        reg["aliases"] = []
    return reg


def seed_registry_if_empty():
    """레지스트리가 비어 있을 때만 최소 시드를 채운다. 이미 내용이 있으면 절대 덮어쓰지
    않는다(사람이 이미 확인/추가한 항목을 잃지 않기 위해)."""
    reg = load_registry()
    if reg["sources"]:
        return reg, False
    for s in _SEED_SOURCES:
        rec = dict(s)
        assert rec["source_type"] in SOURCE_TYPES
        reg["sources"][rec["source_id"]] = rec
    _save(REGISTRY_PATH, reg)
    return reg, True


def register_source(source_id, canonical_name, domain, source_type, official_status=None,
                     country=None, institution_type=None, parent_organization=None):
    """새 source를 명시적으로 등록한다(호출자가 실제로 확인한 경우에만 호출해야 한다 —
    이 함수 자체는 아무것도 추측하지 않고 주어진 값만 저장한다)."""
    assert source_type in SOURCE_TYPES, f"unknown source_type: {source_type}"
    reg = load_registry()
    reg["sources"][source_id] = {
        "source_id": source_id,
        "canonical_name": canonical_name,
        "domain": domain,
        "source_type": source_type,
        "official_status": official_status,
        "country": country,
        "institution_type": institution_type,
        "parent_organization": parent_organization,
        "aliases": [],
        "known_domains": [domain] if domain else [],
    }
    _save(REGISTRY_PATH, reg)
    return reg["sources"][source_id]


def resolve_alias(name_or_domain, target_source_id, basis, evidence=None):
    """name_or_domain이 target_source_id의 별칭임을 기록한다. basis는 반드시
    ALIAS_BASIS_VALUES 중 하나여야 하고, 근거(evidence)를 함께 남긴다 — 이름이
    비슷해 보인다는 것만으로는 EXACT/DOMAIN_VERIFIED 등 어떤 basis도 성립하지 않는다."""
    assert basis in ALIAS_BASIS_VALUES, f"unknown alias basis: {basis}"
    reg = load_registry()
    if target_source_id not in reg["sources"]:
        raise ValueError(f"unknown target_source_id: {target_source_id}")
    entry = {
        "alias": name_or_domain,
        "target_source_id": target_source_id,
        "basis": basis,
        "evidence": evidence,
    }
    reg["aliases"].append(entry)
    _save(REGISTRY_PATH, reg)
    return entry


def lookup_by_domain(domain, registry=None):
    """도메인으로 등록된 source를 찾는다 — 별칭이 아니라 known_domains에 정확히 일치할
    때만 반환한다(퍼지 매칭 없음)."""
    reg = registry or load_registry()
    if not domain:
        return None
    domain = domain.lower().lstrip("www.")
    for rec in reg["sources"].values():
        known = [d.lower().lstrip("www.") for d in (rec.get("known_domains") or [])]
        if rec.get("domain", "").lower().lstrip("www.") == domain or domain in known:
            return rec
    return None
