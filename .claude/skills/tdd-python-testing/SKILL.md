---
name: tdd-python-testing
description: backend 기능을 구현하기 전에 pytest 테스트를 먼저 작성할 때 사용한다. 테스트는 단위 테스트뿐이다(2026-11-09 functional 폐지): feature 문서(docs/features)의 BDD 테스트 케이스를 Fake로 구현한 단위 테스트와, 그 밖에 필요한 함수·클래스 단위 테스트(Repository 계약 포함). red→green 절차, 네이밍, 한글 설명·테스트 코드 번호·given/when/then 주석 형식, 환경변수 격리 방법을 제공한다. 프로덕션 코드 구현 방법, 린트 오류 수정, 프론트엔드 테스트에는 사용하지 않는다.
---

# TDD와 파이썬 테스트

테스트를 먼저 쓰고(red), 최소 구현으로 통과시킨 뒤(green), 정리한다(refactor). 구현자가 테스트를 약하게 고쳐 통과시키는 것을 막는 것이 이 Skill의 핵심입니다. 규칙의 정본은 `docs/dev-guide.html` 13장과 `backend/pyproject.toml`입니다.

## 사용 조건

- 사용: 새 동작을 구현하기 전, 버그 재현 테스트를 쓸 때, feature 문서의 BDD 케이스를 단위 테스트로 옮길 때, Fake Port·Repository 계약 테스트를 만들 때
- 사용하지 않음: 프로덕션 코드 작성 자체(`layer-architecture-rules`), 린트·타입 오류 수정, 프론트엔드 테스트

## 절차 (red → green → refactor)

1. **수락 기준 확인**: 사용자가 확인한 feature 문서(`docs/features/<feature>.md`)의 BDD 테스트 케이스와 계획(`artifacts/10-analysis/01-plan.md`)을 테스트 목록으로 옮긴다. 기준이 모호하면 추측하지 말고 질문한다.
2. **테스트 먼저 작성**: 층을 고른다(아래 표). 새 단위 테스트는 반드시 **실패(red)** 해야 한다. 실행해서 실패 사유가 "아직 구현 없음"인지 확인한다. 처음부터 통과하면 테스트가 약한 것이다.
3. **최소 구현**(구현 담당): 테스트를 통과시키는 최소 코드를 쓴다. **테스트를 수정해 통과시키지 않는다.** 테스트가 틀렸다고 판단되면 테스트 담당에게 근거와 함께 보고한다.
4. **green 확인 후 정리**: 중복 제거, 책임 분리. 정리 후에도 전체 테스트가 통과해야 한다.
5. **게이트**: `uv run python scripts/run_gates.py`로 검증한다(pytest는 단위 테스트만).

## 실행 시점

- **개발 중**(로컬, 모든 Agent 작업, 게이트 기본값): `tests/unit`만 실행한다. 대상만 좁혀 돌릴 때도 `tests/unit/...` 안에서 고른다.
- Jenkins 빌드(Verify 단계 `uv run pytest`)도 같은 테스트(실제 DB가 필요한 `integration` 표시 단위 테스트 포함)를 실행하고, 통과해야 `main`에서 product 배포(사람 승인 후)로 이어진다.

## 테스트 종류 (backend는 단위 테스트 한 가지, 2026-11-09)

| 구분 | 대상 | 방식 | 위치 |
| --- | --- | --- | --- |
| **BDD 케이스 단위 테스트** | feature 문서의 business use case 케이스(테스트 코드 번호 있음) | 유스케이스 하나를 When으로 호출, 모든 Port는 **Fake**(`tests/fakes/`), DB·네트워크 없음, given/when/then 주석 | 주로 `tests/unit/application/`, web 규칙이면 `tests/unit/web/` |
| **그 밖의 단위 테스트** | 함수·클래스 하나(값 객체·엔티티·도메인 서비스·매퍼·Fake·어댑터) | Arrange–Act–Assert(주석은 given/when/then). 예외: infra 어댑터(SQL Repository·마이그레이션)는 실제 임시 DB로 검증하고 `pytestmark = pytest.mark.integration` | `tests/unit/{domain,application,repositories,infra,web}` |

- **functional test(`tests/functional/`, HTTP → 실제 DB end-to-end)는 폐지**되었다(2026-11-09 사용자 결정). 새로 만들지 않는다(기존 것은 단위 테스트로 옮긴 뒤 2026-11-12에 모두 삭제). `contracts`·`integration`·`e2e` 층도 만들지 않는다.
- **테스트 범위(2026-10-16 사용자 결정)**: feature에 정의된 기능이 제대로 동작하는지(정상·실패·권한·경계값)만 검증한다. **경쟁(race)·동시성 테스트는 만들지 않는다.** 사용자가 특정 경쟁 상황을 명시적으로 제시했을 때만 그 상황에 한해 만든다.
- 유스케이스 테스트는 Fake로, 실제 DB 동작은 Repository 계약 테스트(`tests/unit/repositories/`, 같은 테스트를 Fake와 SQL에 실행)로 보장한다. DB를 Mock으로 흉내 내지 않는다(`references/db-fixtures.md`).
- Mock보다 Fake를 우선한다(호출 횟수가 아니라 **결과**를 검증). Fake 예는 `references/fakes.md`.
- 프런트엔드(Vitest)도 BDD 케이스 구현과 주석 형식을 똑같이 따른다(Fake 게이트웨이 사용).

## 규칙

- **이름은 영문 ASCII**: `test_<상황>_<기대결과>` (예: `test_product_rejects_debug_enabled`). 한글 함수명은 Ruff(N802, PLC2401)가 거부한다.
- **주석 형식(필수, `references/bdd.md` 2절)**: 모든 테스트 함수에 ① docstring 첫 줄 한글 설명 ② BDD 케이스면 `테스트 코드: XX-001` ③ 본문 `# given: …`(없으면 생략) / `# when: …` / `# then: …` 한국어 주석.
- 한 테스트는 한 가지 동작만 검증한다(When 하나).
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
- `references/bdd.md`: BDD 케이스를 Fake 단위 테스트로 구현하는 법, 주석 형식, pytest·Vitest 예시, 체크리스트
