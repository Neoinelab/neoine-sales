"""Vendor 라우터의 권한: 읽기는 모든 역할, 쓰기는 admin만(403), 미로그인은 401."""

import pytest

from app.domain.auth.principal import Role
from app.web.permissions import ADMIN_DENIED
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import new_id
from tests.unit.web.vendor_http import URL, client_for, make_vendor, problem


def _writes(vendor_id: object) -> list[tuple[str, str, dict[str, str] | None]]:
    return [
        ("POST", URL, {"name": "X"}),
        ("PATCH", f"{URL}/{vendor_id}", {"name": "X"}),
        ("DELETE", f"{URL}/{vendor_id}", None),
    ]


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_sales_and_user_cannot_change_vendors_and_nothing_is_saved(role: Role) -> None:
    """sales·user는 Vendor 등록·이름 변경·삭제가 403이고 Vendor는 그대로다.

    테스트 코드: CL-048
    """
    # given: admin이 'SAP'를 만들어 두었다
    use_cases = FakeUseCases()
    async with client_for(use_cases) as admin:
        vendor = await make_vendor(admin)
    async with client_for(use_cases, role=role) as http:
        # when: sales 또는 user가 등록·이름 변경·삭제를 요청한다
        responses = [
            await http.request(method, url, json=body)
            for method, url, body in _writes(vendor["id"])
        ]
        listed = (await http.get(URL)).json()

    # then: 모두 403이고 목록은 'SAP' 그대로다
    for response in responses:
        problem(response, 403, "forbidden")
    assert [v["name"] for v in listed] == ["SAP"]


async def test_sales_gets_the_admin_required_message() -> None:
    """sales가 Vendor를 만들면 관리자 권한 문구 403이다.

    테스트 코드: CL-048
    """
    # given: sales로 로그인
    async with client_for(FakeUseCases(), role=Role.SALES) as http:
        # when: Vendor를 만든다
        response = await http.post(URL, json={"name": "X"})

    # then: 403 관리자 문구다
    assert problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED


async def test_unauthenticated_requests_are_401() -> None:
    """로그인하지 않은 요청은 모두 401이다."""
    # given: 로그인하지 않은 클라이언트
    async with client_for(FakeUseCases(), role=None) as http:
        # when: Vendor 읽기·쓰기 경로를 부른다
        responses = [await http.get(URL)]
        for method, url, body in _writes(new_id()):
            responses.append(await http.request(method, url, json=body))

    # then: 모두 401 unauthenticated다
    for response in responses:
        problem(response, 401, "unauthenticated")
