# PHASE M.5E-3 slice: Alternative Explanations preservation for AI_ENERGY_INFRA.
#
# Lists the real, well-known alternative drivers of rising electricity demand besides AI (general
# domain knowledge, not corpus-searched for the list itself), and separately runs one honest real
# corpus search per alternative to see whether the corpus happens to already discuss it.
#
# Vocabulary discipline (per standing constraints): OBSERVED_EFFECT / SUPPORTED_MECHANISM /
# POSSIBLE_IMPLICATION / SPECULATIVE_EXTENSION are graded-strength labels reserved for
# characterizing a REAL corpus-backed finding. An item with no corpus match gets
# GENERAL_KNOWLEDGE_NO_CORPUS_EVIDENCE instead -- general/domain knowledge alone is never given
# one of the 4 graded labels, to avoid conflating "well-established fact I know" with "documented
# in this corpus."
#
# Zero LLM calls. Stdlib only. Never fabricates documents or corpus content.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "energy_demand_alternatives_result.json"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_dp = _load_module("_dp_for_alt_explanations", INTEL_DIR / "evidence_network" / "deep_pilot.py")

GRADED_EFFECT_VOCAB = (
    "OBSERVED_EFFECT", "SUPPORTED_MECHANISM", "POSSIBLE_IMPLICATION", "SPECULATIVE_EXTENSION",
)
GENERAL_KNOWLEDGE_LABEL = "GENERAL_KNOWLEDGE_NO_CORPUS_EVIDENCE"

# Real, well-known alternative drivers of rising electricity demand besides AI. Each is real
# (non-fabricated) general domain knowledge; none of these is invented for this exercise.
ALTERNATIVE_EXPLANATIONS = [
    {
        "explanation_id": "MANUFACTURING_RESHORING",
        "label": "Manufacturing reshoring / onshoring",
        "description": (
            "Policy-driven and supply-chain-driven relocation of manufacturing capacity (e.g., "
            "semiconductor fabs, batteries) back to the US and other economies, adding new "
            "industrial electricity load independent of AI compute."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["reshoring", "onshoring", "reshore", "onshore", "factory construction"],
    },
    {
        "explanation_id": "EV_CHARGING_DEMAND_GROWTH",
        "label": "Electric vehicle (EV) charging demand growth",
        "description": (
            "Rising EV adoption increases residential, commercial, and fast-charging electricity "
            "demand, a well-documented driver of grid load growth independent of data centers."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["electric vehicle", "ev charging", "ev charger", "ev adoption"],
    },
    {
        "explanation_id": "EXTREME_CLIMATE_HVAC_DEMAND",
        "label": "Extreme climate/weather driving HVAC demand",
        "description": (
            "More frequent and intense heat waves and cold snaps increase peak electricity demand "
            "for air conditioning and heating, a recognized driver of grid stress independent of "
            "AI."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["heat wave", "extreme heat", "hvac", "cooling demand", "peak demand"],
    },
    {
        "explanation_id": "POPULATION_ECONOMIC_GROWTH",
        "label": "Population and general economic growth",
        "description": (
            "Baseline population growth and broad economic expansion increase aggregate "
            "electricity consumption over time, independent of any specific technology sector."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["population growth", "economic growth", "gdp growth"],
    },
    {
        "explanation_id": "GENERAL_CLOUD_COMPUTING_GROWTH",
        "label": "General cloud computing growth (not AI-specific)",
        "description": (
            "Growth in non-AI cloud workloads (web hosting, enterprise SaaS, streaming, storage) "
            "has driven data-center electricity demand growth for over a decade, predating the "
            "current AI buildout and continuing independent of it."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["cloud computing", "cloud growth", "data center demand", "hyperscale"],
    },
    {
        "explanation_id": "INDUSTRIAL_POLICY_SUBSIDIES",
        "label": "Industrial policy / subsidies driving new factory construction",
        "description": (
            "Government industrial policy (e.g., subsidies for semiconductor or battery plants) "
            "can drive new large-load factory construction whose electricity demand is a policy "
            "effect distinct from AI compute demand, even when the factories themselves make "
            "AI-adjacent hardware."
        ),
        "is_real_non_fabricated_alternative": True,
        "search_keywords": ["subsidy", "subsidies", "industrial policy", "chips act", "factory construction"],
    },
]


def _doc_text(doc):
    return f"{doc.get('title') or ''} {doc.get('abstract_excerpt') or ''}".lower()


def search_alternative_in_corpus(keywords, documents):
    """Honest, real search of the corpus for one alternative explanation. Returns the list of
    matching document_ids (likely empty for most -- a valid, honestly reported outcome)."""
    hits = []
    for did, doc in sorted(documents.items()):
        text = _doc_text(doc)
        matched = [kw for kw in keywords if kw in text]
        if matched:
            hits.append({"document_id": did, "title": doc.get("title"), "matched_keywords": matched})
    return hits


def classify_evidence_strength(corpus_hits):
    """Classifier: an alternative with no corpus match is GENERAL_KNOWLEDGE_NO_CORPUS_EVIDENCE,
    never one of the 4 graded effect-strength labels. An alternative WITH a real corpus match is
    graded conservatively as POSSIBLE_IMPLICATION by default here (a single title/abstract-level
    keyword hit, with no ability to verify full document content in this corpus's schema, does
    not support the stronger OBSERVED_EFFECT or SUPPORTED_MECHANISM labels; a human reviewer with
    the actual source document could upgrade or downgrade this)."""
    if not corpus_hits:
        return GENERAL_KNOWLEDGE_LABEL
    return "POSSIBLE_IMPLICATION"


def build_result(documents=None):
    documents = documents if documents is not None else _dp.load_documents(DOCUMENTS_PATH)
    entries = []
    graded_count = 0
    general_only_count = 0

    for alt in ALTERNATIVE_EXPLANATIONS:
        corpus_hits = search_alternative_in_corpus(alt["search_keywords"], documents)
        strength_label = classify_evidence_strength(corpus_hits)
        if strength_label in GRADED_EFFECT_VOCAB:
            graded_count += 1
        else:
            general_only_count += 1
        entries.append({
            **alt,
            "corpus_search_result": {
                "status": "REAL_EVIDENCE" if corpus_hits else "NOT_FOUND",
                "matches": corpus_hits,
            },
            "evidence_strength_label": strength_label,
        })

    return {
        "topic_name": "AI_ENERGY_INFRA",
        "purpose": (
            "Preserve real, well-known alternative drivers of electricity demand growth besides "
            "AI, so the topic's evidence chain is not implicitly read as claiming AI is the sole "
            "cause of demand growth."
        ),
        "vocabulary_discipline": {
            "graded_effect_vocabulary": list(GRADED_EFFECT_VOCAB),
            "general_knowledge_label": GENERAL_KNOWLEDGE_LABEL,
            "rule": (
                "General/domain knowledge with no corpus-backed document is labeled "
                f"{GENERAL_KNOWLEDGE_LABEL}, never one of the 4 graded effect-strength labels. "
                "Only a real corpus-backed finding may receive a graded label, and "
                "POSSIBLE_IMPLICATION must never silently become EXPECTED_OUTCOME."
            ),
        },
        "alternatives": entries,
        "summary": {
            "total_alternatives": len(entries),
            "graded_by_corpus_evidence": graded_count,
            "general_knowledge_only": general_only_count,
        },
    }


def main():
    result = build_result()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {result['summary']}")


if __name__ == "__main__":
    main()
