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
- backend 테스트는 두 종류뿐입니다: **단위 테스트**(함수·클래스 하나, `tests/unit/`)와 **functional test**(feature 하나의 end-to-end, HTTP API → 실제 DB·외부 통신, **BDD 형식** Feature/Scenario/Given–When–Then, `tests/functional/`). 상세는 `docs/dev-guide.html` 13장과 `tdd-python-testing` 스킬의 `references/bdd.md`. 프런트엔드는 적용 제외(Vitest 유지).
- 테스트는 feature에 정의된 기능이 제대로 동작하는지만 검증합니다. **경쟁(race)·동시성 테스트는 사용자가 명시적으로 제시한 상황에만** 만듭니다(계획·리뷰에 있어도 사용자 확인 없이는 만들지 않음).
- **개발 중에는 단위 테스트(`tests/unit`)만 실행**합니다(Agent·게이트 모두). functional을 포함한 전체 테스트는 Jenkins 빌드(dev·product 배포 전 Verify 단계)가 실행하며, 로컬 전체 실행(`--full`)과 반복 실행은 사용자가 요청할 때만 합니다. 새 functional test는 `--collect-only`로 수집 오류만 확인합니다.
- 테스트 함수 이름은 영문 ASCII(단위 `test_<상황>_<기대결과>`, functional `test_<시나리오>`), 테스트를 약하게 고쳐서 통과시키지 않습니다.

## 검증 명령 (backend/ 에서 실행)

```
uv run python scripts/run_gates.py          # 전체 게이트(ruff, format, mypy, import-linter, 파일 길이, pytest=단위 테스트만)
uv run python scripts/run_gates.py --only mypy
uv run python scripts/run_gates.py --full   # pytest 전체(functional 포함). 사용자가 요청할 때만
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
| 2026-10-13 | 딜 활동 이력 확장(`deal_actions`에 next_action·due_date·memo, title→action, content 제거), Deal 물리 삭제(활동·단계 이력 있으면 409), 프런트 동시 개편. 마이그레이션 `e3a9c41b7d52` 1개로 컬럼 rename·행 정리를 한 번에 적용해 **expand/contract 원칙의 예외**(사용자가 명시 승인, 개발 단계, 앱과 같은 배포 전제) | `backend/alembic/`, `artifacts/` | 개발 중이라 2단계 분리보다 단순성을 택함. product 적용 전 백업·구 앱 비호환 확인 필수 |
| 2026-10-13 | 모든 테이블의 소프트 삭제 제거(customers·partners·deals·deal_actions·users의 `deleted_at` 컬럼 drop, 삭제는 물리 삭제, 고객·파트너는 참조 Deal이 있으면 409, users 유니크 인덱스를 일반 유니크로). 마이그레이션 `f4b8d2a6c9e1` 1개이며 삭제 표시 행이 있으면 데이터를 지우지 않고 중단하는 사전 점검 포함. 앞선 활동 이력 확장과 같이 **expand/contract 원칙의 예외**(사용자 명시 지시, 개발 단계, 앱과 같은 배포 전제) | `backend/alembic/`, `artifacts/` | 소프트 삭제를 쓰지 않기로 해 데드 컬럼·분기를 정리. product 적용 전 백업·구 앱 비호환 확인 필수 |
| 2026-10-14 | 사용자 참조를 `users.id` FK(RESTRICT)로 통일(딜 담당자·등록자, 활동자, 단계 변경자, 세션, 사용자·AD 설정 등록자 7곳)하고 스키마 점검 테스트 추가. 사용자만 퇴사 처리(소프트 삭제 `deleted_at`·`delete_reason`) 재도입: 연결이 있으면 퇴사, 없으면 물리 삭제, `login_id` DB 유니크 제거(재직자 중복은 앱 로직이 users 잠금 안에서 확인), 재입사는 새 행. 마이그레이션 `0d248153ec93` 1개이며 변환 불가 데이터가 있으면 중단하는 사전 점검 포함. 앞선 두 건과 같이 **expand/contract 원칙의 예외**(사용자 명시 지시, 개발 단계, 앱과 같은 배포 전제). 위 2026-10-13 '소프트 삭제 제거' 행의 'users 유니크'·'users 물리 삭제'는 이 행으로 대체됨 | `backend/alembic/`, `artifacts/` | 퇴사자가 목록에 남지 않으면서 이력은 보존. product 적용 전 백업·구 앱 비호환·변환 불가 데이터 점검 필수 |
| 2026-10-15 | PRD(`docs/prd.html`) 기반 P0~P8 구현 착수 결정: 개발 단계라 **보존할 업무 데이터가 없어 데이터 이전 마이그레이션을 만들지 않고**, 단계별 단일 스키마 마이그레이션(구 테이블 drop 허용)으로 진행하며 `/customers`·`/partners`·`/deal-actions` 등 구 API 폐지 승인. **expand/contract 원칙의 예외**(사용자 결정). 브랜치는 사용자가 직접 관리 | `backend/alembic/`, `artifacts/10-analysis/dev-roadmap-p0-plan.md` | 운영 데이터가 생기면 이 예외는 끝나고 expand/contract로 돌아간다 |
| 2026-10-15 | backend 테스트를 **단위 테스트**(함수·클래스 하나)와 **functional test**(feature end-to-end, 실제 DB·외부 통신, BDD 형식 Given–When–Then, 새 의존성 없이 step 함수)로 이원화. 구 층(contracts/integration/e2e)은 단위(Repository 계약·어댑터) 또는 functional(BDD)로 재작성·재배치. 프런트는 적용 제외 | `docs/dev-guide.html` 13장, `.claude/skills/tdd-python-testing/`(`references/bdd.md` 신규), `.claude/agents/{test,core,infra,web}-engineer.md`, `code-reviewer.md` | 사용자 요청. 테스트 목적(클래스 단위 검증 vs feature 동작 검증)을 분명히 하고 시나리오를 읽기 쉽게 |
| 2026-10-16 | 테스트 실행 시점 분리: 개발 중(게이트 기본값·모든 Agent)은 단위 테스트(`tests/unit`)만, functional 포함 전체는 Jenkins 빌드 Verify 단계(기존 `uv run pytest`, 변경 없음)가 실행. `run_gates.py`에 `--full` 추가, 새 functional test는 `--collect-only`만 | `backend/scripts/run_gates.py`, `tests/unit/test_run_gates.py`, `docs/dev-guide.html` 13장, `tdd-python-testing`, `.claude/agents/{test,infra,web}-engineer.md`, `quality-gate.md` | 사용자 요청. 전체 테스트(약 5분)를 개발 중 반복 실행해 작업이 수십 분씩 지연됨. functional 실패는 CI에서 드러남 |
| 2026-10-16 | P1(Deal 모델 재구성) 착수 결정: 단일 마이그레이션 M-P1이 `deals`를 `deal_code` PK로 재구성하고 `deal_stage_changes` drop, `/deals/pipeline` 폐지, Deal API 경로를 `/deals/{code}`로 변경, UserRef에 role 추가. 2026-10-15 결정과 같은 **expand/contract 원칙의 예외**(보존 데이터 없음) | `backend/alembic/`, `artifacts/10-analysis/p1-plan.md` | 사용자 결정(Q1~Q12 권고안 채택). dev 머지 시 기존 Deal 데이터 삭제 |
| 2026-10-16 | P2(Action) 착수 결정: 단일 마이그레이션 M-P2가 `deal_actions` 행을 지우고 Status/Forecast 스냅숏(codes 복합 FK)·NOT NULL 컬럼 추가, 진행사항·Next Action·Memo 길이 제한 제거(TEXT), `/deal-actions` 전역 검색 폐지, 수행일시·담당자는 서버가 채움(활동자 지정 제거), Action 수정·삭제는 담당자 본인·admin만. 2026-10-15 결정과 같은 **expand/contract 원칙의 예외**(보존 데이터 없음, 마이그레이션은 스키마 생성용 최소 작성) | `backend/alembic/`, `artifacts/10-analysis/p2-plan.md` | 사용자 결정(P2 Q1~Q9) |
| 2026-10-17 | P2b(첨부 파일) 완료: M-P2b(`storage_settings`·`deal_attachments`, 순수 expand), 저장 위치 설정과 최초 설정 3단계(AD → 저장 위치 → admin), 파일 이름 보안 규칙(유니코드 서식 문자 거부, 확장자 판정 전 끝 공백·점 정리, 차단 확장자 24개). 사용자 승인으로 `infra/server/**` 수정(systemd `ReadWritePaths=/var/lib/neoine-sales`, Nginx 업로드 경로만 101m·300s, `bootstrap.sh`가 저장 디렉터리 생성) — 서버 반영은 사람이 `bootstrap.sh` 재실행 | `backend/alembic/`, `infra/server/`, `artifacts/10-analysis/p2b-plan.md` | 사용자 결정(P2b Q1~Q6, 리뷰 후속 결정) |
| 2026-10-17 | P3(자동 규칙·경고) 완료: M-P3(`alert_settings` 테이블, `deals.status_changed_at`을 `created_at`으로 채운 뒤 NOT NULL — 구 앱과 같은 DB 공존 불가, 앱과 같은 배포 전제), 경고 기준 API(admin만 수정, 1~365일·기본 14), Deal 응답에 서버 계산 `risk`·`status_changed_at`·`status_days`(OS 로컬 업무 날짜), 프런트는 http 모드에서 서버 값을 그대로 사용(재계산 금지) | `backend/alembic/`, `artifacts/10-analysis/p3-plan.md` | 사용자 결정(P3 Q1~Q5 권고안) |
| 2026-10-17 | P5(Deals 목록 조회 조건 유지, 프런트 전용)·P8(실제 연동 전환) 완료: 앱 기본 게이트웨이를 HTTP로 고정하고 `VITE_GATEWAY`·`dev:http`·MockBanner·MockPanel 제거, `src/mock/**`를 테스트 전용 Fake(`src/test/fake/**`)로 이동(테스트는 `src/test/setup.ts`의 `vi.mock('../gateway')`로 주입), Forecast는 서버 501일 때만 "준비 중", 목록 BANT 열(12열), 빠른 로그인은 역할 라벨 3개. **머지 시 dev 배포 화면이 목업에서 실제 API로 바뀜**(dev 서버 DB·AD·저장 위치·최초 설정 3단계 준비 필요) | `frontend/`, `artifacts/10-analysis/{p5,p8}-plan.md` | 사용자 결정(P5 Q1~Q3, P8 전환·Q1~Q4·리뷰 후속) |
| 2026-10-16 | 테스트 범위 축소: feature에 정의된 기능 동작만 검증, 경쟁·동시성 테스트는 사용자가 명시적으로 제시할 때만. 리뷰어는 동시성 테스트 부재를 지적하지 않음 | `CLAUDE.md`, `docs/dev-guide.html` 13장, `tdd-python-testing`, `.claude/agents/{test-engineer,code-reviewer}.md` | 사용자 요청. 경쟁 테스트가 설계 모순·교착·flaky를 낳고 개발을 지연시킴 |
