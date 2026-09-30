# STAGE 7 PHASE L — module loader. Phase L builds no new knowledge/retrieval logic; it only
# exposes what operator_brain / knowledge_memory already compute as plain service functions.
# Both those packages are flat-module directories (no __init__.py, cross-module imports rely
# on sys.path containing their own directory - see operator_brain/adapter.py's own
# _load_km_module() for the same pattern this file follows). We must not put both
# operator_brain/ and knowledge_memory/ on sys.path at the same time: they both have same-named
# modules (adapter.py, schema.py, common.py, memory internals) and a bare `import adapter`
# would silently resolve to whichever one got there first via sys.modules caching. So:
#   - operator_brain modules are imported normally (bare import) with only operator_brain/
#     on sys.path - this matches how operator_brain's own tests/pipeline.py already import it.
#   - knowledge_memory modules we need (adapter.py, memory.py, exporter.py) are self-contained
#     (only stdlib imports, no cross-module `import adapter`/`import schema`), so we load them
#     in isolation via importlib.util under private, unique sys.modules keys - never touching
#     sys.path for knowledge_memory at all. This is the exact isolation technique
#     operator_brain/adapter.py already uses for the reverse direction.
import importlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OPERATOR_BRAIN_DIR = INTEL_DIR / "operator_brain"
KNOWLEDGE_MEMORY_DIR = INTEL_DIR / "knowledge_memory"
FORESIGHT_ENGINE_DIR = INTEL_DIR / "foresight_engine"


def _ensure_on_path(path):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


def load_operator_brain(name):
    """Bare-name module inside intel/operator_brain/, e.g. 'retriever', 'ask', 'pipeline',
    'evidence_sufficiency', 'context_builder', 'source_independence', 'view_revision',
    'claude_adapter'. Never imports knowledge_memory modules directly - operator_brain's own
    adapter.py already does that in isolation, and we reuse that, not reinvent it."""
    _ensure_on_path(OPERATOR_BRAIN_DIR)
    return importlib.import_module(name)


def _load_isolated(path, unique_name):
    key = f"_private_api_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def load_km_adapter():
    """knowledge_memory/adapter.py - read-only accessors over Stage 1-6 outputs
    (documents.json, facts_verified.json, production_events.json, changes.json,
    evidence_records.json). Self-contained (json + pathlib only)."""
    return _load_isolated(KNOWLEDGE_MEMORY_DIR / "adapter.py", "km_adapter")


def load_km_memory():
    """knowledge_memory/memory.py - load_notes()/load_relations() over notes.json/
    relations.json (the durable knowledge-note store). We only ever call the load_* readers
    from this module - never upsert_notes/upsert_relations (Phase L is read-only)."""
    return _load_isolated(KNOWLEDGE_MEMORY_DIR / "memory.py", "km_memory")


def load_foresight(name):
    """Bare-name module inside intel/foresight_engine/ (Phase M), e.g. 'coverage',
    'cross_domain', 'historical_analogy', 'intelligence_package', 'operator_view'. Its shared
    schema module is named 'foresight_schema.py' (not 'schema.py') specifically so it never
    collides with the schema.py every other intel/*_layer package ships - safe to keep on
    sys.path permanently alongside operator_brain, unlike knowledge_memory (see module
    docstring above)."""
    _ensure_on_path(FORESIGHT_ENGINE_DIR)
    return importlib.import_module(name)


def load_km_exporter():
    """knowledge_memory/exporter.py - note_to_markdown()/export_vault()/
    check_broken_internal_links(). Reused as-is; Phase L does not reimplement Obsidian
    formatting."""
    return _load_isolated(KNOWLEDGE_MEMORY_DIR / "exporter.py", "km_exporter")
