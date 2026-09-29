# STAGE 7 PHASE A — Query Parser. 자연어 질문을 정규화하고 query record를 만든다.
# 의미를 추측/재작성하지 않는다 - 정규화(공백/대소문자)만 수행(섹션 13: deterministic foundation).
from common import normalize_query, stable_query_id
from schema import ASK_MODES, new_query_record


def parse_query(question_text, mode, now_iso):
    assert mode in ASK_MODES, f"unknown mode: {mode}"
    qid = stable_query_id(question_text, mode, now_iso)
    record = new_query_record(qid, question_text, mode, now_iso)
    record["normalized_text"] = normalize_query(question_text)
    return record
