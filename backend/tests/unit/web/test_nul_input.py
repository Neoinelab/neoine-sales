"""NUL 문자 입력은 500이 아니라 422다(PL-025, PL-026).

Action의 NUL 검증(등록 본문·검색어)은 소유 feature(AC) 테스트가 다룬다. 실제 PostgreSQL까지
가는 확인은 하지 않는다(테스트는 단위 테스트뿐).
"""

from typing import Any

from tests.support.deal_payload import deal_payload
from tests.unit.web.platform_http import KIM, role_clients, then_problem_is

NUL = "a\x00b"
DB_ERROR_TOKENS = ("asyncpg", "dbapierror", "sqlalchemy", "postgres", "0x00")


def _assert_no_driver_text(body: dict[str, Any]) -> None:
    detail = str(body.get("detail", "")).lower()
    assert not [token for token in DB_ERROR_TOKENS if token in detail], detail


async def test_nul_in_a_search_keyword_or_a_registration_body_is_422_invalid_value() -> None:
    """텍스트 검색어·등록 본문의 NUL 문자는 500이 아니라 422 invalid-value다.

    테스트 코드: PL-025
    """
    async with role_clients() as c:
        # given: KIM
        searched = await c[KIM].get("/api/v1/deals", params={"keyword": NUL})
        # when: Deal 목록 keyword에 NUL을 넣어 검색하고, Deal명에 NUL을 넣어 등록한다
        registered = await c[KIM].post("/api/v1/deals", json=deal_payload(name=NUL))
    # then: 둘 다 422 invalid-value이고 DB 드라이버·SQL 문구가 detail에 없다
    for response in (searched, registered):
        _assert_no_driver_text(then_problem_is(response, 422, "invalid-value"))


async def test_nul_in_an_integer_filter_is_422_request_validation() -> None:
    """정수 칸의 NUL 문자는 422 request-validation이다.

    테스트 코드: PL-026
    """
    # given: KIM
    async with role_clients() as c:
        # when: Deal 목록 owner_user_id에 NUL이 든 값을 넣어 검색한다
        response = await c[KIM].get("/api/v1/deals", params={"owner_user_id": NUL})
    # then: 422 request-validation이다
    _assert_no_driver_text(then_problem_is(response, 422, "request-validation"))
