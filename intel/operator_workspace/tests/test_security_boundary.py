# O-1E Part 3 (Te spec section 47) -- Operator Boundary regression test. This codifies, as an
# automated regression, what the N-9B security audit (intel/phase_n9/n9b_security_audit.json)
# previously checked only by hand with a one-off grep over a built site/ directory: that no
# credential, vault full text, private debugging data, or raw environment data ever appears in
# the Operator UI's own rendered output (site/operator/**, as built by operator_ui.py). This test
# renders every Operator page directly (no filesystem build required) and scans the page source
# itself, so it runs in the normal test suite without needing a prior `site/` build step.
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import operator_ui as ou  # noqa: E402

# High-risk literal-credential patterns: real API keys, bearer tokens, AWS-style keys, or a
# "key: <value>"-shaped assignment. Deliberately narrow (literal secret shapes), not the broad
# word list the N-9B audit used (which flags editorial prose like "secret sauce" as noise).
_CREDENTIAL_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                      # AWS access key id
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                    # OpenAI/Anthropic-style secret key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                    # GitHub personal access token
    re.compile(r"(?i)authorization:\s*bearer\s+\S+"),      # a literal Authorization header value
    re.compile(r'(?i)"(api_key|apikey|client_secret|private_key)"\s*:\s*"[^"]+"'),
]

_FORBIDDEN_MARKERS = (
    "full_text", "vault_record", "private_research_vault",  # vault full text
    "GITHUB_TOKEN", "os.environ(",                             # raw environment data (the public
                                                                # "ENVIRONMENT=GITHUB_ACTIONS" run
                                                                # label is an intentional, documented
                                                                # provenance field, not raw env dump)
    "Traceback (most recent call last)",                      # private debugging data (stack trace)
)


def _all_operator_pages_html():
    docs = []
    for name, renderer in ou.PAGES.items():
        docs.append((name, renderer()))
    return docs


def test_operator_pages_contain_no_literal_credentials():
    for name, doc in _all_operator_pages_html():
        for pattern in _CREDENTIAL_PATTERNS:
            assert not pattern.search(doc), f"credential-shaped string found on operator page {name!r}"


def test_operator_pages_contain_no_vault_fulltext_or_env_or_debug_markers():
    for name, doc in _all_operator_pages_html():
        for marker in _FORBIDDEN_MARKERS:
            assert marker not in doc, f"forbidden marker {marker!r} found on operator page {name!r}"
