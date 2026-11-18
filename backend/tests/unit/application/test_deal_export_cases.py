"""Deal 목록(DL) BDD 케이스 — CSV 내보내기 유스케이스 `ExportDeals`.

`ExportDeals`를 When으로 부르고 Deal·연락처·사용자·코드·Action 저장소·시계는 모두 Fake다.
CSV 바이트(BOM·CRLF·따옴표)는 web 층이 만들므로 `unit/web/test_deal_export_http_cases.py`가 본다.
케이스 정의: docs/features/deal-list.md 4절(DL-111~DL-116).
"""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import make_deal_action
from tests.factories_auth import make_user
from tests.factories_contact import make_customer, make_partner
from tests.factories_deal import seed_deal
from tests.support.expect import raises_with
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage
    from tests.unit.application.deal_env import DealEnv

HEADER = (
    "Deal", "담당자", "고객사", "파트너사", "Vendor", "Product", "Status", "Forecast",
    "금액(단위:원)", "Expected Close", "최종 업데이트", "Next Action", "Due", "Next Action 상태",
)  # fmt: skip
TODAY_UTC = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)  # Asia/Seoul 2026-10-15 12:00


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")  # 업무 날짜 기준 시간대


def _set_today(env: DealEnv) -> None:
    """시계를 서버 업무 날짜 2026-10-15로 맞춘다."""
    env.clock.advance((TODAY_UTC - env.clock.now()).total_seconds())


def _names(page: DealPage) -> list[str]:
    return [view.item.deal.details.name for view in page.items]


async def _list_all(env: DealEnv, query: DealQuery) -> list[str]:
    """같은 조건의 목록을 limit 20으로 모든 페이지 이어 붙인 Deal 이름 순서."""
    names: list[str] = []
    offset = 0
    while True:
        page = await env.list.execute(replace(query, offset=offset, limit=20))
        names += _names(page)
        offset += 20
        if offset >= page.total:
            return names


async def test_export_lists_every_matching_deal_in_list_order_regardless_of_paging(
    env: DealEnv,
) -> None:
    """내보내기는 페이지와 무관하게 조건에 맞는 모든 Deal을 목록 정렬 순서로 낸다.

    테스트 코드: DL-111
    """
    # given: 업무 날짜 2026-10-15, Status a(introduction) Deal 25건(금액 일부 동일)과 다른
    # Status 3건
    _set_today(env)
    for index in range(25):
        await env.new_deal(
            name=f"A-{index:02d}", status_key="introduction", revenue_amount=(index % 5 + 1) * 1000
        )
    for index in range(3):
        await env.new_deal(name=f"B-{index}", status_key="prospecting")
    query = DealQuery(status_key="introduction", sort=DealSort.REVENUE_AMOUNT, order=SortOrder.ASC)
    # when: 그 조건·정렬로 내보낸다
    export = await env.export.execute(query)
    # then: 데이터 줄 25개이고 순서가 목록(20건씩 이어 붙임)과 같으며 다른 Status는 없다
    assert [row[0] for row in export.rows] == await _list_all(env, query)
    assert len(export.rows) == 25
    assert not any(row[0].startswith("B-") for row in export.rows)
    # then: 금액 오름차순이다
    amounts = [int(row[8].replace(",", "")) for row in export.rows]
    assert amounts == sorted(amounts)


async def test_export_interprets_mine_overdue_and_quarter_without_year_like_the_list(
    env: DealEnv,
) -> None:
    """내보내기의 조건 해석(내 딜만·기한초과·연도 없는 분기)은 목록과 같다.

    테스트 코드: DL-112
    """
    # given: 2026-10-15. KIM의 기한초과 "A"(2026-02-10), 경고 없는 "B"(2025-02-10), PARK의
    # 기한초과 "C"
    _set_today(env)
    kim = make_user("kim", Role.SALES)
    park = make_user("park", Role.SALES)
    await env.uow.users.add(kim)
    await env.uow.users.add(park)
    deal_a = await env.new_deal(name="A", owner_user_id=kim.id, revenue_date=date(2026, 2, 10))
    await env.new_deal(name="B", owner_user_id=kim.id, revenue_date=date(2025, 2, 10))
    deal_c = await env.new_deal(name="C", owner_user_id=park.id, revenue_date=date(2026, 2, 10))
    for view in (deal_a, deal_c):
        await env.uow.deal_actions.add(
            make_deal_action(
                deal_code=view.item.deal.id,
                now=env.clock.now(),
                actor_user_id=ACTOR_ID,
                due_date=date(2026, 10, 1),
            )
        )
    mine_overdue = DealQuery(owner_user_id=kim.id, overdue=True)
    mine_q1 = DealQuery(owner_user_id=kim.id, quarters=frozenset({1}))
    # when: KIM이 (1) 내 딜만+기한초과 (2) 내 딜만+Q1(연도 없음)로 내보낸다
    overdue_export = await env.export.execute(mine_overdue)
    quarter_export = await env.export.execute(mine_q1)
    # then: 둘 다 "A"만이고(2025년 "B"는 연도 채움으로 제외, PARK의 "C"는 없음) 건수가
    # 목록 total과 같다
    assert [row[0] for row in overdue_export.rows] == ["A"]
    assert [row[0] for row in quarter_export.rows] == ["A"]
    assert len(overdue_export.rows) == (await env.list.execute(mine_overdue)).total
    assert len(quarter_export.rows) == (await env.list.execute(mine_q1)).total


async def test_export_header_has_fourteen_columns_and_values_follow_the_cell_rules(
    env: DealEnv,
) -> None:
    """CSV 머리글은 화면 13열 + Product이고 칸 값은 이름·콤마 금액·YYYY-MM-DD·빈 칸 규칙을 따른다.

    테스트 코드: DL-113
    """
    # given: 퇴사한 담당자·고객 "한빛"·Vendor SAP·Product·금액·날짜·Open Next Action이
    # 있는 "ERP 교체"
    _set_today(env)
    vendor = await env.new_vendor("SAP")
    leaver = make_user("park", Role.SALES, display_name="박영업")
    await env.uow.users.add(leaver)
    erp = await seed_deal(
        env.uow,
        code="20261016-E001",
        name="ERP 교체",
        owner_user_id=leaver.id,
        customer=make_customer(company="한빛"),
        vendor_id=vendor.id,
        product="S/4HANA",
        status_key="prospecting",
        forecast_key="commit",
        revenue_amount=1_870_000_000,
        revenue_date=date(2026, 12, 31),
    )
    leaver.resign(env.clock.now())
    await env.uow.users.update(leaver)
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=erp.id,
            now=env.clock.now(),
            actor_user_id=ACTOR_ID,
            acted_on=date(2026, 10, 1),
            next_action="PoC 일정 협의",
            due_date=date(2026, 10, 20),
        )
    )
    # given: 활성 파트너 "누리"·Product 없음·금액 500·Next Action 없는 "MFA 도입"(재직
    # 담당자 김영업)
    kim = make_user("kim", Role.SALES, display_name="김영업")
    await env.uow.users.add(kim)
    await seed_deal(
        env.uow,
        code="20261016-M001",
        name="MFA 도입",
        owner_user_id=kim.id,
        customer=make_customer(company="고객사"),
        partner=make_partner(company="누리"),
        vendor_id=vendor.id,
        product="",
        status_key="prospecting",
        forecast_key="pipeline",
        revenue_amount=500,
        revenue_date=date(2026, 6, 30),
    )
    # when: 두 Deal이 맞는 조건으로 내보낸다
    export = await env.export.execute(DealQuery())
    # then: 머리글 14열
    assert export.header == HEADER
    rows = {row[0]: row for row in export.rows}
    # then: "ERP 교체" 줄(금액은 콤마, 날짜는 YYYY-MM-DD, 퇴사 담당자는 이름(퇴사), 파트너 빈 칸)
    assert rows["ERP 교체"] == (
        "ERP 교체", "박영업(퇴사)", "한빛", "", "SAP", "S/4HANA", "기회발굴", "Commit",
        "1,870,000,000", "2026-12-31", "2026-10-01", "PoC 일정 협의", "2026-10-20", "Open",
    )  # fmt: skip
    # then: "MFA 도입" 줄(파트너 이름, Product 빈 칸, 1,000 미만 금액은 콤마 없음, Next
    # Action 세 칸 빈 칸)
    mfa = rows["MFA 도입"]
    assert (mfa[1], mfa[3], mfa[5], mfa[8]) == ("김영업", "누리", "", "500")
    assert mfa[11:] == ("", "", "")
    # then: 어느 줄에도 Deal code와 "—"가 없다
    assert not any("20261016" in cell or "—" in cell for row in export.rows for cell in row)


@pytest.mark.parametrize(
    ("status", "label"),
    [(NextActionStatus.DONE, "종료(수행)"), (NextActionStatus.NOT_DONE, "종료(미수행)")],
)
async def test_export_next_action_status_uses_the_screen_labels(
    env: DealEnv, status: NextActionStatus, label: str
) -> None:
    """Next Action 상태 칸은 화면 라벨(종료(수행)·종료(미수행))이다.

    테스트 코드: DL-113
    """
    # given: 종료한 Next Action이 있는 Deal
    _set_today(env)
    view = await env.new_deal()
    action = make_deal_action(
        deal_code=view.item.deal.id, now=env.clock.now(), actor_user_id=ACTOR_ID
    )
    await env.uow.deal_actions.add(action)
    action.change_next_action_status(status, "", env.clock.now())
    await env.uow.deal_actions.update(action)
    # when: 내보낸다
    export = await env.export.execute(DealQuery())
    # then: 상태 칸이 라벨이다
    assert export.rows[0][13] == label


async def test_export_shows_the_key_itself_when_the_code_is_not_in_the_code_list(
    env: DealEnv,
) -> None:
    """코드 목록에 없는 Status key는 key 그대로 낸다.

    테스트 코드: DL-113
    """
    # given: 코드 목록에 없는 Status key를 가진 Deal
    _set_today(env)
    await seed_deal(env.uow, code="20261016-U001", status_key="technical_evaluation")
    # given: 그 뒤 코드 목록에서 그 Status 코드가 사라졌다
    gone = [c for c in env.uow.codes._items.values() if c.key.value == "technical_evaluation"]
    for code in gone:
        del env.uow.codes._items[code.id]
    # when: 내보낸다
    export = await env.export.execute(DealQuery())
    # then: Status 칸은 key 그대로다
    assert export.rows[0][6] == "technical_evaluation"


async def test_export_neutralizes_text_cells_that_start_with_formula_symbols(env: DealEnv) -> None:
    """수식 기호로 시작하는 텍스트 칸은 앞에 작은따옴표가 붙는다.

    테스트 코드: DL-114
    """
    # given: Deal 이름 =SUM(A1), 고객 +82상사, 파트너 @누리, Next Action -할인 제안인
    # Deal과 "정상" Deal
    _set_today(env)
    risky = await seed_deal(
        env.uow,
        code="20261016-R001",
        name="=SUM(A1)",
        product="=HYPERLINK(1)",
        customer=make_customer(company="+82상사"),
        partner=make_partner(company="@누리"),
        revenue_amount=7,
    )
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=risky.id,
            now=env.clock.now(),
            actor_user_id=ACTOR_ID,
            next_action="-할인 제안",
            due_date=date(2026, 10, 20),
        )
    )
    await seed_deal(env.uow, code="20261016-N001", name="정상")
    # when: 두 Deal이 맞는 조건으로 내보낸다
    export = await env.export.execute(DealQuery())
    rows = {row[0]: row for row in export.rows}
    # then: 위험한 칸은 '로 시작한다
    row = rows["'=SUM(A1)"]
    assert (row[2], row[3], row[11]) == ("'+82상사", "'@누리", "'-할인 제안")
    assert row[5] == "'=HYPERLINK(1)"
    # then: "정상" 이름 칸과 금액·날짜 칸에는 '가 붙지 않는다
    assert "정상" in rows
    assert not any(cell.startswith("'") for cell in (row[8], row[9], row[10], row[12]))
    assert not any(cell.startswith("'") for cell in rows["정상"])


async def test_export_without_matching_deals_returns_only_the_header(env: DealEnv) -> None:
    """조건에 맞는 Deal이 없으면 머리글만 있고 파일 이름은 업무 날짜다.

    테스트 코드: DL-115
    """
    # given: Status zz인 Deal이 없다(다른 Deal은 있다)
    _set_today(env)
    await env.new_deal()
    # when: status_key=zz로 내보낸다
    export = await env.export.execute(DealQuery(status_key="zz"))
    # then: 행 없이 머리글 14열과 파일 이름뿐이다
    assert export.rows == []
    assert export.header == HEADER
    assert export.file_name == "Deals_20261015.csv"


async def test_export_allows_exactly_ten_thousand_deals(env: DealEnv) -> None:
    """정확히 10,000건은 내려받는다.

    테스트 코드: DL-116
    """
    # given: 조건에 맞는 Deal 10,000건
    _set_today(env)
    customer = make_customer(company="대량")
    for index in range(10_000):
        await seed_deal(
            env.uow,
            code=f"20261016-{index:04X}",
            name=f"D{index}",
            customer=customer,
            commit=False,
        )
    # when: 내보낸다
    export = await env.export.execute(DealQuery())
    # then: 데이터 줄 10,000개다
    assert len(export.rows) == 10_000


async def test_export_over_ten_thousand_is_invalid_value(env: DealEnv) -> None:
    """10,001건은 invalid-value(422)이고 CSV를 만들지 않는다.

    테스트 코드: DL-116
    """
    # given: 조건에 맞는 Deal 10,001건
    _set_today(env)
    customer = make_customer(company="대량")
    for index in range(10_001):
        await seed_deal(
            env.uow,
            code=f"20261016-{index:04X}",
            name=f"D{index}",
            customer=customer,
            commit=False,
        )
    # when: 내보낸다
    # then: 건수가 든 고정 문구로 거절된다
    with raises_with(
        InvalidValueError,
        "내려받을 Deal이 10,000건을 넘습니다(10,001건). 조건을 좁혀 다시 시도하세요.",
    ):
        await env.export.execute(DealQuery())
