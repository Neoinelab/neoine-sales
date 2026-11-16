"""ReportQueryRunner(SQL) 계약: 연산자별 조건 결과와 값 안전성.

텍스트 contains/equals/starts_with/is_empty, 코드·사용자 in/not_in/is_empty, 숫자 비교·between,
날짜 before/after/between을 실제 DB로 확인한다. 기대값은 데이터에서 직접 적은 값이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.bant.values import BantCategory
from tests.factories import make_bant
from tests.support.report_defs import col, cond
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

INJECTION = "'; drop table deals; --"
ALPHA, ALPHA_TWO, BETA, GAMMA = "Alpha Project", "alpha-two", "Beta", "Gamma"
KIM = uid("op_kim")
LEE = uid("op_lee")


class Ids:
    """시드가 만든 id를 담는다 (조건 값으로 쓴다)."""

    def __init__(self, sap: int, ibm: int, label: int) -> None:
        self.sap = sap
        self.ibm = ibm
        self.label = label


async def _seed(case: ReportCase) -> Ids:
    sap = await case.deals.new_vendor("SAP")
    ibm = await case.deals.new_vendor("IBM")
    label = await case.deals.new_label(BantCategory.BUDGET, "Budget OK")
    await case.add_deal(
        name=ALPHA, amount=100, day=date(2026, 3, 1), vendor_id=sap.id, owner=KIM,
        bant=make_bant(budget=label.id),
    )  # fmt: skip
    await case.add_deal(
        name=ALPHA_TWO, amount=200, day=date(2026, 4, 1), vendor_id=ibm.id, owner=LEE,
        status="introduction", forecast="commit", procurement="RFP", product="",
    )  # fmt: skip
    await case.add_deal(name=BETA, amount=300, day=date(2026, 5, 1), vendor_id=sap.id, owner=KIM)
    await case.add_deal(
        name=GAMMA, amount=400, day=date(2026, 6, 1), vendor_id=sap.id, owner=LEE, forecast="lost"
    )
    return Ids(sap.id, ibm.id, label.id)


def _cases(ids: Ids) -> list[tuple[str, str, str, object, list[str]]]:
    return [
        ("contains-case-insensitive", "deal.name", "contains", "alpha", [ALPHA, ALPHA_TWO]),
        ("contains-hyphen", "deal.name", "contains", "ALPHA-", [ALPHA_TWO]),
        ("equals-ignores-case", "deal.name", "equals", "ALPHA PROJECT", [ALPHA]),
        ("equals-is-not-substring", "deal.name", "equals", "alpha", []),
        ("starts-with", "deal.name", "starts_with", "alph", [ALPHA, ALPHA_TWO]),
        ("starts-with-not-middle", "deal.name", "starts_with", "pha", []),
        ("text-empty-string", "deal.procurement", "is_empty", None, [ALPHA, BETA, GAMMA]),
        ("text-not-empty", "deal.procurement", "is_not_empty", None, [ALPHA_TWO]),
        ("null-counts-as-empty", "deal.partner_company", "is_empty", None, [ALPHA, ALPHA_TWO, BETA, GAMMA]),  # noqa: E501
        ("null-is-not-not-empty", "deal.partner_company", "is_not_empty", None, []),
        ("vendor-in", "deal.vendor", "in", [ids.sap], [ALPHA, BETA, GAMMA]),
        ("vendor-in-two", "deal.vendor", "in", [ids.sap, ids.ibm], [ALPHA, ALPHA_TWO, BETA, GAMMA]),
        ("vendor-not-in", "deal.vendor", "not_in", [ids.sap], [ALPHA_TWO]),
        ("product-is-empty", "deal.product", "is_empty", None, [ALPHA_TWO]),
        ("product-is-not-empty", "deal.product", "is_not_empty", None, [ALPHA, BETA, GAMMA]),
        ("owner-in", "deal.owner", "in", [KIM], [ALPHA, BETA]),
        ("owner-not-in", "deal.owner", "not_in", [KIM], [ALPHA_TWO, GAMMA]),
        ("status-in", "deal.status", "in", ["introduction"], [ALPHA_TWO]),
        ("status-not-in", "deal.status", "not_in", ["introduction"], [ALPHA, BETA, GAMMA]),
        ("forecast-in", "deal.forecast", "in", ["commit", "lost"], [ALPHA_TWO, GAMMA]),
        ("outcome-in-open", "deal.forecast_outcome", "in", ["open"], [ALPHA, ALPHA_TWO, BETA]),
        ("outcome-not-in-lost", "deal.forecast_outcome", "not_in", ["lost"], [ALPHA, ALPHA_TWO, BETA]),  # noqa: E501
        ("bant-in", "deal.bant_budget", "in", [ids.label], [ALPHA]),
        ("bant-is-empty", "deal.bant_budget", "is_empty", None, [ALPHA_TWO, BETA, GAMMA]),
        ("number-eq", "deal.amount", "eq", 200, [ALPHA_TWO]),
        ("number-ne", "deal.amount", "ne", 200, [ALPHA, BETA, GAMMA]),
        ("number-gt-strict", "deal.amount", "gt", 200, [BETA, GAMMA]),
        ("number-gte", "deal.amount", "gte", 200, [ALPHA_TWO, BETA, GAMMA]),
        ("number-lt-strict", "deal.amount", "lt", 200, [ALPHA]),
        ("number-lte", "deal.amount", "lte", 200, [ALPHA, ALPHA_TWO]),
        ("number-between-inclusive", "deal.amount", "between", [200, 300], [ALPHA_TWO, BETA]),
        ("date-before-strict", "deal.expected_close", "before", "2026-04-01", [ALPHA]),
        ("date-after-strict", "deal.expected_close", "after", "2026-04-01", [BETA, GAMMA]),
        ("date-between-inclusive", "deal.expected_close", "between", ["2026-04-01", "2026-05-01"], [ALPHA_TWO, BETA]),  # noqa: E501
    ]  # fmt: skip


def _ids_for_parametrize() -> list[str]:
    return [case[0] for case in _cases(Ids(1, 2, 3))]


@pytest.mark.parametrize("index", range(len(_cases(Ids(1, 2, 3)))), ids=_ids_for_parametrize())
async def test_text_code_number_date_operators(report_case: ReportCase, index: int) -> None:
    """텍스트·코드·숫자·날짜 연산자는 정해진 뜻으로 거른다.

    테스트 코드: RQ-032
    """
    # given: 이름·금액·날짜·Vendor·담당자가 다른 Deal 4건(IBM·빈 Product Deal 하나, 나머지는 SAP)
    ids = await _seed(report_case)
    _, field, operator, value, expected = _cases(ids)[index]

    # when: 연산자 조건 하나로 이름을 조회한다 (전제: 사례 매개변수)
    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    # then: 기대한 이름들이 순서대로 나온다
    assert [row[0] for row in rows] == expected


async def test_or_returns_deals_meeting_any_condition(report_case: ReportCase) -> None:
    """OR는 조건 하나라도 맞는 Deal을 고른다.

    테스트 코드: RQ-032
    """
    # given: 금액이 다른 Deal 4건
    await _seed(report_case)

    # when: 금액 150 미만 또는 350 초과 조건을 OR로 조회한다
    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.amount", "lt", 150), cond("deal.amount", "gt", 350)],
        combine="or",
    )

    # then: 양쪽 끝 Deal 둘이다
    assert [row[0] for row in rows] == [ALPHA, GAMMA]


async def test_and_returns_deals_meeting_every_condition(report_case: ReportCase) -> None:
    """AND는 모든 조건을 만족하는 Deal만 고른다.

    테스트 코드: RQ-032
    """
    # given: 금액과 담당자가 다른 Deal 4건
    await _seed(report_case)

    # when: 금액 200 이상이고 담당자가 KIM인 조건을 AND로 조회한다
    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.amount", "gte", 200), cond("deal.owner", "in", [KIM])],
        combine="and",
    )

    # then: 둘 다 맞는 Deal 하나다
    assert [row[0] for row in rows] == [BETA]


# ---- 값 안전성 ----


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("deal.name", "contains", INJECTION),
        ("deal.name", "equals", INJECTION),
        ("deal.name", "starts_with", INJECTION),
        ("deal.status", "in", [INJECTION]),
        ("deal.forecast", "not_in", [INJECTION]),
    ],
    ids=["contains", "equals", "starts-with", "key-in", "key-not-in"],
)
async def test_sql_injection_like_values_keep_the_tables(
    report_case: ReportCase, field: str, operator: str, value: object
) -> None:
    """SQL처럼 보이는 값은 글자 그대로 취급되고 데이터는 그대로다.

    테스트 코드: RQ-033
    """
    # given: Deal 4건
    await _seed(report_case)

    # when: SQL 주입 문자열을 값으로 조건 조회한다 (전제: 조건 매개변수)
    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    # then: 맞는 행 수가 기대와 같고 Deal은 여전히 4건이다
    expected = {"not_in": 4}.get(operator, 0)
    assert len(rows) == expected  # not_in은 일치하는 값이 없으므로 모두 남는다
    assert await report_case.deals.deals.count(DealQuery()) == 4


async def test_injection_text_is_matched_literally_when_a_deal_has_it(
    report_case: ReportCase,
) -> None:
    """Deal 이름이 SQL 주입 문자열과 같으면 글자 그대로 찾는다.

    테스트 코드: RQ-033
    """
    # given: 이름이 SQL 주입 문자열인 Deal과 일반 Deal
    await report_case.add_deal(name=INJECTION)
    await report_case.add_deal(name="ordinary")

    # when: 그 문자열로 같음 조건 조회한다
    rows = await report_case.rows([col("deal.name")], [cond("deal.name", "equals", INJECTION)])

    # then: 해당 Deal 하나다
    assert rows == [(INJECTION,)]


async def test_percent_and_underscore_are_matched_literally(report_case: ReportCase) -> None:
    """%와 _는 와일드카드가 아니라 글자 그대로 찾는다.

    테스트 코드: RQ-033
    """
    # given: 50% off, 50x off, 50_ off, 50y off Deal
    for name in ("50% off", "50x off", "50_ off", "50y off"):
        await report_case.add_deal(name=name)

    # when: 50%, 50_ 포함과 50% 시작으로 각각 조회한다
    percent = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "50%")])
    underscore = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "50_")])
    starts = await report_case.rows([col("deal.name")], [cond("deal.name", "starts_with", "50%")])

    # then: 각각 글자가 일치하는 Deal 하나뿐이다
    assert percent == [("50% off",)]
    assert underscore == [("50_ off",)]
    assert starts == [("50% off",)]


async def test_backslash_is_matched_literally(report_case: ReportCase) -> None:
    """역슬래시도 글자 그대로 찾는다.

    테스트 코드: RQ-033
    """
    # given: a\b와 ab 이름의 Deal
    await report_case.add_deal(name="a\\b")
    await report_case.add_deal(name="ab")

    # when: a\b 포함 조건으로 조회한다
    rows = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "a\\b")])

    # then: a\b Deal 하나다
    assert rows == [("a\\b",)]


# ---- int32를 넘는 숫자 값 ----

BIG = 3_000_000_000


@pytest.mark.parametrize(
    ("field", "operator", "value", "keeps_all"),
    [
        ("deal.users", "gt", BIG, False),
        ("deal.users", "gte", BIG, False),
        ("deal.users", "eq", BIG, False),
        ("deal.users", "lt", BIG, True),
        ("deal.users", "lte", BIG, True),
        ("deal.users", "ne", BIG, True),
        ("deal.users", "gt", -BIG, True),
        ("deal.users", "lt", -BIG, False),
        ("deal.users", "between", [-BIG, BIG], True),
        ("deal.users", "between", [BIG, BIG + 1], False),
        ("deal.status_days", "gt", BIG, False),
        ("deal.amount", "lt", BIG * 1000, True),
    ],
)
async def test_numbers_beyond_int32_are_compared_not_rejected(
    report_case: ReportCase, field: str, operator: str, value: object, keeps_all: bool
) -> None:
    """int32를 넘는 숫자도 거절하지 않고 비교한다.

    테스트 코드: RQ-034
    """
    # given: Users가 1과 2,000,000,000인 Deal
    await report_case.add_deal(name="A", users=1)
    await report_case.add_deal(name="B", users=2_000_000_000)

    # when: 3,000,000,000 등 큰 값으로 비교 조건 조회한다 (전제: 연산자·값 매개변수)
    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    # then: 기대대로 전부 또는 아무것도 나오지 않는다
    assert rows == ([("A",), ("B",)] if keeps_all else [])
