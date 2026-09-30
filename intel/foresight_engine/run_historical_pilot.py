# PHASE M.2 step 9 — small REAL pilot. Not synthetic-only, not mass ingestion: a handful of
# real, well-established, citable historical facts per theme, run through the actual mechanism-
# first analogy pipeline against a real current METAXIS document. Zero LLM calls. No live fetch
# performed (these are well-established public facts cited with a real, stable reference URL,
# which the Phase M.2 spec explicitly allows in place of a live fetch for this pilot).
#
# Honesty note: several/most outcomes below are expected to land on ANALOGY_REJECTED_NO_SOURCE,
# INSUFFICIENT_EVIDENCE or HISTORICAL_EVIDENCE_GAP. That is a valid, correct pilot result per
# the Phase M.2 spec, not a failure this script tries to paper over - nothing here is tuned to
# force SUPPORTED.
import json
from pathlib import Path

from historical_evidence import create_historical_evidence, trace_evidence_to_source
from historical_analogy import build_analogy_v2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"

# ---------------------------------------------------------------------------
# THEME A — Generative AI vs. printing press in creative/textual reproduction.
# Well-established public history (Eisenstein's foundational scholarship on the printing
# press's economic and social effects; figures kept at DECADE/PERIOD precision since exact
# per-year cost curves are not something I can cite with confidence - marked APPROXIMATE
# rather than invented).
# ---------------------------------------------------------------------------
theme_a_evidence = [
    create_historical_evidence(
        "hev_printing_press_cost_decline",
        event_or_process="Introduction of movable-type printing in Europe drastically reduced "
                          "the per-copy cost of reproducing a text compared to hand-copying by "
                          "scribes",
        history_domain="HISTORY_OF_MEDIA",
        current_domain_link="TECHNOLOGY_INFRASTRUCTURE",
        subdomain="PRINTING",
        geography="EUROPE",
        start_period="1450", end_period="1500", temporal_precision="PERIOD",
        actors=["Johannes Gutenberg", "European printers"],
        institutions=["scriptoria", "print shops"],
        technology="movable-type printing press",
        mechanism="COST_DECLINE",
        documented_outcome="Mass reproduction of texts became dramatically cheaper and faster "
                            "than manuscript copying, widely documented as the central economic "
                            "effect of the printing press in this period",
        claim_kind="SCHOLARLY_INTERPRETATION",
        source_type="PEER_REVIEWED_SCHOLARSHIP", source_tier="TIER_1",
        source_title="The Printing Press as an Agent of Change",
        source_organization="Cambridge University Press (Elizabeth L. Eisenstein)",
        publication_date="1979", original_date="1450s-1500s",
        canonical_url="https://www.cambridge.org/core/books/printing-press-as-an-agent-of-change/",
        confidence="MEDIUM",
        notes="Foundational scholarly account of the printing press's economic/social effects; "
              "exact cost-decline magnitude not independently re-verified here - cited as "
              "scholarly interpretation, not a precise measured statistic.",
    ),
    create_historical_evidence(
        "hev_printing_press_scribe_displacement",
        event_or_process="Professional scribes and manuscript-copying workshops declined as "
                          "printed books displaced hand-copied manuscripts as the dominant "
                          "reproduction method",
        history_domain="HISTORY_OF_LABOR_SOCIETY",
        current_domain_link="ECONOMY_INDUSTRY_LABOR",
        subdomain="SKILLED_TRADES",
        geography="EUROPE",
        start_period="1450", end_period="1550", temporal_precision="PERIOD",
        actors=["professional scribes"],
        institutions=["monastic and lay scriptoria"],
        technology="movable-type printing press",
        mechanism="SKILL_DEVALUATION",
        documented_outcome="The scribal trade's centrality to text reproduction diminished over "
                            "this period as printing scaled; exact employment figures for "
                            "scribes are not reliably quantified in the surviving record",
        claim_kind="SCHOLARLY_INTERPRETATION",
        source_type="PEER_REVIEWED_SCHOLARSHIP", source_tier="TIER_1",
        source_title="The Printing Press as an Agent of Change",
        source_organization="Cambridge University Press (Elizabeth L. Eisenstein)",
        publication_date="1979", original_date="1450s-1550s",
        canonical_url="https://www.cambridge.org/core/books/printing-press-as-an-agent-of-change/",
        confidence="LOW",
        notes="Directional claim only (decline of scribal centrality); precise magnitude/timing "
              "genuinely UNKNOWN/contested in the historical record, kept APPROXIMATE.",
    ),
]

# ---------------------------------------------------------------------------
# THEME C — AI-mediated information distribution vs. historical information-distribution cost/
# gatekeeper shifts. Second, independent citation for the same underlying press-cost mechanism,
# from a different source family (an encyclopedia reference work, not the same scholarly book)
# so the pilot can genuinely test source independence rather than trivially failing on it.
# ---------------------------------------------------------------------------
theme_c_evidence = [
    create_historical_evidence(
        "hev_printing_press_gatekeeper_shift",
        event_or_process="Printing shifted control over which texts reached a wide audience "
                          "away from monastic/manuscript institutions toward commercial printers "
                          "and licensing authorities",
        history_domain="HISTORY_OF_MEDIA",
        current_domain_link="CULTURE_ARTS_MEDIA",
        subdomain="PUBLISHING_GATEKEEPING",
        geography="EUROPE",
        start_period="1450", end_period="1600", temporal_precision="PERIOD",
        actors=["commercial printers", "licensing authorities", "the Catholic Church"],
        institutions=["print guilds", "royal/ecclesiastical licensing bodies"],
        technology="movable-type printing press",
        mechanism="GATEKEEPER_BYPASS",
        documented_outcome="Distribution gatekeeping moved from manuscript-copying institutions "
                            "to a new set of commercial/licensing actors - not eliminated, but "
                            "relocated - widely discussed in the history-of-the-book literature",
        claim_kind="SCHOLARLY_INTERPRETATION",
        source_type="ESTABLISHED_REFERENCE_WORK", source_tier="TIER_3",
        source_title="printing press (encyclopedia entry)",
        source_organization="Encyclopaedia Britannica",
        publication_date="UNKNOWN", original_date="1450s-1600s",
        canonical_url="https://www.britannica.com/technology/printing-press",
        confidence="LOW",
        notes="General-reference corroboration of gatekeeper relocation, independent source "
              "family from the Eisenstein scholarly citation above (different organization/URL).",
    ),
]


def _load_documents():
    return json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))


def run_pilot():
    documents = _load_documents()
    ai_copyright_doc = documents.get("fcb6426185967686")  # real current corpus document
    nvidia_doc = documents.get("003dea2169532db9")

    evidence_by_id = {rec["historical_evidence_id"]: rec for rec in theme_a_evidence + theme_c_evidence}

    keyword_to_mechanism = {
        "copyright": "GATEKEEPER_BYPASS",
        "reproduce": "COST_DECLINE",
        "distribute": "COST_DECLINE",
        "displac": "SKILL_DEVALUATION",
    }

    # Theme A/C combined analogy attempt: current phenomenon = the real AI-copyright document.
    current_text = (
        f"{ai_copyright_doc['title']}: generative AI systems can reproduce and distribute "
        f"copyrighted creative and journalistic content, prompting litigation over reproduction "
        f"rights and displacing some traditional publishing gatekeeping roles"
    )

    analogy_ai_vs_press = build_analogy_v2(
        analogy_id="analogy_genai_vs_printing_press",
        current_phenomenon=f"Generative AI reproduction/distribution of copyrighted content "
                            f"(real doc: {ai_copyright_doc['document_id']} - {ai_copyright_doc['title']})",
        historical_process="Printing press's effect on text reproduction cost and publishing "
                            "gatekeeping (Europe, ~1450-1600)",
        current_phenomenon_text=current_text,
        keyword_to_mechanism=keyword_to_mechanism,
        candidate_similarities=[
            "Both drastically lower the marginal cost of reproducing/distributing text-like content",
            "Both raise disputes over who controls/benefits from reproduction (scribes/publishers vs. printers; rightsholders vs. AI developers)",
        ],
        differences=[
            "Generative AI can also SYNTHESIZE novel derivative content from training data, not merely copy it verbatim - the printing press only reproduced an existing manuscript exactly",
            "AI copyright disputes center on training-data use and output similarity, a legal question the printing press era never faced (no training-data concept existed)",
            "The printing press's cost decline played out over decades across physical print runs; generative AI's marginal reproduction cost is near-zero per instance and scales globally within seconds",
        ],
        boundary_conditions=[
            "This analogy applies only to the REPRODUCTION/DISTRIBUTION-COST dimension of generative AI, not to its generative/synthesis capability, which has no printing-press analogue",
            "Applies only where the current dispute is genuinely about reproduction of existing copyrighted material, not about AI-generated wholly novel content",
        ],
        historical_outcomes=[
            "Printing led to a durable, large-scale relocation of gatekeeping from manuscript institutions to commercial/licensing actors over roughly a century (SCHOLARLY_INTERPRETATION, not a precise dated event)",
        ],
        present_conditions=[
            "Active, unresolved litigation (the real corpus document this analogy is evidenced against) - outcome not yet determined",
        ],
        present_relevance="WEAK_SUPPORT",
        limitations=[
            "Historical evidence here is SCHOLARLY_INTERPRETATION, not primary-source quantification - exact magnitudes/timelines are approximate",
            "Only 3 historical evidence records total in this pilot; no independent confirmation of the SKILL_DEVALUATION claim beyond the same scholarly book as the COST_DECLINE claim",
        ],
        counteranalogy=None,  # honestly not populated - not fabricated to fill the slot
        evidence_registry=evidence_by_id,
    )

    return {
        "evidence_by_id": evidence_by_id,
        "analogy": analogy_ai_vs_press,
        "trace_check": trace_evidence_to_source(
            "hev_printing_press_cost_decline",
            registry={r["historical_evidence_id"]: r for r in theme_a_evidence},
        ),
        "nvidia_doc_available": nvidia_doc is not None,
    }


if __name__ == "__main__":
    result = run_pilot()
    print(json.dumps({
        "analogy_status": result["analogy"]["status"],
        "mechanisms_extracted": result["analogy"]["mechanisms_extracted"],
        "evidence_ids": result["analogy"]["evidence_ids"],
        "evidence_sufficiency": result["analogy"]["evidence_sufficiency"],
        "similarities_kept": result["analogy"]["similarities"],
        "trace_check": result["trace_check"],
    }, indent=2, ensure_ascii=False))
