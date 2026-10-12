# neoine-sales

Python(FastAPI) 백엔드 + React 프론트엔드. 규칙의 정본은 `docs/dev-guide.html`, 설정·검증의 정본은 `backend/pyproject.toml`과 `backend/scripts/`입니다. 하네스 설계는 `docs/harness-guide.html`을 봅니다.

## 반드시 지킬 규칙 (요약)

- 계층: `web → application → domain`, `infra → application → domain`. application은 infra를 import하지 않고 외부 통신은 `application/ports`의 Port(Protocol)로만 합니다. infra가 Port를 구현합니다.
- backend의 `.py` 파일은 300줄 이하. 초과하면 책임별로 분리합니다(줄을 맞추려고 압축하지 않습니다).
- 모든 공개 함수에 타입 힌트, mypy strict 통과. 함수 복잡도·인자 수는 ruff 설정을 따릅니다.
- 프로파일은 `local` / `dev` / `product`. 설정은 `app.config.get_settings()`로만 읽고 domain/application에서 import하지 않습니다.
- 비밀과 `.env`는 읽지도 쓰지도 않습니다(필요한 변수 이름은 `backend/.env.example`). 의존성 추가(`uv add`, `pnpm add`)는 사용자 승인 후에만 합니다.
- 패키지·환경은 uv만 사용합니다(`pip install`, `python -m venv` 금지).
- DB 마이그레이션 정책: **local과 dev는 자동**(dev는 `main` 머지 시 Jenkins 배포의 `deploy.sh`가 `alembic upgrade head`를 자동 실행), **product만 사람 승인 후** `deploy.sh`가 실행합니다. dev에 자동 적용되므로 마이그레이션은 항상 하위 호환(expand/contract)으로 작성합니다. `downgrade`/`stamp`는 환경과 무관하게 사용자 확인을 받고, product 대상 alembic 명령은 하네스가 거부합니다. 배포·머지·push는 사람이 합니다.
- 테스트 함수 이름은 영문 ASCII(`test_<상황>_<기대결과>`), 테스트를 약하게 고쳐서 통과시키지 않습니다.

## 검증 명령 (backend/ 에서 실행)

```
uv run python scripts/run_gates.py          # 전체 게이트(ruff, format, mypy, import-linter, 파일 길이, pytest)
uv run python scripts/run_gates.py --only mypy
```

프런트엔드(`frontend/`, pnpm): `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm build`. 백엔드 API를 바꾸면 `uv run python scripts/export_openapi.py`(backend) 후 `pnpm gen:api`(frontend)를 실행해 둘 다 커밋합니다. 로컬에서 corepack 서명 오류가 나면 `COREPACK_INTEGRITY_KEYS=0 corepack pnpm …`.

## 작업 방식 (하네스)

- **로직 구현은 아래 Agent가 각자 역할대로 합니다(필수).** 메인 세션은 조율만 하고, 맡길 수 있는 일을 직접 하지 않습니다. 순서와 담당:
  1. `feature-planner`: 계획 → `artifacts/10-analysis/01-plan.md` (중·대 변경은 사용자 확인 후 진행)
  2. `test-engineer`: 수락 기준을 **테스트로 먼저**, red 확인 → `artifacts/20-agent-outputs/02-tests.md`
  3. `core-engineer`: domain·application 로직과 Port 구현 → `artifacts/20-agent-outputs/core.md`
  4. `infra-engineer`: Port 구현체·ORM·마이그레이션(로컬 확인까지)·`container.py` → `infra.md`
  5. `web-engineer`: 라우터·스키마·오류 매핑·`openapi.json` 갱신 → `web.md`
  6. `frontend-engineer`: 화면·훅(`pnpm gen:api` 후 생성 타입 사용) → `frontend.md`
  7. `quality-gate`: 게이트 6/6 확인(프런트 변경은 `pnpm typecheck/lint/test/build`도) → `artifacts/30-review/gate.md`
  8. `code-reviewer`: 게이트 PASS 뒤 아키텍처·정확성·보안·컨벤션·통합 리뷰 → `artifacts/final/review-report.md`. Blocker·Major가 있으면 지적된 담당이 고치고 7~8단계를 다시 합니다
  - Agent에 일을 맡길 때는 목표, 입력 파일, 출력 파일, 수정 금지 범위를 모두 적습니다. 각 Agent는 자기 범위 밖 파일을 고치지 않고, 자기 결과를 스스로 합격 처리하지 않습니다.
  - 예외: 한 줄 버그 수정, 오타, 문서·설정만 바꾸는 작업, 질문은 Agent 없이 바로 처리합니다(게이트는 그대로 돌립니다).
- 규칙 Skill: `layer-architecture-rules`(계층·Port·SOLID), `tdd-python-testing`(테스트 선행·Fake Port), `config-and-secrets`(프로파일·환경변수). 해당 작업을 하기 전에 먼저 읽습니다.
- 구현이 끝나면 `quality-gate` Agent(또는 위 게이트 명령)로 검증하고, 통과 증거 없이 "완료"라고 하지 않습니다.
- 한 줄 버그 수정·오타·질문은 하네스 없이 바로 처리합니다. 여러 계층에 걸친 기능은 먼저 계획(영향 계층, Port 시그니처, 테스트 목록)을 세우고 시작합니다.
- **권한 설정(2026-10-07, 사용자가 직접 변경)**: `.claude/settings.json`의 확인(`ask`) 규칙에서 `uv add`, `git commit`, `git merge`를 제거했습니다. 도구가 묻지 않으므로 **사용자의 명시적 요청·승인 없이 실행하지 않는 것은 Claude의 책임입니다**: `uv add`/`pnpm add`는 승인된 패키지만, `git commit`은 사용자가 요청했을 때만, 머지·push·배포는 사람이 합니다. `uv remove`와 `pyproject.toml`·`mise.toml`·`Jenkinsfile`·`infra/server/**` 편집은 계속 도구가 묻고, `.env*`·`uv.lock` 직접 편집, `git push`, `git reset --hard`, `git clean`, `rm -rf`는 계속 차단됩니다. 이 설정을 Claude가 임의로 바꾸지 않습니다.
- 승인이 필요한 행동(머지, 배포, product 마이그레이션, 비밀 변경, 의존성 추가, 공개 API 호환 깨짐)은 멈추고 사용자에게 묻습니다.
- 하네스가 만든 `.claude/hooks`가 `.env`·`uv.lock` 접근 차단, product 대상 alembic 차단(downgrade/stamp는 확인), 편집 후 자동 포맷을 수행합니다. 막히면 우회하지 말고 사유를 사용자에게 알립니다.
- 라이브러리·프레임워크 사용법은 Context7 MCP로 최신 문서를 확인합니다.

## 주요 위치

- Agent(`feature-planner`, `test-engineer`, `core-engineer`, `infra-engineer`, `web-engineer`, `frontend-engineer`, `quality-gate`, `code-reviewer`): `.claude/agents/` · Skill: `.claude/skills/` · hooks: `.claude/hooks/` · 권한/hooks 설정: `.claude/settings.json`
- 실행 산출물(Git 제외): `artifacts/` (게이트 결과 `artifacts/30-review/gate.md`)
- 아직 없는 것: `feature-dev-orchestrator`(지금은 메인 세션이 위 순서로 조율), `release-checker` (로드맵은 `docs/harness-guide.html` 13장)

## 하네스 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
| --- | --- | --- | --- |
| 2026-10-06 | 1~2단계 초기 구성: 권한·hooks, `run_gates.py`, 규칙 Skill 3개, `quality-gate` Agent | 전체 | 개발 시작 전 규칙·검증·안전장치 확보 |
| 2026-10-07 | web 단계 반영: `scripts/export_openapi.py`(API 계약 파일 생성, 드리프트는 pytest가 검사), ruff가 `src/app/web/**`의 TC 규칙을 면제하고 pydantic 모델을 런타임 평가 대상으로 지정 | `backend/pyproject.toml`, `backend/scripts/` | FastAPI가 타입 힌트를 런타임에 해석 |
| 2026-10-07 | 인증·프런트엔드 단계: 프런트엔드 검증 명령(pnpm)과 API 타입 재생성 절차를 안내에 추가 | `CLAUDE.md` | 하네스 게이트(`run_gates.py`)는 backend 전용이라 frontend 검증 명령을 따로 안내 |
| 2026-10-07 | Jenkins CI: 루트 `Jenkinsfile`(Verify 병렬, Contract & Security, Package), `infra/build_release.sh`, CI 전용 `REQUIRE_INTEGRATION_DB`(DB 불가 시 skip 대신 실패) | `Jenkinsfile`, `infra/`, `backend/tests/support/skips.py` | CI의 조용한 skip 방지와 프런트엔드 빌드·계약 검증 자동화 |
| 2026-10-07 | 최소 구성 Agent 추가(`feature-planner`, `test-engineer`, `core-engineer`)와 리뷰 5역할을 겸하는 `code-reviewer`, 로직 구현 위임 순서를 `CLAUDE.md`에 규정 | `.claude/agents/`, `CLAUDE.md` | 구현자와 판정자 분리, 계획→테스트→구현→게이트→리뷰 절차의 반복 가능화 |
| 2026-10-07 | 계층별 구현 Agent 추가(`infra-engineer`, `web-engineer`, `frontend-engineer`), 구현 순서를 8단계로 확장 | `.claude/agents/`, `CLAUDE.md` | 메인 세션이 직접 맡던 infra·web·frontend 구현을 역할별로 분리 |
| 2026-10-07 | 사용자가 `settings.json`의 `ask`에서 `uv add`·`git commit`·`git merge`를 제거: 도구 확인 대신 규칙(요청·승인 시에만 실행)으로 유지한다고 명시 | `.claude/settings.json`, `CLAUDE.md` | 사용자의 권한 정책 변경(사용자가 직접 수행)을 문서에 반영 |
| 2026-10-08 | 서버 배포 자산 추가(`infra/server/`: deploy.sh, bootstrap.sh, systemd, Nginx, sudoers)와 Jenkins 배포 단계, deploy.sh 스크립트 테스트(CI `Infra scripts`) | `infra/server/`, `Jenkinsfile` | 운영에서 Nginx가 정적 파일 서빙 + `/api` 프록시로 한 주소로 제공(방식 A) |
| 2026-10-08 | 새 Agent 구조(planner → test → core → infra·web → frontend → gate → reviewer)로 딜 단계·파이프라인, 상세 보강, 고객·파트너 검색, 내 딜을 구현. 새 Agent는 세션 재시작 전에는 로드되지 않아 일반 에이전트가 Agent 정의 파일을 읽고 수행 | `.claude/agents/`, `artifacts/` | 첫 대형 기능으로 하네스 흐름 검증. 리뷰 지적은 같은 순서(테스트 먼저)로 수정 |
| 2026-10-13 | 역할별 권한·사용자 관리·AD(LDAP) 로그인 구현(OIDC 제거, AD 설정 DB 저장·2단계 최초 설정, ldap3 추가). 새 Agent 구조로 4라운드(도메인·영속화·어댑터 / 로그인 교체 / 사용자·설정·권한 / 프런트) 진행, 에이전트 중단 시 메인 세션이 상태 확인 후 재개하거나 좁은 범위로 재위임 | `.claude/agents/`, `artifacts/` | 인증 구조 교체와 권한 적용을 TDD·계층 분리로 검증 |
