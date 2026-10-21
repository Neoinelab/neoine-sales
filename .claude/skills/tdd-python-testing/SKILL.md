---
name: tdd-python-testing
description: backend 기능을 구현하기 전에 pytest 테스트를 먼저 작성할 때 사용한다. 테스트는 단위 테스트(함수·클래스 하나, Fake Port·Repository 계약 포함)와 BDD 형식 functional test(feature 하나의 end-to-end, 실제 DB·외부 통신 포함) 두 가지다. red→green 절차, 네이밍, BDD step 작성법, 환경변수 격리 방법을 제공한다. 프로덕션 코드 구현 방법, 린트 오류 수정, 프론트엔드 테스트에는 사용하지 않는다.
---

# TDD와 파이썬 테스트

테스트를 먼저 쓰고(red), 최소 구현으로 통과시킨 뒤(green), 정리한다(refactor). 구현자가 테스트를 약하게 고쳐 통과시키는 것을 막는 것이 이 Skill의 핵심입니다. 규칙의 정본은 `docs/dev-guide.html` 13장과 `backend/pyproject.toml`입니다.

## 사용 조건

- 사용: 새 동작을 구현하기 전, 버그 재현 테스트를 쓸 때, 단위 테스트(Fake Port·Repository 계약 포함)와 BDD 형식 functional test를 만들 때
- 사용하지 않음: 프로덕션 코드 작성 자체(`layer-architecture-rules`), 린트·타입 오류 수정, 프론트엔드 테스트

## 절차 (red → green → refactor)

1. **수락 기준 확인**: 계획(`artifacts/10-analysis/01-plan.md`)이나 사용자 요청에서 "무엇이 되면 완료인가"를 테스트 목록으로 옮긴다. 기준이 모호하면 추측하지 말고 질문한다.
2. **테스트 먼저 작성**: 층을 고른다(아래 표). 새 단위 테스트는 반드시 **실패(red)** 해야 한다. 실행해서 실패 사유가 "아직 구현 없음"인지 확인한다. 처음부터 통과하면 테스트가 약한 것이다. 새 functional test는 개발 중에 실행하지 않고 `uv run pytest <파일> --collect-only -q`로 수집 오류만 확인한다(아래 "실행 시점").
3. **최소 구현**(구현 담당): 테스트를 통과시키는 최소 코드를 쓴다. **테스트를 수정해 통과시키지 않는다.** 테스트가 틀렸다고 판단되면 테스트 담당에게 근거와 함께 보고한다.
4. **green 확인 후 정리**: 중복 제거, 책임 분리. 정리 후에도 전체 테스트가 통과해야 한다.
5. **게이트**: `uv run python scripts/run_gates.py`로 검증한다(pytest는 단위 테스트만).

## 실행 시점 (2026-10-16 결정)

- **개발 중**(로컬, 모든 Agent 작업, 게이트 기본값): **단위 테스트(`tests/unit`)만** 실행한다. 대상만 좁혀 돌릴 때도 `tests/unit/...` 안에서 고른다.
- **functional test를 포함한 전체**: Jenkins 빌드(Verify 단계 `uv run pytest`)가 실행하고, 통과해야 `main`에서 product 배포(사람 승인 후)로 이어진다. 로컬에서는 사용자가 요청할 때만 `uv run python scripts/run_gates.py --full`.
- 새·변경 functional test는 개발 중 `--collect-only`로 수집(문법·import) 오류만 확인한다. 실패는 CI에서 드러나므로, CI 실패 보고를 받으면 같은 순서(테스트 → 담당 계층)로 고친다.

## 테스트 종류 (backend는 두 가지뿐)

| 종류 | 대상 | 방식 | 위치 |
| --- | --- | --- | --- |
| **단위 테스트** | **하나의 함수 또는 하나의 클래스**(엔티티·값 객체·도메인 서비스·유스케이스·Fake·Repository) | Arrange–Act–Assert. 기본은 DB·네트워크 없이 **Fake Port** 사용. 예외: infra 어댑터 클래스 하나(SQL Repository 등)는 실제 임시 DB로 검증하고 `pytestmark = pytest.mark.integration` | `backend/tests/unit/` (`domain/`, `application/`, `repositories/`(Fake↔SQL 계약), `infra/`, `web/`) |
| **functional test** | **하나의 feature의 end-to-end**: HTTP API(ASGI) → 유스케이스 → 실제 Repository → 실제 PostgreSQL, 외부 통신 포함 | **BDD 형식**(Feature / Scenario / Given–When–Then, step 함수). `pytestmark = pytest.mark.integration` | `backend/tests/functional/<영역>/test_<feature>.py`, step은 `backend/tests/functional/steps/` |

- 위 두 가지 외의 층(`contracts`, `integration`, `e2e`)은 새로 만들지 않는다. 마이그레이션 왕복·openapi 계약 검증도 feature 시나리오로 functional test에 둔다.
- **테스트 범위(2026-10-16 사용자 결정)**: feature에 정의된 기능이 제대로 동작하는지(정상·실패·권한·경계값)만 검증한다. **경쟁(race)·동시성 테스트는 만들지 않는다.** 사용자가 특정 경쟁 상황을 명시적으로 제시했을 때만 그 상황에 한해 만든다. 계획이나 리뷰 지적에 동시성 테스트가 들어 있어도 사용자 지시가 없으면 만들지 않고 "사용자 확인 필요"로 보고한다.
- DB를 목킹하지 않는다. 실제 PostgreSQL 임시 DB를 쓴다(`references/db-fixtures.md`).
- Mock보다 Fake를 우선한다(호출 횟수가 아니라 **결과**를 검증). Fake가 실제 구현과 같게 동작하는지는 `tests/unit/repositories/`의 계약 단위 테스트(같은 테스트를 Fake와 SQL에 실행)로 보장한다. Fake 예는 `references/fakes.md`.
- 외부 통신: functional test는 실제 어댑터까지 통과시킨다. 테스트에서 띄울 수 없는 외부 시스템(회사 AD 등)은 네트워크 경계 바깥을 테스트용 서버로 대체하고, 불가능하면 Port 대체를 허용하되 docstring에 사유를 적는다.
- 프런트엔드 테스트는 이 구분을 적용하지 않는다(Vitest 유지).

## 규칙

- **이름은 영문 ASCII**: 단위는 `test_<상황>_<기대결과>` (예: `test_product_rejects_debug_enabled`), functional은 `test_<시나리오>` (예: `test_admin_renames_locked_status_code`). 한글 함수명은 Ruff(N802, PLC2401)가 거부한다(docstring·주석은 한국어 가능).
- 단위 테스트 구조는 Arrange–Act–Assert, 한 테스트는 한 가지 동작만 검증한다.
- functional test는 **BDD 형식**을 지킨다(`references/bdd.md`): 모듈 docstring `Feature: …`, 테스트 docstring `Scenario: …`, 본문 `# Given` → `# When`(하나) → `# Then`, 단계는 `given_*`/`when_*`/`then_*` step 함수(When은 반드시 HTTP API 호출, Then은 관찰 가능한 결과). 새 의존성(pytest-bdd 등)은 쓰지 않는다.
- 환경변수를 읽는 코드는 `monkeypatch`로 격리한다. `APP_*` 변수를 모두 지우고 필요한 것만 설정하며 `tmp_path`로 cwd를 옮겨 실제 `.env`를 읽지 않게 한다(`backend/tests/unit/test_settings.py`가 모범 예).
- 비밀 값을 테스트 코드에 쓰지 않는다. 더미 값만 쓴다.
- 파일은 테스트 대상 모듈과 1:1로 나누고 공통 준비 코드는 `conftest.py`·factory로 옮긴다. 300줄 제한은 테스트에 적용하지 않으므로 길이만을 이유로 쪼개지 않는다.
- 테스트에서는 Ruff가 `S101`(assert), `PLR2004`(매직 넘버)를 허용한다(`pyproject.toml`의 per-file-ignores). 그 외 규칙은 동일하게 적용된다.

## 품질 기준

- 새 동작마다 실패→통과 증거가 있다(red 단계 출력 또는 기록).
- 새 Port마다 Fake 구현이 있고, 가능하면 Fake와 실제 구현 모두에 같은 계약 테스트가 돈다.
- 커버리지 목표: 전체 80% 이상, domain/application 90% 이상. **현재 `pyproject.toml`에는 하한(`--cov-fail-under`)이 설정되어 있지 않다.** 첫 기능 코드가 생기면 하한 추가를 사용자와 확인한다.
- 결과 보고에는 실행한 명령, 통과/실패 수, red 증거, 실행하지 못한 테스트(미검증)를 구분해 적는다.

## 참조 (필요할 때만 읽는다)

- `references/fakes.md`: Fake UoW/Repository 예와 계약 테스트 패턴
- `references/db-fixtures.md`: 실제 임시 DB fixture(구현됨) 사용법, 건너뜀·실패 기준, 새 구현에 계약 테스트 적용하는 법
- `references/bdd.md`: functional test의 BDD 형식(Feature/Scenario/Given–When–Then, step 함수 작성법과 예)
