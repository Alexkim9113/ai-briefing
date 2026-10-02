# METAXIS Operating Contracts (O-2D closure/verification round)

This file fixes, as permanent documentation, three operating contracts that were previously
implicit in code comments and scattered module behavior. It changes no behavior and bumps no
Report or Intelligence Object version. Where current code does not fully match an aspirational
rule, that gap is recorded honestly below rather than hidden or "fixed" by editing behavior
during this documentation round.

Architecture reference (unchanged): SOURCE → EVIDENCE → CLAIM → HYPOTHESIS →
INTELLIGENCE OBJECT → REPORT → PUBLIC PRODUCT → OPERATOR WORKSPACE.

---

## 1. News Copyright Operating Contract

**Where enforced today:** `briefing.py` (`make_item`, `summarize`, `detail_lines`,
`run_article_provenance_pilot`), constants `SUMMARY_CHARS` / `DETAIL_CHARS` (briefing.py lines
~37-38).

**Permanent rules:**

1. A general (non-promoted) news item stores: `title`, `title_ko` (translated title), `source`
   (outlet), `published` (date), `category`, `field`, and `link` (URL) — plus a short,
   copyright-bounded excerpt (see rule 2). It never stores the full article body.
2. Two capped excerpt fields exist and are the ONLY body-text-derived fields stored:
   - `summary` / `summary_ko`: an extractive lead-sentence excerpt, hard-capped at
     `SUMMARY_CHARS` = 180 characters (`summarize()`), built only from the publisher's own
     RSS/Atom `<description>`/`<summary>` field — never from a scraped article page.
   - `detail` / `detail_ko`: a TextRank-selected set of up to 5 sentences from that same
     publisher-supplied feed description, hard-capped at `DETAIL_CHARS` = 300 characters
     (`detail_lines()`). The in-code comment already names the copyright rationale:
     `발췌 요약 최대 길이(저작권상 짧게 유지)` ("excerpt length capped, kept short for
     copyright reasons").
   - Neither field is ever populated from a full fetched article body. `detail_lines()`'s own
     docstring states its input is "언론사가 피드로 공개한 소개글" (the intro text the outlet
     itself exposed via its public feed), not the article page.
3. Full article text IS fetched, but only inside `run_article_provenance_pilot()`
   (`content_acquisition.acquire_content()`), and only for a small daily-capped sample
   (`PROVENANCE_FETCH_CAP`) of newly admitted items, for the sole purpose of extracting outbound
   reference links for the REPORTS_ON relationship graph
   (`intel/relationships_company_gov.json`). That function's own comment states the invariant:
   `원문 전체 텍스트는 여기서 참조 추출에만 쓰이고 어디에도 새로 저장되지 않는다 (MINIMAL
   STORAGE, 기존 관례 그대로)` — the full text is used only for reference extraction and is
   never persisted anywhere; the `finally:` block explicitly discards the in-memory `text` and
   `html_body` variables after use. `MAX_PROVENANCE_DEPTH == 1` is asserted so this fetch never
   cascades into re-fetching linked pages.
4. **"Important News" promotion** — an item being surfaced with deeper treatment than the
   standard minimal fields (today: the `hot` sort-priority field, and in the Intelligence
   pipeline: progression from a collected document into `intel/claims` /
   `intel/hypothesis` / `intel/intelligence_objects`) must be justified by at least one of:
   - policy/regulatory change
   - a major empirical data release
   - industry structure change
   - infrastructure change
   - labor market change
   - potential to change an existing Intelligence judgment (an existing
     `intel/intelligence_objects/intelligence_objects.json` entry)
   - important counterevidence (`intel/counterevidence/`)
   - long-term tracking value
   and **never** by pageviews or virality alone.

**Verification done this round (see item 4 below for the real test, and the handback report for
command output):**
- `grep`'d the full `intel/` tree and `briefing.py` for `pageview`/`virality` as a promotion
  criterion: no such criterion exists anywhere in the codebase. PASS (no virality-based gate to
  remove).
- The closest existing, already-shipped implementation of the 8-criterion list is
  `intel/legacy_enrichment/priority_candidates.py`, which scores documents on policy/regulatory
  flag, major tech releases, labor market shifts, industry/investment changes, social impact,
  and longitudinal-tracking value (repeated-event clustering) — all via literal, human-reviewable
  keyword/field matching, explicitly "no LLM, no fuzzy semantic matching." It does not score on
  pageviews or any popularity signal. This module is read-only (never writes
  `intel/documents.json`) and is the right anchor point for this contract; it was not modified
  this round.
- **Honest gap**: field inventory of a real collected day (`data/2026-10-02.json`, 370 items)
  shows `summary`/`detail` ARE present on general items regardless of `hot` status (74/370 items
  had a non-empty `detail`, 0 of those also had `hot` set) — i.e. the capped excerpt is not
  gated by "importance." This is consistent with rules 1-3 above (a short, copyright-bounded,
  publisher-sourced excerpt, never full text) but is **not** the same as the narrower
  "title+outlet+date+category+URL only, nothing else" framing some phrasings of this contract
  use. The code's own comments show this was a deliberate, copyright-reviewed design choice
  (`SUMMARY_CHARS`/`DETAIL_CHARS` + the "저작권상 짧게 유지" comment), not an oversight. This
  round documents the ACTUAL contract (rules 1-3) rather than silently weakening the aspirational
  rule to claim a false PASS, and does not change behavior. The field list in rule 1 has been
  corrected to name `summary`/`summary_ko`/`detail`/`detail_ko` explicitly as the only
  body-text-derived, hard-capped exceptions to the minimal-field rule — not as full article text
  or lead paragraphs, which is where the actual risk the aspirational rule guards against (full
  reproduction of copyrighted body text) lies, and which remains verified absent (see Priority 4
  test).

---

## 2. Token Allocation Contract

No live token/LLM-budget allocator exists in this codebase today — there is no central scheduler
that spends a shared token or cost budget across task types (confirmed by `grep` across `intel/`
and `briefing.py`: no `token_budget`, `max_tokens` allocation table, or priority-queue construct
tied to LLM spend). This section is **documentation only**, fixing the intended priority order
for any future token/LLM-budget-aware code (e.g. a future `operator_brain` scheduler) to honor,
highest priority first:

1. Intelligence Research
2. Evidence Verification
3. Counterevidence
4. Claim/Hypothesis Evaluation
5. Intelligence Synthesis
6. Report
7. Operator Decision Support
8. Important Signal Analysis
9. General Feed

Where a real, narrower precedent already exists: `intel/evidence_pipeline/`,
`intel/counterevidence/`, `intel/claims/`, and `intel/hypothesis/` are processed, in the real
pipeline wiring, ahead of `intel/report_engine/` report generation, which is itself upstream of
`intel/operator_workspace/` and the General Feed (`briefing.py` collection). That existing
module ordering is consistent with, and is the closest real anchor for, the priority list above.

---

## 3. Feed → Intelligence Funnel

Named pipeline, using real existing module names (no new engine introduced):

```
briefing.py collect()/collect_source()/parse_feed()
        │   (RSS/Atom ingestion → Feed item: title/summary/link/date, capped per
        │    Section 1's Copyright Contract)
        ▼
data/<date>.json item   ──(admission)──▶  intel/documents.json
        │                                  (intel/document_identity, intel/document_service.py)
        ▼
intel/evidence_admission/admission_gate.py
        │   (deterministic admission: is this a real, independent, sufficiently-specific
        │    EVIDENCE candidate, not just a collected Feed item?)
        ▼
intel/evidence.json  (via intel/evidence_service.py)
        │
        ├──▶ intel/counterevidence/   (searched for disconfirming evidence on the same claim)
        │
        ▼
intel/claims/  (claims.json via claim construction from admitted Evidence)
        ▼
intel/hypothesis/  (hypothesis_model: claims aggregated/weighed into a testable Hypothesis)
        ▼
intel/intelligence_objects/intelligence_objects.json
        │   (an Intelligence Object: a versioned, hash-pinned judgment built from Hypotheses —
        │    e.g. intel_87210a61730c22b9 / AI_ENERGY_INFRA, frozen at v6 and never touched by
        │    this round)
        ▼
intel/report_engine/  (report_engine.py builds a Report from one or more Intelligence Objects)
        ▼
intel/report_engine/reports/report_<id>_v<N>.json
        │
        ├──▶ Public Product   (intel/public_relevance/, public_delivery.py → site/intelligence/)
        └──▶ Operator Workspace  (intel/operator_workspace/, operator_ui.py → site/operator/)
```

Most Feed items never cross the `admission_gate.py` boundary — they remain general Feed items
under Section 1's minimal-field contract and are published only to the public news feed
(`briefing.py` → `site/<category>/`). Only items that clear admission, evidence sufficiency,
claim construction, and hypothesis evaluation can ever contribute to an Intelligence Object, and
only a change that clears `intel/intelligence_objects/n2_contract_check.py` and the Report
Engine's own versioning rules can bump a Report or Intelligence Object version — which, per this
round's standing rule, did not happen here.
