# M.5E FINAL Section 26 — USEFUL_BUT_UNCLASSIFIED sample audit

73 documents total (Corpus Quality Section 21). Random sample of 15 (seed=42, reproducible)
inspected directly against their real `source_id`/`category`/`title`:

- `src_khan_co_kr` / 채용 회복 기사 (hiring/labor news, no AI mention)
- `src_ein_news` / GPU 산업 forecast press-release aggregator (industry-report spam, not AI-specific)
- `src_newsis_com` / 중기부 연구개발과제 선정 (unrelated gov grant announcement)
- `src_federal_register` ×5 / routine regulatory notices (loan fund, Federal Reserve policy,
  Unified Agenda, isotope advisory committee, National ... information collection) — none mention
  AI in the title at all
- `src_zdnet_com` / Bose headphone Bluetooth update (consumer electronics, not AI)
- `src_newsis_com` / 고등어 어획량 (mackerel catch volume — completely unrelated)
- `src_crossref` / rural electrification research (energy-adjacent but not AI)
- `src_itbiznews_com` / AI agent product news (genuinely AI-related, title keyword list missed it)
- `src_fnnews_com` / NYSE market wrap mentioning Nvidia in passing (not substantively AI content)
- `src_newsis_com` / 엔화 환율 (yen exchange rate, unrelated)

**Root cause (honest finding, not a classifier defect):** the overwhelming majority of this
sample (12/15) are genuinely NOT about any `REAL_DOMAINS`/`PLANET_SUBDOMAINS` topic — they are
routine Federal Register notices, general business/finance wire items, or unrelated beats that
happen to share a `source_id` (e.g. `src_federal_register`, `src_newsis_com`) with topic-relevant
documents from the same feed. `domain_classifier.py`'s conservative TITLE_KEYWORD fallback
correctly declines to guess a domain for them, per its own design (Section 3-6: a LOW-confidence
keyword match is required, not inferred from source alone). A small minority (2/15: the AI-agent
product article and the Nvidia-mention market wrap) are borderline AI-adjacent and were missed by
the keyword list's conservativeness — a genuine, small QUERY/CLASSIFICATION gap, not forced open.

**Decision (per Te's explicit instruction): do NOT artificially force the classification rate
up.** The correct action is leaving the clearly off-topic majority as DOMAIN_UNKNOWN (accurate)
and accepting that a small number of borderline AI-adjacent documents remain unclassified as an
honest, bounded CLASSIFICATION_GAP rather than expanding the keyword list reactively from a tiny
sample (which risks exactly the keyword-overfitting failure mode this phase exists to avoid).

**Conclusion:** USEFUL_BUT_UNCLASSIFIED is working as designed — it is correctly catching
"complete metadata, but off-topic or borderline" documents, not hiding a real classifier bug.
