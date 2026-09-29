# STAGE 7 PHASE G — Claude Adapter. 독립 모듈, optional, cached, budgeted (섹션 9, 59).
# 섹션 2 RUNTIME/API ENVIRONMENT CHECK 결과 (2026-09-29, 이 sandbox 기준):
#   - repository .github/workflows/*.yml에는 ANTHROPIC_API_KEY/CLAUDE_API_KEY wiring이
#     아예 없다(기존 컨벤션 없음) - GEMINI_KEY/DEEPL_KEY/MS_TRANSLATOR_KEY만 secrets.*로
#     주입되는 패턴이 있다(daily.yml env: NAME: ${{ secrets.NAME }}).
#   - 이 sandbox 프로세스 환경에도 ANTHROPIC_API_KEY가 없다(존재 여부만 확인 - 값은 절대
#     출력/로그/저장하지 않는다).
#   - Stage 7은 Private/on-demand 시스템이라(섹션 58 계열, knowledge_memory와 동일 원칙)
#     daily.yml cron에 새로 연결하지 않는다 - 이 Adapter는 기본 contract로
#     ANTHROPIC_API_KEY 환경변수를 읽고, 없으면 NOT_CONFIGURED로 안전하게 후퇴한다.
import os

STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_CONFIGURED = "CONFIGURED"
STATUS_CALL_FAILED = "CALL_FAILED"


def adapter_status():
    """API KEY VALUE는 여기서도, 어디서도 반환/로그하지 않는다 - 존재 여부만 반환."""
    return STATUS_CONFIGURED if os.environ.get("ANTHROPIC_API_KEY") else STATUS_NOT_CONFIGURED


def call_claude(system_prompt, user_prompt, model, max_tokens=2000, client_factory=None):
    """실제 Claude API 호출. client_factory는 테스트에서 실제 네트워크 호출 없이
    주입하기 위한 의존성 - 프로덕션에서는 None으로 두면 anthropic SDK를 사용한다.
    실패(키 없음/SDK 없음/네트워크 오류) 시 예외를 던지지 않고 RETRIEVAL_ONLY 상태를
    반환한다(섹션 61: Claude API 실패 시 Ask METAXIS 전체 실패 금지)."""
    if adapter_status() == STATUS_NOT_CONFIGURED and client_factory is None:
        return {"status": STATUS_NOT_CONFIGURED, "text": None, "usage": None}

    try:
        if client_factory is not None:
            client = client_factory()
        else:
            import anthropic  # 지연 import - Adapter 없이도 나머지 시스템은 동작해야 함
            client = anthropic.Anthropic()

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        usage = {
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
        }
        return {"status": STATUS_CONFIGURED, "text": text, "usage": usage, "model": model}
    except Exception as exc:  # noqa: BLE001 - 섹션 61: 어떤 실패든 전체 실패로 번지면 안 됨
        return {"status": STATUS_CALL_FAILED, "text": None, "usage": None, "error": type(exc).__name__}
