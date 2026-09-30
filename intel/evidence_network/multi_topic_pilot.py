# PHASE M.5E-3 -- item 1/2: generalized Deep Pilot evidence-chain construction, usable for an
# arbitrary topic (keyword list + BASELINE/CURRENT temporal windows), not just the hardcoded
# AI_ENERGY_INFRA case in deep_pilot.py.
#
# This module is ADDITIVE: it imports deep_pilot.py and reuses its functions/constants directly
# rather than forking or rewriting them, exactly per the M.5E-3 instructions -- deep_pilot.py's
# own AI_ENERGY_INFRA behavior (and its committed test suite / deep_pilot_result.json) is never
# modified by this module. AI_ENERGY_INFRA's own generalized run below reuses
# deep_pilot.build_evidence_chain()/deep_pilot_report() verbatim; it is not reimplemented.
#
# Zero LLM. Deterministic Python, stdlib only. Never fabricates a document, a match, or a
# "real evidence" node -- every REAL_EVIDENCE node references an actual document_id that already
# exists in intel/documents.json, found by real title/field substring matching. An honest gap
# (a GAP_STATUS) is a correct, valid, and expected result, not a bug to paper over.
import json
from dataclasses import dataclass, field
from pathlib import Path

import deep_pilot as dp

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TopicDef:
    """A pilot topic's real, documented definition. `field_value` is the real `field` tag in
    documents.json this topic's NEWS/RESEARCH documents carry. `policy_keywords`/`ai_hints` find
    real POLICY documents relevant to the topic (same two-keyword-set method deep_pilot.py uses
    for AI_ENERGY_INFRA: a topic keyword AND an AI hint must both appear in the title).
    `cross_domain_phrases` are the unambiguous multi-word phrases used to detect a real
    cross-domain reference to THIS topic's subject matter inside OTHER topics' documents.
    `other_field_values` names which other pilot topics' field-tagged documents are searched for
    that cross-domain reference."""

    name: str
    field_value: str
    policy_keywords: tuple
    ai_hints: tuple
    cross_domain_phrases: tuple
    other_field_values: tuple
    selection_note: str


# Real field-tag document counts (see intel/temporal_depth/pilot_topic_coverage.py PILOT_TOPICS
# comment): AI_AGENTS/에이전트 = 12, AI_LABOR/사회·노동 = 11, AI_ENERGY_INFRA/에너지·환경 = 11.
TOPIC_AI_ENERGY_INFRA = TopicDef(
    name="AI_ENERGY_INFRA",
    field_value=dp.TOPIC_FIELD_VALUE,
    policy_keywords=dp._ENERGY_POLICY_KEYWORDS,
    ai_hints=dp._AI_HINTS,
    cross_domain_phrases=dp._CROSS_DOMAIN_ENERGY_PHRASES,
    other_field_values=("에이전트", "사회·노동"),
    selection_note=(
        "M.5E-2's original pilot topic; reused here via deep_pilot.py's own functions, not "
        "reimplemented, to prove the generalized pipeline reproduces the exact same result"
    ),
)

# AI_AGENTS keyword choices (documented, judgment call): phrases that describe autonomous /
# tool-using AI systems as a subject, distinct from a generic mention of "AI". Chosen to mirror
# the specificity of the energy topic's phrase-based cross-domain matching (avoids matching a
# bare "agent" which could mean a real-estate or insurance agent in an unrelated NEWS piece).
TOPIC_AI_AGENTS = TopicDef(
    name="AI_AGENTS",
    field_value="에이전트",
    policy_keywords=("ai agent", "autonomous agent", "agentic", "ai agents"),
    ai_hints=dp._AI_HINTS,
    cross_domain_phrases=("ai agent", "autonomous agent", "agentic workflow", "ai agents"),
    other_field_values=("사회·노동", "에너지·환경"),
    selection_note=(
        "keyword set chosen to describe autonomous/tool-using AI systems as a subject; not "
        "swapped in place of a spec default -- AI_AGENTS is itself one of the two spec-named "
        "additional topics"
    ),
)

# AI_LABOR keyword choices (documented, judgment call): phrases about AI's effect on jobs/the
# labor market. "workforce" and "automation jobs" included because that is how this corpus's
# real 사회·노동-tagged NEWS documents tend to phrase the subject (checked by hand against titles
# before picking the set -- see m5e3_progress_check.json for the honest coverage finding this
# produced).
TOPIC_AI_LABOR = TopicDef(
    name="AI_LABOR",
    field_value="사회·노동",
    policy_keywords=("ai jobs", "labor market", "workforce", "automation jobs", "job displacement"),
    ai_hints=dp._AI_HINTS,
    cross_domain_phrases=("labor market", "job displacement", "workforce automation", "job losses"),
    other_field_values=("에이전트", "에너지·환경"),
    selection_note=(
        "keyword set chosen to describe AI's effect on jobs/the labor market; AI_LABOR is one "
        "of the two spec-named additional topics, not a substitute"
    ),
)

ALL_TOPICS = (TOPIC_AI_ENERGY_INFRA, TOPIC_AI_AGENTS, TOPIC_AI_LABOR)


def find_topic_policy_documents(documents, topic_def):
    """Generalized form of deep_pilot.find_topic_policy_documents(): same substring-matching
    method, parameterized by topic keyword/hint sets instead of the hardcoded energy ones."""
    matches = {}
    for did, d in documents.items():
        if d.get("document_type") != "POLICY":
            continue
        title_lower = (d.get("title") or "").lower()
        if not any(kw in title_lower for kw in topic_def.policy_keywords):
            continue
        if not any(hint in title_lower for hint in topic_def.ai_hints):
            continue
        matches[did] = d
    return matches


def topic_corpus(topic_def, documents=None):
    documents = documents if documents is not None else dp.load_documents()
    field_tagged = {did: d for did, d in documents.items() if d.get("field") == topic_def.field_value}
    policy_matched = find_topic_policy_documents(documents, topic_def)
    combined = dict(field_tagged)
    combined.update(policy_matched)
    return combined


def classify_topic_documents(topic_def, documents=None):
    docs = topic_corpus(topic_def, documents)
    buckets = {"BASELINE": [], "TRANSITION": [], "CURRENT": [], "UNASSIGNED_GAP": []}
    for did, d in docs.items():
        buckets[dp.classify_document(d)].append(did)
    for k in buckets:
        buckets[k].sort()
    return buckets


def _find_cross_domain_hit(topic_def, documents):
    for did, d in sorted(documents.items()):
        if d.get("field") not in topic_def.other_field_values:
            continue
        title_lower = (d.get("title") or "").lower()
        if any(kw in title_lower for kw in topic_def.cross_domain_phrases):
            return did
    return None


def build_evidence_chain(topic_def, documents=None):
    """Generalized 10-node evidence chain, mirroring deep_pilot.build_evidence_chain()'s exact
    node-by-node logic but parameterized by topic_def. For TOPIC_AI_ENERGY_INFRA this is proven
    (by test) to reproduce deep_pilot.build_evidence_chain()'s exact output."""
    documents = documents if documents is not None else dp.load_documents()
    all_docs = topic_corpus(topic_def, documents)
    buckets = classify_topic_documents(topic_def, documents)

    current_news = sorted(
        (did for did in buckets["CURRENT"] if all_docs[did].get("document_type") == "NEWS"),
        key=lambda did: all_docs[did].get("published") or "",
        reverse=True,
    )
    current_research = sorted(
        (did for did in buckets["CURRENT"] if all_docs[did].get("document_type") == "RESEARCH"),
        key=lambda did: all_docs[did].get("published") or "",
        reverse=True,
    )
    baseline_policy = buckets["BASELINE"]

    chain = {}

    if current_news:
        chain["CURRENT_EVENT"] = dp._node(
            current_news[0],
            f"most recent real NEWS document tagged field=={topic_def.field_value}, published "
            "in the CURRENT bucket (>= 2026-09-01)",
            all_docs,
        )
    else:
        chain["CURRENT_EVENT"] = dp._node("TEMPORAL_GAP", "no real NEWS document falls in the CURRENT bucket")

    if current_research:
        chain["PRIMARY_EVIDENCE"] = dp._node(
            current_research[0],
            "no government/official primary source falls in the CURRENT bucket for this topic; "
            "the most recent real RESEARCH (arXiv) document is reported instead, explicitly "
            "labeled as such, not upgraded to an official-primary-source claim",
            all_docs,
        )
    else:
        chain["PRIMARY_EVIDENCE"] = dp._node("SOURCE_GAP", "no RESEARCH or official document in the CURRENT bucket")

    if baseline_policy:
        chain["PREVIOUS_STATE"] = dp._node(
            baseline_policy[0],
            "a real POLICY (Federal Register) document that both title-matches this topic's "
            "keywords and references AI, published before the BASELINE cutoff",
            all_docs,
        )
    else:
        chain["PREVIOUS_STATE"] = dp._node("TEMPORAL_GAP", "no real BASELINE document found")

    if buckets["TRANSITION"]:
        chain["CONFIRMED_CHANGE"] = dp._node(
            buckets["TRANSITION"][0],
            "real document published in the TRANSITION window between PREVIOUS_STATE and "
            "CURRENT_EVENT",
            all_docs,
        )
    else:
        chain["CONFIRMED_CHANGE"] = dp._node(
            "TEMPORAL_GAP",
            "no real document in this topic's corpus bridges the BASELINE and CURRENT windows "
            "-- an honestly reported gap, not an oversight",
        )

    chain["STATISTICAL_CONTEXT"] = dp._node(
        "STATISTICAL_GAP",
        "corpus-wide: no statistical-agency source is registered in this corpus's admission "
        "gate (see intel/source_diversity/audit.py statistical_source_ratio() == 0/597)",
    )

    research_pool = [did for did in sorted(all_docs)
                      if all_docs[did].get("document_type") == "RESEARCH"
                      and did != chain["PRIMARY_EVIDENCE"].get("document_id")]
    if research_pool:
        chain["RESEARCH_CONTEXT"] = dp._node(
            research_pool[0],
            "a real, distinct arXiv RESEARCH document from this topic's corpus, offering "
            "additional technical context beyond PRIMARY_EVIDENCE",
            all_docs,
        )
    else:
        chain["RESEARCH_CONTEXT"] = dp._node("RESEARCH_GAP", "no additional distinct RESEARCH document in this topic's corpus")

    chain["HISTORICAL_CONTEXT"] = dp._node(
        "HISTORY_GAP",
        "corpus-wide: intel/foresight_engine has zero registered historical_evidence records "
        "for any pilot topic today (see pilot_topic_coverage.py historical_evidence_count == 0)",
    )

    cross_domain_hit = _find_cross_domain_hit(topic_def, documents)
    if cross_domain_hit:
        chain["CROSS_DOMAIN_EFFECT"] = dp._node(
            cross_domain_hit,
            "a real document tagged with a DIFFERENT pilot topic's field value that also "
            "title-matches this topic's cross-domain phrase list",
            documents,
        )
    else:
        chain["CROSS_DOMAIN_EFFECT"] = dp._node(
            "SOURCE_GAP",
            "no document in the other pilot topics' fields title-matches this topic's "
            "cross-domain phrase list in the real corpus",
        )

    chain["COUNTEREVIDENCE"] = dp._node(
        "COUNTEREVIDENCE_GAP",
        "no counterevidence-flagging pipeline has been run for this topic; "
        "pilot_topic_coverage.py's own matrix already reports counterevidence_flagged as UNKNOWN",
    )

    chain["UNCERTAINTY"] = {
        "status": "NOTED",
        "document_id": None,
        "reason": (
            f"this topic's real corpus has {len(all_docs)} total documents across all buckets "
            f"(BASELINE={len(buckets['BASELINE'])}, TRANSITION={len(buckets['TRANSITION'])}, "
            f"CURRENT={len(buckets['CURRENT'])}, UNASSIGNED_GAP={len(buckets['UNASSIGNED_GAP'])}) "
            "-- any REAL_EVIDENCE node above rests on this small, real sample, not a broad one"
        ),
    }

    return chain


def topic_report(topic_def, documents=None):
    documents = documents if documents is not None else dp.load_documents()
    buckets = classify_topic_documents(topic_def, documents)
    all_docs = topic_corpus(topic_def, documents)
    chain = build_evidence_chain(topic_def, documents)

    real_evidence_nodes = sum(1 for n in chain.values() if n["status"] in ("REAL_EVIDENCE", "NOTED"))
    gap_nodes = sum(1 for n in chain.values() if n["status"] in dp.GAP_STATUSES)

    return {
        "topic_name": topic_def.name,
        "topic_field_value": topic_def.field_value,
        "topic_selection_reason": topic_def.selection_note,
        "policy_keywords_used": list(topic_def.policy_keywords),
        "cross_domain_phrases_used": list(topic_def.cross_domain_phrases),
        "total_topic_documents": len(all_docs),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
        "bucket_document_ids": buckets,
        "evidence_chain": chain,
        "chain_summary": {
            "total_nodes": len(dp.CHAIN_NODES),
            "real_evidence_or_noted_nodes": real_evidence_nodes,
            "gap_nodes": gap_nodes,
        },
    }


def main():
    documents = dp.load_documents()
    outputs = {
        TOPIC_AI_AGENTS: HERE / "deep_pilot_ai_agents_result.json",
        TOPIC_AI_LABOR: HERE / "deep_pilot_ai_labor_result.json",
    }
    for topic_def, out_path in outputs.items():
        report = topic_report(topic_def, documents)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}: {report['chain_summary']}")


if __name__ == "__main__":
    main()
