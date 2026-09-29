# STAGE 7 PHASE F — synthetic tests (섹션 62): concept interface, mass-generation guard.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import concept_interface  # noqa: E402


def test_concept_object_shell_has_all_spec_fields():
    shell = concept_interface.new_concept_object_shell("c1", "AGENCY", "PHILOSOPHY")
    assert set(shell.keys()) == set(concept_interface.CONCEPT_OBJECT_FIELDS)
    assert shell["review_status"] == "CANDIDATE"


def test_no_curated_concepts_reports_ready_for_curated_knowledge_not_not_ready():
    assert concept_interface.readiness() == "READY_FOR_CURATED_KNOWLEDGE"


def test_retrieve_nonexistent_concept_returns_none_not_fabricated():
    assert concept_interface.retrieve_concept("does_not_exist") is None


def test_no_mass_llm_generation_function_exists():
    # 섹션 27: "Stage 7에서 LLM을 이용해 수천 개 Concept를 자동 생성하지 않는다" - 그런
    # 함수 자체가 모듈에 없어야 한다(있을 수 없다는 것을 코드 구조로 보장).
    assert not hasattr(concept_interface, "generate_concepts_with_llm")
    assert not hasattr(concept_interface, "auto_generate_concept_database")
