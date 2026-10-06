# neoine-sales

Python(FastAPI) 백엔드 + React 프론트엔드. 규칙의 정본은 `docs/dev-guide.html`, 설정·검증의 정본은 `backend/pyproject.toml`과 `backend/scripts/`입니다. 하네스 설계는 `docs/harness-guide.html`을 봅니다.

## 반드시 지킬 규칙 (요약)

- 계층: `web → application → domain`, `infra → application → domain`. application은 infra를 import하지 않고 외부 통신은 `application/ports`의 Port(Protocol)로만 합니다. infra가 Port를 구현합니다.
- backend의 `.py` 파일은 300줄 이하. 초과하면 책임별로 분리합니다(줄을 맞추려고 압축하지 않습니다).
- 모든 공개 함수에 타입 힌트, mypy strict 통과. 함수 복잡도·인자 수는 ruff 설정을 따릅니다.
- 프로파일은 `local` / `dev` / `product`. 설정은 `app.config.get_settings()`로만 읽고 domain/application에서 import하지 않습니다.
- 비밀과 `.env`는 읽지도 쓰지도 않습니다(필요한 변수 이름은 `backend/.env.example`). 의존성 추가(`uv add`)는 사용자 승인 후에만 합니다.
- 패키지·환경은 uv만 사용합니다(`pip install`, `python -m venv` 금지).
- DB 마이그레이션은 로컬 DB에만 실행합니다. dev/product 실행, 배포, 머지, push는 사람이 합니다. 커밋은 사용자가 요청할 때만 합니다.
- 테스트 함수 이름은 영문 ASCII(`test_<상황>_<기대결과>`), 테스트를 약하게 고쳐서 통과시키지 않습니다.

## 검증 명령 (backend/ 에서 실행)

```
uv run python scripts/run_gates.py          # 전체 게이트(ruff, format, mypy, import-linter, 파일 길이, pytest)
uv run python scripts/run_gates.py --only mypy
```

## 작업 방식 (하네스)

- 규칙 Skill: `layer-architecture-rules`(계층·Port·SOLID), `tdd-python-testing`(테스트 선행·Fake Port), `config-and-secrets`(프로파일·환경변수). 해당 작업을 하기 전에 먼저 읽습니다.
- 구현이 끝나면 `quality-gate` Agent(또는 위 게이트 명령)로 검증하고, 통과 증거 없이 "완료"라고 하지 않습니다.
- 한 줄 버그 수정·오타·질문은 하네스 없이 바로 처리합니다. 여러 계층에 걸친 기능은 먼저 계획(영향 계층, Port 시그니처, 테스트 목록)을 세우고 시작합니다.
- 승인이 필요한 행동(머지, 배포, 비로컬 마이그레이션, 비밀 변경, 의존성 추가, 공개 API 호환 깨짐)은 멈추고 사용자에게 묻습니다.
- 하네스가 만든 `.claude/hooks`가 `.env`·`uv.lock` 접근 차단, alembic 실행 확인, 편집 후 자동 포맷을 수행합니다. 막히면 우회하지 말고 사유를 사용자에게 알립니다.
- 라이브러리·프레임워크 사용법은 Context7 MCP로 최신 문서를 확인합니다.

## 주요 위치

- Agent: `.claude/agents/` · Skill: `.claude/skills/` · hooks: `.claude/hooks/` · 권한/hooks 설정: `.claude/settings.json`
- 실행 산출물(Git 제외): `artifacts/` (게이트 결과 `artifacts/30-review/gate.md`)
- 아직 없는 것(코드가 생긴 뒤 도입): `feature-dev-orchestrator`, `code-review-orchestrator`, 계층별 구현 Agent, 리뷰 Agent (로드맵은 `docs/harness-guide.html` 13장)

## 하네스 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
| --- | --- | --- | --- |
| 2026-10-06 | 1~2단계 초기 구성: 권한·hooks, `run_gates.py`, 규칙 Skill 3개, `quality-gate` Agent | 전체 | 개발 시작 전 규칙·검증·안전장치 확보 |
