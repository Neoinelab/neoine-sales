"""Deal 목록(DL) BDD 케이스 — CSV 내보내기 HTTP: 응답 헤더·BOM·CRLF·검증 422·권한·경로 해석.

라우터·스키마·CSV 직렬화를 `FakeUseCases`(Fake UoW) 위에서 TestClient 호출 하나(When)로 본다.
조건·정렬·칸 값 규칙은 `unit/application/test_deal_export_cases.py`가 본다.
케이스 정의: docs/features/deal-list.md 4절(DL-117~DL-119).
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from app.domain.deal.code import DealCode
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_create_input
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.support.user_ids import ACTOR_ID
from tests.unit.web.vendor_http import client_for, problem

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

URL = "/api/v1/deals/export"
BOM = b"\xef\xbb\xbf"
HEADER_LINE = (
    "Deal,담당자,고객사,파트너사,Vendor,Product,Status,Forecast,금액(단위:원),"
    "Expected Close,최종 업데이트,Next Action,Due,Next Action 상태"
)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")  # Fake 시계 2026-01-01 09:00Z = 서울 2026-01-01 18:00


def _use_cases() -> FakeUseCases:
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    return use_cases


async def _register(use_cases: FakeUseCases, **overrides: Any) -> str:  # noqa: ANN401
    await use_cases.seed_user("owner", Role.SALES)
    owner_id = await use_cases.user_id_of("owner")
    view = await use_cases.register_deal().execute(
        make_create_input(owner_user_id=owner_id, **overrides), SALES
    )
    return view.item.deal.id.value


async def _export(http: AsyncClient, params: Any = None) -> Any:  # noqa: ANN401
    return await http.get(URL, params=params)


async def test_response_is_a_utf8_csv_attachment_with_bom_crlf_and_quoted_cells() -> None:
    """응답은 text/csv·BOM·CRLF·파일 이름 Deals_YYYYMMDD.csv이고 특수 문자 칸은 따옴표로 감싼다.

    테스트 코드: DL-117
    """
    # given: 업무 날짜 2026-01-01, Deal 이름 `A, "B"`, Next Action 내용에 줄바꿈이 든 Deal
    use_cases = _use_cases()
    code = await _register(use_cases, name='A, "B"')
    await use_cases.uow.deal_actions.add(
        make_deal_action(
            deal_code=DealCode(code),
            now=use_cases.clock.now(),
            actor_user_id=ACTOR_ID,
            next_action="1행\n2행",
            due_date=date(2026, 1, 20),
        )
    )
    async with client_for(use_cases) as http:
        # when: GET /deals/export
        response = await _export(http)
    # then: 200 + 헤더(대문자 D, 같은 이름의 filename*)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"Deals_20260101.csv\"; filename*=UTF-8''Deals_20260101.csv"
    )
    # then: 첫 세 바이트 BOM, 머리글·데이터 줄 끝 CRLF(칸 안의 줄바꿈은 LF 그대로)
    body = response.content
    assert body.startswith(BOM)
    assert body.endswith(b"\r\n")
    assert body.count(b"\r\n") == 2
    text = body[3:].decode("utf-8")
    assert text.startswith(HEADER_LINE + "\r\n")
    # then: 쉼표·따옴표가 든 이름 칸과 줄바꿈이 든 Next Action 칸만 따옴표로 감싼다
    assert text.split("\r\n")[1].startswith('"A, ""B""",')
    assert '"1행\n2행"' in text


async def test_response_without_deals_is_bom_and_a_single_header_line() -> None:
    """조건에 맞는 Deal이 없으면 BOM + 머리글 + CRLF뿐인 200이다.

    테스트 코드: DL-115
    """
    # given: Status zz인 Deal이 없다
    async with client_for(_use_cases()) as http:
        # when: status_key=zz로 내보낸다
        response = await _export(http, {"status_key": "zz"})
    # then: 200이고 본문이 정확히 그 세 조각이다
    assert response.status_code == 200, response.text
    assert response.content == BOM + (HEADER_LINE + "\r\n").encode()


async def test_over_the_row_limit_is_a_problem_json_not_a_csv() -> None:
    """상한 초과는 CSV가 아니라 422 invalid-value problem+json이다.

    테스트 코드: DL-116
    """
    # given: 내보내기 상한을 넘는 건수를 세는 저장소(count만 10,001)
    use_cases = _use_cases()

    async def too_many(_query: object) -> int:
        return 10_001

    use_cases.uow.deals.count = too_many  # type: ignore[assignment]
    async with client_for(use_cases) as http:
        # when: 내보낸다
        response = await _export(http)
    # then: 422 invalid-value와 서버 문구
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == (
        "내려받을 Deal이 10,000건을 넘습니다(10,001건). 조건을 좁혀 다시 시도하세요."
    )


@pytest.mark.parametrize(
    "params",
    [{"offset": 0}, {"limit": 20}, {"stage": "x"}, {"sort": "DESC"}],
)
async def test_unknown_paging_and_malformed_params_are_request_validation(
    params: dict[str, Any],
) -> None:
    """offset·limit·모르는 키·잘못된 정렬 값은 422 request-validation(problem+json)이다.

    테스트 코드: DL-118
    """
    # when: 그 쿼리로 내보낸다
    async with client_for(_use_cases()) as http:
        response = await _export(http, params)
    # then: 422 request-validation이고 CSV가 아니다
    problem(response, 422, "request-validation")
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_quarter_with_month_is_invalid_value() -> None:
    """분기와 월을 함께 보내면 목록과 같은 문구의 422 invalid-value다.

    테스트 코드: DL-118
    """
    # when: quarter=1&month=2로 내보낸다
    async with client_for(_use_cases()) as http:
        response = await _export(http, {"quarter": 1, "month": 2})
    # then: 422 invalid-value와 고정 문구
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."


async def test_keyword_with_nul_is_invalid_value() -> None:
    """키워드에 NUL이 있으면 목록과 같은 문구의 422 invalid-value다.

    테스트 코드: DL-118
    """
    # when: NUL이 든 키워드로 내보낸다
    async with client_for(_use_cases()) as http:
        response = await _export(http, {"keyword": "a\x00b"})
    # then: 422 invalid-value와 고정 문구
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == "검색어에는 NUL 문자를 쓸 수 없습니다"


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_a_csv_and_export_is_not_read_as_a_deal_code(role: Role) -> None:
    """세 역할 모두 내보낼 수 있고 export는 Deal code로 해석되지 않는다(404 아님).

    테스트 코드: DL-119
    """
    # given: Deal 1건
    use_cases = _use_cases()
    await _register(use_cases)
    async with client_for(use_cases, role=role) as http:
        # when: 역할마다 GET /deals/export
        response = await _export(http)
    # then: 200 CSV이고 머리글 아래 데이터 줄이 하나다
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.count(b"\r\n") == 2


async def test_unauthenticated_export_is_401() -> None:
    """로그인 없이 내보내면 401 unauthenticated다.

    테스트 코드: DL-119
    """
    # when: 로그인 없이 GET /deals/export
    async with client_for(_use_cases(), role=None) as http:
        response = await _export(http)
    # then: 401 unauthenticated
    problem(response, 401, "unauthenticated")
