# N-6 PRIORITY 1 -- Atomic Publish. GENERATE -> TEMP WRITE -> VALIDATE -> ATOMIC REPLACE for every
# publish boundary that can overwrite an existing, previously-valid artifact (Report JSON, Public
# HTML, Print HTML, PDF, Public Intelligence Detail page, Report Index). A brand-new, never-before-
# written version file (e.g. report_{id}_v{N}.json the first time v{N} is produced) is append-only
# and therefore already safe -- this module is for the overwrite-in-place boundaries only.
#
# Pattern: write candidate content to "<path>.tmp", validate it, then os.replace(tmp, path), which
# is atomic on POSIX. On ANY failure (write error or validation failure) the pre-existing file at
# `path` is left completely untouched and the .tmp file is removed. No new Report Engine, no new
# scoring/validation framework -- this wraps the existing validate_pdf()/JSON parsing with os.replace.
import json
import os
from pathlib import Path


class PublishValidationError(Exception):
    pass


def atomic_write(path, content, validator=None, encoding="utf-8"):
    """Writes `content` (str or bytes) to `path` atomically.

    validator(tmp_path) -- optional callable. Must return a truthy value (or None, meaning "no
    opinion, treat as pass") for success, or either return a falsy value or raise to signal
    failure. On failure, `path` is never touched and the .tmp file is removed.

    Returns a status dict: {"status": "PUBLISHED"|"PUBLISH_FAILED", "path": str, ["error": str]}.
    This function never raises -- callers can treat every publish boundary as failure-isolated,
    matching report_ops.py's existing ARTIFACT_STATES convention.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    is_bytes = isinstance(content, (bytes, bytearray))
    try:
        if is_bytes:
            tmp.write_bytes(content)
        else:
            tmp.write_text(content, encoding=encoding)
        if validator is not None:
            result = validator(tmp)
            if result is False:
                raise PublishValidationError(f"validation returned False for {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, path)  # atomic on POSIX -- either the old file or the new one, never partial
        return {"status": "PUBLISHED", "path": str(path)}
    except Exception as e:  # noqa: BLE001 -- failure isolation: never raise past a publish boundary
        try:
            tmp.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return {"status": "PUBLISH_FAILED", "path": str(path), "error": str(e)}


def json_validator(tmp_path):
    """Validates that the temp file is parseable JSON (and non-empty)."""
    text = Path(tmp_path).read_text(encoding="utf-8")
    data = json.loads(text)  # raises on malformed JSON -- caught by atomic_write()
    return data is not None


def html_validator(tmp_path):
    """Minimal well-formed-ish HTML check: non-empty, has a doctype/html open tag and a closing
    </html>. Not a full HTML parser -- this project does not build a new validation framework for
    content that product_html.py / operator_ui.py already render deterministically from templates."""
    text = Path(tmp_path).read_text(encoding="utf-8")
    if not text.strip():
        return False
    lower = text.lower()
    if "<html" not in lower or "</html>" not in lower:
        return False
    return True


def pdf_validator_factory(pp_module):
    """Returns a validator bound to the existing pdf_pipeline.validate_pdf() -- never a new PDF
    validation path."""

    def _validate(tmp_path):
        result = pp_module.validate_pdf(tmp_path)
        return bool(result.get("ok"))

    return _validate
