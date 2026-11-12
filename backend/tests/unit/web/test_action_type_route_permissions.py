"""Action 유형 라우터의 권한: 조회는 모든 역할, 생성은 sales·admin, 변경·삭제 admin."""

import pytest

from app.domain.auth.principal import Role
from app.web.permissions import ADMIN_DENIED
from tests.support.ids import MISSING_ID
from tests.unit.web.action_type_http import URL, seeded_use_cases, type_id_of
from tests.unit.web.vendor_http import client_for, problem


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_may_list_action_types(role: Role) -> None:
    """모든 역할이 유형 목록을 볼 수 있다.

    테스트 코드: CL-025
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases(), role=role) as http:
        # when: 해당 역할이 유형 목록을 부른다
        response = await http.get(URL)

    # then: 200이고 8개다
    assert response.status_code == 200, response.text
    assert len(response.json()) == 8


async def test_user_cannot_create_a_type_and_nothing_is_saved() -> None:
    """user가 유형을 만들면 403이고 저장되지 않는다.

    테스트 코드: CL-029
    """
    # given: VIEWER(user)로 로그인
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.USER) as http:
        # when: '웨비나'를 만든다
        response = await http.post(URL, json={"name": "웨비나"})
        listed = (await http.get(URL)).json()

    # then: 403이고 목록에 '웨비나'가 없다
    assert response.status_code == 403, response.text
    assert "웨비나" not in [item["name"] for item in listed]


async def test_sales_cannot_rename_or_delete_and_gets_the_admin_required_message() -> None:
    """sales는 유형 이름 변경·삭제가 관리자 문구 403이고 유형은 그대로다.

    테스트 코드: CL-044
    """
    # given: sales로 로그인, 기본 유형 '데모'
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.SALES) as http:
        demo = await type_id_of(http, "데모")
        # when: '데모'의 이름 변경·삭제를 요청한다
        renamed = await http.patch(f"{URL}/{demo}", json={"name": "시연"})
        deleted = await http.delete(f"{URL}/{demo}")
        listed = (await http.get(URL)).json()

    # then: 둘 다 403 관리자 문구이고 '데모'가 남는다
    assert problem(renamed, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert problem(deleted, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert "데모" in [item["name"] for item in listed]


async def test_user_cannot_rename_or_delete() -> None:
    """user도 유형 이름 변경·삭제가 403이다.

    테스트 코드: CL-044
    """
    # given: user로 로그인, 기본 유형 '데모'
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.USER) as http:
        demo = await type_id_of(http, "데모")
        # when: '데모'의 이름 변경·삭제를 요청한다
        renamed = await http.patch(f"{URL}/{demo}", json={"name": "시연"})
        deleted = await http.delete(f"{URL}/{demo}")

    # then: 둘 다 403이다
    assert renamed.status_code == 403, renamed.text
    assert deleted.status_code == 403, deleted.text


async def test_the_permission_is_checked_before_the_id_is_looked_up() -> None:
    """권한 판정은 id 조회보다 먼저라 없는 id여도 sales는 403이다.

    테스트 코드: CL-044
    """
    # given: sales로 로그인
    async with client_for(seeded_use_cases(), role=Role.SALES) as http:
        # when: 없는 id의 이름 변경·삭제를 요청한다
        renamed = await http.patch(f"{URL}/{MISSING_ID}", json={"name": "x"})
        deleted = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 둘 다 404가 아니라 403이다
    problem(renamed, 403, "forbidden")
    problem(deleted, 403, "forbidden")


async def test_unauthenticated_requests_are_401() -> None:
    """로그인하지 않은 요청은 모두 401이다."""
    # given: 로그인하지 않은 클라이언트
    async with client_for(seeded_use_cases(), role=None) as http:
        # when: 네 경로를 부른다
        responses = [
            await http.get(URL),
            await http.post(URL, json={"name": "x"}),
            await http.patch(f"{URL}/{MISSING_ID}", json={"name": "x"}),
            await http.delete(f"{URL}/{MISSING_ID}"),
        ]

    # then: 모두 401 unauthenticated다
    for response in responses:
        problem(response, 401, "unauthenticated")
