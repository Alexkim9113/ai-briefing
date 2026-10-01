# N-4 -- Presentation Model. A thin layer between the N-3 canonical Report JSON and any renderer
# (HTML/PDF/Public Page). It NEVER computes new facts, claims, evidence, or statuses -- it only
# adds display-only metadata (ordering, visibility, visualization hints, section titles) on top of
# a report object produced by report_engine.build_report(). Presentation fields never feed back
# into readiness/grounding/claim status.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import schema as sc  # noqa: E402

# Section 4 -- the N-4 Report UX information hierarchy (display order only, not a new section
# contract -- maps 1:1 onto N-3's existing SECTION_TYPES except COVER/EXECUTIVE_INTELLIGENCE/
# KEY_FINDINGS/WHAT_TO_WATCH/METHODOLOGY/LIMITATIONS, which are presentation-only framing the
# report_engine module does not compute as separate sections; their content is derived from
# existing section data at render time, never invented).
DISPLAY_SECTION_ORDER = (
    "KEY_QUESTION", "CURRENT_STATE", "KEY_CLAIMS", "WHAT_WE_KNOW", "WHAT_WE_DO_NOT_KNOW",
    "STATISTICAL_CONTEXT", "RESEARCH_EVIDENCE", "POLICY_CONTEXT", "COUNTEREVIDENCE",
    "ALTERNATIVE_EXPLANATIONS", "UNCERTAINTIES", "GEOGRAPHIC_CONTEXT", "TEMPORAL_CONTEXT",
    "METAXIS_POINT", "EVIDENCE_MAP", "SOURCE_PROVENANCE",
)

SECTION_DISPLAY_TITLES = {
    "KEY_QUESTION": "핵심 질문", "CURRENT_STATE": "현재 상태", "KEY_CLAIMS": "핵심 주장",
    "WHAT_WE_KNOW": "확인된 사실", "WHAT_WE_DO_NOT_KNOW": "아직 모르는 것",
    "STATISTICAL_CONTEXT": "통계", "RESEARCH_EVIDENCE": "연구 근거", "POLICY_CONTEXT": "정책/규제",
    "COUNTEREVIDENCE": "반증", "ALTERNATIVE_EXPLANATIONS": "대안 설명", "UNCERTAINTIES": "불확실성",
    "GEOGRAPHIC_CONTEXT": "지리적 맥락", "TEMPORAL_CONTEXT": "시간적 맥락",
    "METAXIS_POINT": "METAXIS POINT", "EVIDENCE_MAP": "근거 지도", "SOURCE_PROVENANCE": "출처",
}

# Section 6 -- EVIDENCE STATUS badges are a UI label over existing CLAIM_STATUSES, never a new
# scoring system. No numeric score is ever introduced.
EVIDENCE_STATUS_BADGES = {
    "SUPPORTED": "SUPPORTED", "PARTIALLY_SUPPORTED": "PARTIALLY SUPPORTED",
    "CONTESTED": "CONTESTED", "INSUFFICIENT_EVIDENCE": "INSUFFICIENT EVIDENCE",
    "OPEN": "UNKNOWN", "WEAKENED": "WEAKENED", "REJECTED": "REJECTED", "UNKNOWN": "UNKNOWN",
}

VISUALIZATION_TYPES = ("LINE_CHART_NO_FORECAST", "TABLE", "NONE")


def evidence_status_badge(claim_status):
    return EVIDENCE_STATUS_BADGES.get(claim_status, "UNKNOWN")


def build_executive_card(report):
    """Section 5 -- Executive Intelligence Card. KEY SIGNAL is only ever an evidence-supported
    claim's own rendered sentence; if no SUPPORTED/PARTIALLY_SUPPORTED claim exists, key_signal is
    explicitly 'NO_CONFIRMED_SIGNAL' or 'EVIDENCE_INSUFFICIENT' -- never invented."""
    key_claims_section = report["sections"].get("KEY_CLAIMS", {})
    supported_blocks = [b for b in key_claims_section.get("content_blocks", [])
                        if isinstance(b, dict) and b.get("claim_status") in ("SUPPORTED", "PARTIALLY_SUPPORTED")]
    if supported_blocks:
        key_signal = supported_blocks[0]["text"]
        key_signal_status = "KEY_SIGNAL_PRESENT"
    elif key_claims_section.get("content_blocks"):
        key_signal = "EVIDENCE_INSUFFICIENT"
        key_signal_status = "EVIDENCE_INSUFFICIENT"
    else:
        key_signal = "NO_CONFIRMED_SIGNAL"
        key_signal_status = "NO_CONFIRMED_SIGNAL"

    uncertainty_section = report["sections"].get("UNCERTAINTIES", {})
    major_uncertainty = (uncertainty_section.get("content_blocks") or ["없음"])[0]

    return {
        "current_state": report["sections"].get("CURRENT_STATE", {}).get("content_blocks", ["UNKNOWN"])[0],
        "key_signal": key_signal,
        "key_signal_status": key_signal_status,
        "evidence_status": report["readiness"],
        "major_uncertainty": major_uncertainty,
        "what_to_watch": _what_to_watch(report),
    }


def _what_to_watch(report):
    """Section 5/41's explicit ban on forecasting: WHAT TO WATCH only ever lists existing
    known_gaps as monitoring targets (closing a gap is observable), never a predicted event."""
    gaps = report["sections"].get("EVIDENCE_GAPS", {}).get("content_blocks", [])
    if not gaps:
        return ["모니터링 대상 없음 (현재 확인된 gap 없음)"]
    return [g.get("gap_type", "UNKNOWN") if isinstance(g, dict) else str(g) for g in gaps]


def build_statistics_chart_spec(statistics_block):
    """Section 9 -- a chart spec from a REAL statistics content block only. Never a forecast
    line, never an attribution overlay, never an axis that exaggerates a NO_CLEAR_SIGNAL trend."""
    return {
        "visualization_type": "LINE_CHART_NO_FORECAST" if statistics_block.get("observation_count", 0) > 1 else "TABLE",
        "indicator": statistics_block.get("indicator"),
        "geography": statistics_block.get("geography"),
        "period": statistics_block.get("period"),
        "source": statistics_block.get("source"),
        "trend_status": statistics_block.get("trend_status"),
        "forecast_line": False,
        "ai_attribution_overlay": False,
        "axis_note": "실제 관측값 범위를 그대로 사용 -- 추세를 과장하는 축 조정 없음",
    }


def build_presentation(report, display_title=None):
    """Attaches presentation-only metadata to a copy of the report. Never mutates the input
    report dict, never changes any claim/evidence/section content -- verified by
    test_presentation_never_changes_report_facts."""
    present_sections = []
    for section_type in DISPLAY_SECTION_ORDER:
        section = report["sections"].get(section_type)
        if not section:
            continue
        entry = {
            "section_type": section_type,
            "display_title": SECTION_DISPLAY_TITLES.get(section_type, section_type),
            "visibility": "VISIBLE" if section["status"] != "NOT_APPLICABLE" else "HIDDEN",
            "section": section,
        }
        if section_type == "STATISTICAL_CONTEXT":
            entry["charts"] = [build_statistics_chart_spec(b) for b in section.get("content_blocks", [])
                               if isinstance(b, dict) and "indicator" in b]
        present_sections.append(entry)

    return {
        "report_id": report["report_id"],
        "intelligence_id": report["intelligence_id"],
        "topic": report["topic"],
        "display_title": display_title or f"{report['topic']} Intelligence Report",
        "version": report["version"],
        "readiness": report["readiness"],
        "executive_card": build_executive_card(report),
        "sections": present_sections,
    }
