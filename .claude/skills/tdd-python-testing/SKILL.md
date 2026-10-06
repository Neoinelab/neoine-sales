---
name: tdd-python-testing
description: backend 기능을 구현하기 전에 pytest 테스트를 먼저 작성하거나, 유스케이스용 Fake Port(InMemory UoW/Repository)와 계약 테스트, 임시 DB 통합 테스트를 만들 때 사용한다. red→green 절차, 테스트 네이밍, 환경변수 격리 방법을 제공한다. 프로덕션 코드 구현 방법, 린트 오류 수정, 프론트엔드 테스트에는 사용하지 않는다.
---

# TDD와 파이썬 테스트

테스트를 먼저 쓰고(red), 최소 구현으로 통과시킨 뒤(green), 정리한다(refactor). 구현자가 테스트를 약하게 고쳐 통과시키는 것을 막는 것이 이 Skill의 핵심입니다. 규칙의 정본은 `docs/dev-guide.html` 13장과 `backend/pyproject.toml`입니다.

## 사용 조건

- 사용: 새 동작을 구현하기 전, 버그 재현 테스트를 쓸 때, Fake Port/계약 테스트/통합 테스트를 만들 때
- 사용하지 않음: 프로덕션 코드 작성 자체(`layer-architecture-rules`), 린트·타입 오류 수정, 프론트엔드 테스트

## 절차 (red → green → refactor)

1. **수락 기준 확인**: 계획(`artifacts/10-analysis/01-plan.md`)이나 사용자 요청에서 "무엇이 되면 완료인가"를 테스트 목록으로 옮긴다. 기준이 모호하면 추측하지 말고 질문한다.
2. **테스트 먼저 작성**: 층을 고른다(아래 표). 새 테스트는 반드시 **실패(red)** 해야 한다. 실행해서 실패 사유가 "아직 구현 없음"인지 확인한다. 처음부터 통과하면 테스트가 약한 것이다.
3. **최소 구현**(구현 담당): 테스트를 통과시키는 최소 코드를 쓴다. **테스트를 수정해 통과시키지 않는다.** 테스트가 틀렸다고 판단되면 테스트 담당에게 근거와 함께 보고한다.
4. **green 확인 후 정리**: 중복 제거, 책임 분리. 정리 후에도 전체 테스트가 통과해야 한다.
5. **게이트**: `uv run python scripts/run_gates.py`로 전체 검증한다.

## 테스트 층

| 층 | 대상 | 방식 | 위치 |
| --- | --- | --- | --- |
| 단위 | domain, application | DB·네트워크 없음, **Fake Port** 사용 | `backend/tests/unit/` |
| 통합 | infra(Repository, 마이그레이션, 외부 어댑터) | 실제 PostgreSQL의 테스트 전용 임시 DB | `backend/tests/integration/` |
| E2E/API | web 전 구간 | `httpx` ASGI 전송, 스모크 수준 | `backend/tests/e2e/` |

- 비율 목표: 단위 약 70%, 통합 약 20%, E2E 약 10%.
- DB를 목킹하지 않는다. 통합 테스트는 실제 PostgreSQL을 쓴다(`references/db-fixtures.md`).
- Mock보다 Fake를 우선한다(호출 횟수가 아니라 **결과**를 검증). Fake 예는 `references/fakes.md`.

## 규칙

- **이름은 영문 ASCII**: `test_<상황>_<기대결과>` (예: `test_product_rejects_debug_enabled`). 한글 함수명은 Ruff(N802, PLC2401)가 거부한다.
- 구조는 Arrange–Act–Assert. 한 테스트는 한 가지 동작만 검증한다.
- 환경변수를 읽는 코드는 `monkeypatch`로 격리한다. `APP_*` 변수를 모두 지우고 필요한 것만 설정하며 `tmp_path`로 cwd를 옮겨 실제 `.env`를 읽지 않게 한다(`backend/tests/unit/test_settings.py`가 모범 예).
- 비밀 값을 테스트 코드에 쓰지 않는다. 더미 값만 쓴다.
- 파일은 테스트 대상 모듈과 1:1로 나누고 공통 준비 코드는 `conftest.py`·factory로 옮긴다(파일 길이 제한 적용).
- 테스트에서는 Ruff가 `S101`(assert), `PLR2004`(매직 넘버)를 허용한다(`pyproject.toml`의 per-file-ignores). 그 외 규칙은 동일하게 적용된다.

## 품질 기준

- 새 동작마다 실패→통과 증거가 있다(red 단계 출력 또는 기록).
- 새 Port마다 Fake 구현이 있고, 가능하면 Fake와 실제 구현 모두에 같은 계약 테스트가 돈다.
- 커버리지 목표: 전체 80% 이상, domain/application 90% 이상. **현재 `pyproject.toml`에는 하한(`--cov-fail-under`)이 설정되어 있지 않다.** 첫 기능 코드가 생기면 하한 추가를 사용자와 확인한다.
- 결과 보고에는 실행한 명령, 통과/실패 수, red 증거, 실행하지 못한 테스트(미검증)를 구분해 적는다.

## 참조 (필요할 때만 읽는다)

- `references/fakes.md`: Fake UoW/Repository 예와 계약 테스트 패턴
- `references/db-fixtures.md`: 통합 테스트용 임시 DB fixture 설계(구현 시점 안내 포함)
