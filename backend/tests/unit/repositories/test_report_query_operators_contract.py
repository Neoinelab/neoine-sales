"""ReportQueryRunner(SQL) 계약: 연산자별 조건 결과와 값 안전성 (AC4, AC8, AC11).

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
        status="introduction", forecast="commit", procurement="RFP",
    )  # fmt: skip
    await case.add_deal(name=BETA, amount=300, day=date(2026, 5, 1), owner=KIM)
    await case.add_deal(name=GAMMA, amount=400, day=date(2026, 6, 1), owner=LEE, forecast="lost")
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
        ("vendor-in", "deal.vendor", "in", [ids.sap], [ALPHA]),
        ("vendor-in-two", "deal.vendor", "in", [ids.sap, ids.ibm], [ALPHA, ALPHA_TWO]),
        ("vendor-not-in-includes-none", "deal.vendor", "not_in", [ids.sap], [ALPHA_TWO, BETA, GAMMA]),  # noqa: E501
        ("vendor-is-empty", "deal.vendor", "is_empty", None, [BETA, GAMMA]),
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
    ids = await _seed(report_case)
    _, field, operator, value, expected = _cases(ids)[index]

    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    assert [row[0] for row in rows] == expected


async def test_or_returns_deals_meeting_any_condition(report_case: ReportCase) -> None:
    await _seed(report_case)

    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.amount", "lt", 150), cond("deal.amount", "gt", 350)],
        combine="or",
    )

    assert [row[0] for row in rows] == [ALPHA, GAMMA]


async def test_and_returns_deals_meeting_every_condition(report_case: ReportCase) -> None:
    await _seed(report_case)

    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.amount", "gte", 200), cond("deal.owner", "in", [KIM])],
        combine="and",
    )

    assert [row[0] for row in rows] == [BETA]


# ---- 값 안전성 (AC11) ----


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
    await _seed(report_case)

    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    expected = {"not_in": 4}.get(operator, 0)
    assert len(rows) == expected  # not_in은 일치하는 값이 없으므로 모두 남는다
    assert await report_case.deals.deals.count(DealQuery()) == 4


async def test_injection_text_is_matched_literally_when_a_deal_has_it(
    report_case: ReportCase,
) -> None:
    await report_case.add_deal(name=INJECTION)
    await report_case.add_deal(name="ordinary")

    rows = await report_case.rows([col("deal.name")], [cond("deal.name", "equals", INJECTION)])

    assert rows == [(INJECTION,)]


async def test_percent_and_underscore_are_matched_literally(report_case: ReportCase) -> None:
    for name in ("50% off", "50x off", "50_ off", "50y off"):
        await report_case.add_deal(name=name)

    percent = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "50%")])
    underscore = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "50_")])
    starts = await report_case.rows([col("deal.name")], [cond("deal.name", "starts_with", "50%")])

    assert percent == [("50% off",)]
    assert underscore == [("50_ off",)]
    assert starts == [("50% off",)]


async def test_backslash_is_matched_literally(report_case: ReportCase) -> None:
    await report_case.add_deal(name="a\\b")
    await report_case.add_deal(name="ab")

    rows = await report_case.rows([col("deal.name")], [cond("deal.name", "contains", "a\\b")])

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
    await report_case.add_deal(name="A", users=1)
    await report_case.add_deal(name="B", users=2_000_000_000)

    rows = await report_case.rows([col("deal.name")], [cond(field, operator, value)])

    assert rows == ([("A",), ("B",)] if keeps_all else [])
