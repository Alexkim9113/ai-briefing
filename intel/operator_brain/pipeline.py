# STAGE 7 — 실행 진입점. 이번 커밋은 PHASE A(Query Foundation)만 구현한다 - 섹션 60의
# 구현 순서를 따른다. PHASE B(Retrieval) 이후는 별도 커밋/승인 후 진행.
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intent_classifier
import query_parser
import retriever
import scope_parser


def ask(question_text, mode):
    """PHASE A+B: query 정규화 -> intent 분류 -> scope 추출 -> retrieval(FACT/EVENT/CHANGE
    + provenance). Context Pack/Claude 호출은 이후 Phase에서 추가된다(섹션 60, 아직 미구현) -
    지금은 RETRIEVE 모드와 동일하게 항상 retrieval-only 결과만 반환한다(Claude=0)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    record = query_parser.parse_query(question_text, mode, now_iso)
    record["intent"] = intent_classifier.classify_intent(record["normalized_text"])
    record["scope"] = scope_parser.extract_scope(question_text)
    retrieval = retriever.retrieve(record["intent"], record["scope"])
    record["retrieval"] = retrieval
    return record


if __name__ == "__main__":
    import json
    demo = ask("최근 AI Agent 관련 중요한 Event는?", "RETRIEVE")
    print(json.dumps(demo, ensure_ascii=False, indent=1))
