# PUBLICATION GATE — Shadow/Dry-run only. 아직 어디에서도 import되지 않는다.
# INTERNAL DOCUMENT(intel/documents.json + data/*.json 원본 필드) → 이 Gate → PUBLIC PAYLOAD 후보.
# 기존 site/, briefing.py Public Renderer, search.json은 절대 읽거나 쓰지 않는다(운영자 지시 21).
#
# 핵심 원칙(운영자 지시 20, Fail Closed): rights_mode가 비어있거나 판단 중 오류가 나면
# 무조건 LINK_ONLY로 떨어뜨린다. "권리 불명 → 전체 허용"은 이 모듈에서 절대 만들지 않는다.
#
# Rights Mode 승격(운영자 지시 18)은 이 모듈이 스스로 판단하지 않는다 — 오직 이미 저장된
# document_type/source_type/rights_mode 메타데이터, 그리고 아래 명시된 소수의 "명확한 규칙"만 쓴다.
# Gemini/Claude 등 어떤 AI도 이 결정에 관여하지 않는다(운영자 지시 22: 비용 0).

RIGHTS_DECISIONS = ("LINK_ONLY", "METAXIS_ORIGINAL", "LICENSED", "OPEN_LICENSE",
                     "PUBLIC_DOMAIN", "GOV_OFFICIAL", "MANUAL_REVIEW")

# LINK_ONLY 문서의 공통 허용/차단 필드(운영자 지시 5번)
_LINK_ONLY_ALLOWED = ["document_id", "title", "source", "published", "original_url",
                      "category", "canonical_topics", "document_type", "rights_mode"]
_LINK_ONLY_BLOCKED = ["summary", "detail", "mx.b", "mx.p", "body", "excerpt", "translation",
                      "transcript", "external_image", "external_thumbnail", "long_quote"]

# METAXIS_ORIGINAL(에디터 글)은 우리가 직접 쓴 글이므로 본문 전체를 공개해도 된다.
_ORIGINAL_ALLOWED = ["document_id", "title", "source", "published", "canonical_topics",
                     "document_type", "rights_mode", "body", "cover"]
_ORIGINAL_BLOCKED = []  # METAXIS 저작물 자신이므로 차단할 "외부 저작물" 필드가 없음


def _fail_closed(document_id, reason):
    """rights_mode를 판단할 수 없거나 오류가 났을 때 항상 이리로 떨어진다(20번)."""
    return {
        "document_id": document_id, "rights_mode": "LINK_ONLY",
        "allowed_fields": list(_LINK_ONLY_ALLOWED), "blocked_fields": list(_LINK_ONLY_BLOCKED),
        "reason": reason,
    }


def decide_rights(document):
    """document(intel/documents.json 레코드)의 rights_mode를 보고 Public Payload에
    허용/차단할 필드를 정한다. 여기서 rights_mode 값 자체를 "새로 추정"하지 않는다 —
    이미 저장된 값만 읽는다(18번: AI가 rights_mode를 바꾸면 안 됨, 이 Gate도 마찬가지로
    스스로 승격하지 않고 저장된 값을 그대로 신뢰하되 모르면 안전 쪽으로 떨어뜨린다)."""
    try:
        did = document.get("document_id")
        if not did:
            return _fail_closed(document.get("document_id"), "MISSING_DOCUMENT_ID")

        rm = document.get("rights_mode")
        dtype = document.get("document_type")

        if rm == "METAXIS_ORIGINAL" or dtype == "EDITOR_ORIGINAL":
            # 에디터 글(METAXIS 자체 저작물)만 이 경로로 온다 — 외부 기사 요약을
            # METAXIS_ORIGINAL로 잘못 분류하는 사고를 막기 위해 document_type도 함께 확인(7번).
            return {
                "document_id": did, "rights_mode": "METAXIS_ORIGINAL",
                "allowed_fields": list(_ORIGINAL_ALLOWED), "blocked_fields": list(_ORIGINAL_BLOCKED),
                "reason": "METAXIS_OWN_CONTENT",
            }

        if rm in ("LICENSED", "OPEN_LICENSE", "PUBLIC_DOMAIN"):
            # 이번 단계는 License Resolver를 만들지 않는다(15번) — 이미 명시적으로 저장된
            # 값이 있을 때만 인정하고, 그 값이 없으면(현재 전부 없음) 절대 이 분기로 오지 않는다.
            return {
                "document_id": did, "rights_mode": rm,
                "allowed_fields": list(_LINK_ONLY_ALLOWED) + ["summary"],
                "blocked_fields": [f for f in _LINK_ONLY_BLOCKED if f != "summary"],
                "reason": f"EXPLICIT_{rm}_ON_RECORD",
            }

        if rm == "GOV_OFFICIAL":
            # 16번: 정부 소스라는 사실 자체가 자유이용을 뜻하지 않는다. GOV_OFFICIAL이어도
            # 공개 Payload는 LINK_ONLY와 동일하게 보수적으로 유지한다.
            return {
                "document_id": did, "rights_mode": "GOV_OFFICIAL",
                "allowed_fields": list(_LINK_ONLY_ALLOWED), "blocked_fields": list(_LINK_ONLY_BLOCKED),
                "reason": "GOV_SOURCE_BUT_TERMS_UNCONFIRMED",
            }

        if rm == "MANUAL_REVIEW":
            return _fail_closed(did, "MANUAL_REVIEW_PENDING")

        # rm이 없거나(LINK_ONLY 기본값) 알 수 없는 값이면 전부 LINK_ONLY(20번, 기본 Fail-safe)
        return {
            "document_id": did, "rights_mode": "LINK_ONLY",
            "allowed_fields": list(_LINK_ONLY_ALLOWED), "blocked_fields": list(_LINK_ONLY_BLOCKED),
            "reason": "RIGHTS_UNKNOWN" if not rm else f"DEFAULT_LINK_ONLY({rm})",
        }
    except Exception as exc:  # noqa: BLE001 — Gate 자체가 죽어도 반드시 LINK_ONLY로(20번)
        return _fail_closed(document.get("document_id") if isinstance(document, dict) else None,
                             f"GATE_ERROR:{type(exc).__name__}")


def external_image_allowed(rights_decision):
    """9번: 권리 미확인 외부 이미지는 LINK_ONLY Payload에서 제외."""
    return rights_decision["rights_mode"] in ("METAXIS_ORIGINAL", "LICENSED", "OPEN_LICENSE", "PUBLIC_DOMAIN")


def build_public_payload(document, raw_item, rights_decision):
    """실제 필드 값을 채워 Public Payload 하나를 만든다. allowed_fields에 없는 키는 절대 넣지 않는다."""
    allowed = set(rights_decision["allowed_fields"])
    src = {
        "document_id": document.get("document_id"),
        "title": document.get("title"),
        "source": raw_item.get("source") if raw_item else None,
        "published": document.get("published"),
        "original_url": document.get("canonical_url"),
        "category": document.get("category"),
        "canonical_topics": raw_item.get("mx", {}).get("t") if raw_item else None,
        "document_type": document.get("document_type"),
        "rights_mode": rights_decision["rights_mode"],
        "summary": (raw_item or {}).get("summary"),
        "body": (raw_item or {}).get("detail") or (raw_item or {}).get("summary"),
        "cover": (raw_item or {}).get("cover"),
    }
    payload = {k: v for k, v in src.items() if k in allowed and v is not None}
    payload["_external_image_allowed"] = external_image_allowed(rights_decision)
    payload["_blocked_fields"] = rights_decision["blocked_fields"]
    return payload


def build_search_payload(document, rights_decision):
    """10번: Public Search Payload도 동일 Gate를 거친다. summary/detail/mx.b/mx.p는
    이 함수가 애초에 만들지 않으므로 Search Index에 들어갈 수 없다 — LINK_ONLY 기준
    title/source/date/topic/original_url만 남긴다(rights_mode와 무관하게 이 5개가 상한선)."""
    return {
        "document_id": document.get("document_id"),
        "title": document.get("title"),
        "source": document.get("source_id"),
        "date": (document.get("published") or "")[:10],
        "topic": document.get("category"),
        "original_url": document.get("canonical_url"),
        "rights_mode": rights_decision["rights_mode"],
    }
