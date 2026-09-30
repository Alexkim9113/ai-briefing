# STAGE 7 PHASE M — Operator View store (Te spec section 36-37). HUMAN-AUTHORED ONLY.
# Nothing in this repo's pipelines imports this module. It is invoked only by an explicit,
# human-triggered call (a future manual private_api write path, or a script Te runs by hand).
# Storage: flat JSON, append-only history per view, matching every other layer's own
# memory.py convention (never overwritten silently).
import json
from datetime import datetime, timezone
from pathlib import Path

from foresight_schema import new_operator_view_shell

HERE = Path(__file__).resolve().parent
STORE_PATH = HERE / "operator_views.json"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_views(path=None):
    path = path or STORE_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(views, path=None):
    path = path or STORE_PATH
    path.write_text(json.dumps(views, ensure_ascii=False, indent=1, sort_keys=True),
                     encoding="utf-8")


def create_operator_view(view_id, author, statement, linked_hypothesis_ids=None,
                          linked_evidence_ids=None, path=None):
    """The only way a view enters the store. `author` is required and must be a real human
    identifier (e.g. an email or operator name) - never a pipeline/system name."""
    if author in (None, "", "SYSTEM", "CODE_DETERMINISTIC", "PIPELINE"):
        raise ValueError("operator_view.create_operator_view requires a real human author")
    views = load_views(path)
    shell = new_operator_view_shell(view_id, author, statement, linked_hypothesis_ids,
                                     linked_evidence_ids)
    shell["history"] = [{"at": _now_iso(), "action": "CREATED", "author": author}]
    views[view_id] = shell
    _save(views, path)
    return shell


def link_evidence(view_id, evidence_id, author, path=None):
    """Append-only: adds one evidence link and one history entry, never rewrites prior
    history. Still requires a human author on every call."""
    if author in (None, "", "SYSTEM", "CODE_DETERMINISTIC", "PIPELINE"):
        raise ValueError("operator_view.link_evidence requires a real human author")
    views = load_views(path)
    if view_id not in views:
        raise KeyError(view_id)
    view = views[view_id]
    if evidence_id not in view["linked_evidence_ids"]:
        view["linked_evidence_ids"].append(evidence_id)
    view["history"].append({"at": _now_iso(), "action": "EVIDENCE_LINKED",
                             "author": author, "evidence_id": evidence_id})
    _save(views, path)
    return view


def get_view(view_id, path=None):
    return load_views(path).get(view_id)


def list_views(path=None):
    return list(load_views(path).values())
