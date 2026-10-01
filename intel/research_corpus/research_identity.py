# N-1 -- Research identity extraction + canonical dedup. A document is RESEARCH only if a real
# research identity can be confirmed (DOI, arXiv ID, or a recognized research-repository source);
# "an article about a paper" is NEWS regardless of its current `category` tag.
import re

ARXIV_URL_RE = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(v\d+)?)", re.IGNORECASE)

# Source families that themselves constitute a research-repository identity signal (the actual
# paper feed, not a news outlet republishing about papers). Matches documents.json's real
# source_id prefixes for this corpus's arXiv feeds.
RESEARCH_REPOSITORY_SOURCE_PREFIXES = (
    "src_arxiv_", "src_rss_arxiv_", "src_crossref", "src_openalex", "src_semantic_scholar",
    "src_pubmed", "src_ssrn", "src_riss", "src_dbpia", "src_kci", "src_scienceon",
)

RESEARCH_STATUS_VALUES = ("RESEARCH_IDENTITY_CONFIRMED", "NEWS_ABOUT_RESEARCH", "NO_IDENTITY_NEWS")


def extract_identity(doc):
    """Returns (identity_type, identity_value) or (None, None). Checks DOI (field or
    _identifiers), then an arXiv ID parsed from canonical_url -- never fabricates an identifier
    that isn't actually present in the document's own data."""
    if doc.get("doi"):
        return "DOI", doc["doi"]
    for pair in (doc.get("_identifiers") or []):
        if pair[0] == "DOI" and pair[1].get("normalized"):
            return "DOI", pair[1]["normalized"]
    url = doc.get("canonical_url") or ""
    m = ARXIV_URL_RE.search(url)
    if m:
        return "ARXIV_ID", m.group(1)
    return None, None


def is_research_repository_source(doc):
    source_id = doc.get("source_id") or ""
    return any(source_id.startswith(p) for p in RESEARCH_REPOSITORY_SOURCE_PREFIXES)


def classify_research_status(doc):
    """RESEARCH_IDENTITY_CONFIRMED: a real identifier exists, OR the source itself is a
    recognized research repository (arXiv feed etc.) even without a DOI (arXiv preprints
    routinely have no DOI). NEWS_ABOUT_RESEARCH: currently tagged papers/research but neither an
    identifier nor a repository source is present -- a news/media outlet writing about research.
    NO_IDENTITY_NEWS: not tagged as research at all."""
    identity_type, identity_value = extract_identity(doc)
    if identity_type:
        return "RESEARCH_IDENTITY_CONFIRMED", identity_type, identity_value
    if is_research_repository_source(doc):
        return "RESEARCH_IDENTITY_CONFIRMED", "SOURCE_REPOSITORY", doc.get("source_id")
    if (doc.get("category") or "") in ("papers", "research"):
        return "NEWS_ABOUT_RESEARCH", None, None
    return "NO_IDENTITY_NEWS", None, None


def canonical_fingerprint(doc):
    """Fallback identity when no DOI/arXiv ID/repository source exists -- used ONLY to detect
    exact duplicates, never to merge two different real papers on a normalized-title guess
    alone (Te's explicit instruction)."""
    return doc.get("content_hash")


def group_by_research_identity(documents):
    """documents: {doc_id: doc}. Returns {identity_key: [doc_id, ...]} for confirmed-identity
    docs only -- the actual dedup surface. A single doc with no identity is never grouped with
    another by title similarity alone."""
    groups = {}
    for doc_id, doc in documents.items():
        status, id_type, id_value = classify_research_status(doc)
        if status != "RESEARCH_IDENTITY_CONFIRMED" or id_type == "SOURCE_REPOSITORY":
            continue
        key = f"{id_type}:{id_value}"
        groups.setdefault(key, []).append(doc_id)
    return {k: v for k, v in groups.items() if len(v) > 1}
