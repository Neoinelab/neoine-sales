"""BANT Label 라우터의 권한: 조회는 모든 역할, 생성은 sales·admin, 이름 변경·삭제는 admin."""

import pytest

from app.domain.auth.principal import Role
from app.web.permissions import ADMIN_DENIED
from tests.support.ids import MISSING_ID
from tests.unit.web.bant_label_http import (
    BASELINE,
    URL,
    label_id_of,
    labels_of,
    seeded_use_cases,
)
from tests.unit.web.vendor_http import client_for, problem

READ_ONLY = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"


async def test_user_cannot_create_a_label_and_nothing_is_saved() -> None:
    """user가 Label을 만들면 읽기 전용 403이고 저장되지 않는다.

    테스트 코드: CL-005
    """
    # given: VIEWER(user)로 로그인
    async with client_for(seeded_use_cases(), role=Role.USER) as http:
        # when: need에 '규제 대응'을 만든다
        response = await http.post(URL, json={"category": "need", "name": "규제 대응"})
        count = len(await labels_of(http))

    # then: 403 forbidden 읽기 전용 문구이고 Label은 23개 그대로다
    assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert count == BASELINE


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_sales_and_user_cannot_rename_or_delete_even_their_own_label(role: Role) -> None:
    """sales·user는 Label 이름 변경·삭제가 관리자 403이다(자기가 만든 Label 포함).

    테스트 코드: CL-024
    """
    # given: KIM이 need '규제 대응'을 만들었다(user는 만들 수 없어 sales가 만든 것을 쓴다)
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.SALES) as kim:
        made = (await kim.post(URL, json={"category": "need", "name": "규제 대응"})).json()
    async with client_for(use_cases, role=role) as http:
        default = await label_id_of(http, "budget", "예산 없음")

        # when: 기본 '예산 없음'과 '규제 대응'의 이름 변경·삭제를 각각 요청한다
        responses = [
            await http.patch(f"{URL}/{default}", json={"name": "x"}),
            await http.delete(f"{URL}/{default}"),
            await http.patch(f"{URL}/{made['id']}", json={"name": "x"}),
            await http.delete(f"{URL}/{made['id']}"),
        ]
        names = [x["name"] for x in await labels_of(http)]

    # then: 모두 403 forbidden 관리자 문구이고 두 Label은 그대로다
    for response in responses:
        assert problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert "예산 없음" in names
    assert "규제 대응" in names


async def test_the_permission_is_checked_before_the_id_is_looked_up() -> None:
    """권한 판정은 id 조회보다 먼저라 없는 id여도 sales는 403이다."""
    async with client_for(seeded_use_cases(), role=Role.SALES) as http:
        # when: 없는 id의 이름 변경·삭제를 요청한다
        renamed = await http.patch(f"{URL}/{MISSING_ID}", json={"name": "x"})
        deleted = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 둘 다 403이다(404가 아니다)
    problem(renamed, 403, "forbidden")
    problem(deleted, 403, "forbidden")


async def test_unauthenticated_requests_are_401() -> None:
    """로그인하지 않은 요청은 모두 401이다."""
    async with client_for(seeded_use_cases(), role=None) as http:
        # when: 로그인 없이 네 경로를 부른다
        responses = [
            await http.get(URL),
            await http.post(URL, json={"category": "need", "name": "x"}),
            await http.patch(f"{URL}/{MISSING_ID}", json={"name": "x"}),
            await http.delete(f"{URL}/{MISSING_ID}"),
        ]

    # then: 모두 401 unauthenticated다
    for response in responses:
        problem(response, 401, "unauthenticated")
