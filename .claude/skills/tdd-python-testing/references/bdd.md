# functional test의 BDD 형식

functional test는 **하나의 feature를 end-to-end로** 검증한다. HTTP API(httpx ASGI 전송) → 유스케이스 → 실제 Repository → 실제 PostgreSQL 임시 DB를 모두 통과한다. 새 의존성(pytest-bdd 등) 없이 pytest만으로 BDD 형식을 지킨다. 정본은 `docs/dev-guide.html` 13.1절.

## 목차

1. 파일·함수 구조
2. step 함수 규칙
3. 예시
4. 외부 통신
5. 체크리스트

## 1. 파일·함수 구조

| 요소 | 규칙 |
| --- | --- |
| Feature | 파일 하나 = feature 하나. `tests/functional/<영역>/test_<feature>.py`. 모듈 docstring 첫 줄 `Feature: <사용자 관점 기능 설명>` |
| Scenario | 테스트 함수 하나 = 시나리오 하나. 이름 `test_<시나리오>`(영문 ASCII), docstring 첫 줄 `Scenario: <한 문장>` |
| 단계 | 본문은 `# Given` → `# When` → `# Then` 주석으로 구분. **When은 정확히 하나**(한 시나리오 = 한 행동). `And`가 필요하면 같은 단계 안에서 step 함수를 더 호출 |
| 마커 | 모듈에 `pytestmark = pytest.mark.integration`(실제 DB 필요). 건너뛴 수 0을 확인 |
| 픽스처 | `api`(로그인 상태를 바꿀 수 있는 ASGI 클라이언트 래퍼)와 임시 DB 픽스처는 `tests/functional/conftest.py`에 둔다 |

## 2. step 함수 규칙

- 위치: `tests/functional/steps/<영역>.py`(예: `auth.py`, `codes.py`, `contacts.py`, `deals.py`). 여러 feature가 재사용한다.
- `given_*`: 사전 상태를 만든다. 가능하면 **공개 API로** 만들고(사용자가 실제로 하는 방법), API가 없는 상태만 DB에 직접 넣는다.
- `when_*`: 검증 대상 행동. **반드시 HTTP API를 호출**하고 응답을 반환한다. 유스케이스나 Repository를 직접 부르지 않는다.
- `then_*`: **관찰 가능한 결과**만 단언한다 — 상태 코드·응답 본문(Problem `type` 포함)·다른 API로 다시 조회한 결과·필요하면 DB 상태. 내부 호출 순서나 private 함수는 검증하지 않는다.
- step 이름은 영어 동사구, 인자는 키워드로 의미가 드러나게(`given_deal_exists(api, owner="kim", forecast="won")`).
- 한 step 함수는 한 가지 일만 한다. 시나리오 본문에 조건문·반복문을 두지 않는다(필요하면 `pytest.mark.parametrize`로 시나리오를 나눈다).

## 3. 예시

```python
# tests/functional/admin/test_status_codes.py
"""Feature: admin은 Status 코드의 이름과 순서를 관리하고, 시스템 코드는 지울 수 없다."""

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    then_code_exists,
    then_problem_is,
    when_delete_code,
)

pytestmark = pytest.mark.integration


async def test_admin_cannot_delete_locked_status_code(api):
    """Scenario: 참조가 없어도 잠긴 Status 코드(계약완료)는 삭제할 수 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_code(api, kind="status", key="contract_completed")
    # Then
    then_problem_is(response, status=409, type_suffix="code-locked")
    await then_code_exists(api, kind="status", key="contract_completed")
```

```python
# tests/functional/steps/codes.py
async def when_delete_code(api, *, kind: str, key: str):
    return await api.delete(f"/api/v1/codes/{kind}/{key}")


def then_problem_is(response, *, status: int, type_suffix: str) -> None:
    assert response.status_code == status
    assert response.json()["type"].endswith(type_suffix)
```

## 4. 외부 통신

- 원칙: 실제 어댑터(예: LDAP 클라이언트, 파일 저장소)를 그대로 통과시킨다.
- 테스트 환경에서 띄울 수 없는 외부 시스템(회사 AD)은 네트워크 경계 바깥을 테스트용 서버로 대체한다. 그것도 불가능하면 Port 구현만 테스트 대역으로 바꾸고, 시나리오 docstring에 "외부 대체: <사유>"를 적는다.
- 파일 저장은 `tmp_path` 아래 실제 디렉터리를 쓴다.

## 5. 체크리스트

- [ ] Feature/Scenario docstring이 있고 사용자 관점 문장이다
- [ ] Given/When/Then 주석과 step 함수로 구분되어 있고 When이 하나다
- [ ] When이 HTTP API를 호출한다
- [ ] Then이 관찰 가능한 결과만 검증한다
- [ ] 정상·실패(검증 422/충돌 409/없음 404)·권한(403) 시나리오가 feature마다 있다
- [ ] `integration` 마커, 건너뜀 0
