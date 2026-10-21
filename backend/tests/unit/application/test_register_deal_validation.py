"""RegisterDeal 입력 검증(AC-05, R-8): 목업 `validateDealFields`의 순서·문구.

모든 위반은 InvalidValueError 계열(422)이다. 순서 시험은 누적 방식이다. i번째 사례는 i번째 이후의
모든 위반을 함께 가지고 있고, 가장 앞선 i번째 문구가 나와야 한다. 실패하면 아무것도 저장하지 않는다.
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_create_input, make_draft
from tests.support.auth_seed import seed_user
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.deal.inputs import ContactDraftInput
    from tests.unit.application.deal_env import DealEnv

NAME_MISSING = "Deal Name을 입력하세요."
NAME_LONG = "Deal Name은 200자 이내로 입력하세요."
OWNER_RESIGNED = "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."
OWNER_NOT_SALES = "Owner는 재직 중인 영업 담당자여야 합니다."
AMOUNT = "매출금액은 1원 이상의 정수로 입력하세요."
CLOSE_MISSING = "Expected Close를 입력하세요."
USERS = "Users는 0 이상의 정수로 입력하세요."
USERS_REQUIRED = "Users를 입력하세요."
STATUS_MISSING = "Status를 선택하세요."
FORECAST_MISSING = "Forecast를 선택하세요."
SYNC = "Status와 Forecast의 동기화가 맞지 않습니다."
LABEL = "BANT Label이 올바르지 않습니다."
PROCUREMENT = "구매절차는 500자 이내로 입력하세요."
CUSTOMER_COMPANY = "고객 회사명을 입력하세요."
CUSTOMER_NAME = "고객 담당자명을 입력하세요."
PARTNER_INCOMPLETE = "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."
EMAIL = "이메일 형식이 올바르지 않습니다."
SOLUTION_NEEDS_VENDOR = "Solution을 선택하려면 Vendor를 먼저 선택하세요."
UNKNOWN_VENDOR = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."
SOLUTION_MISMATCH = "선택한 Solution은 이 Vendor에 속하지 않습니다."


@dataclass
class Ctx:
    resigned_owner: int
    admin_owner: int
    other_category_label: int
    sap: int
    oracle_solution: int


@pytest.fixture
async def ctx(env: DealEnv) -> Ctx:
    resigned = await seed_user(env.uow_factory, "gone", Role.SALES, resigned=True)
    admin = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    oracle = await env.new_vendor("Oracle", ("EBS",))
    return Ctx(resigned.id, admin.id, need.id, sap.id, oracle.solutions[0].id)


def _steps(ctx: Ctx) -> list[tuple[str, dict[str, Any], str]]:
    """(이름, 위반 입력, 기대 문구) - AC-05 순서대로."""
    return [
        ("name-missing", {"name": "  "}, NAME_MISSING),
        (
            "solution-without-vendor",
            {"vendor_id": None, "solution_id": ctx.oracle_solution},
            SOLUTION_NEEDS_VENDOR,
        ),
        ("unknown-vendor", {"vendor_id": new_id()}, UNKNOWN_VENDOR),
        (
            "solution-of-other-vendor",
            {"vendor_id": ctx.sap, "solution_id": ctx.oracle_solution},
            SOLUTION_MISMATCH,
        ),
        ("owner-resigned", {"owner_user_id": ctx.resigned_owner}, OWNER_RESIGNED),
        ("amount-zero", {"revenue_amount": 0}, AMOUNT),
        ("close-missing", {"revenue_date": None}, CLOSE_MISSING),
        ("users-negative", {"users": -1}, USERS),
        ("status-missing", {"status_key": ""}, STATUS_MISSING),
        ("forecast-missing", {"forecast_key": ""}, FORECAST_MISSING),
        (
            "sync-mismatch",
            {"status_key": "contract_completed", "forecast_key": "pipeline"},
            SYNC,
        ),
        ("bant-wrong-category", {"bant": {BantCategory.BUDGET: ctx.other_category_label}}, LABEL),
        ("procurement-long", {"procurement": "가" * 501}, PROCUREMENT),
        (
            "customer-company-missing",
            {"customer": make_draft(company="", email="bad")},
            CUSTOMER_COMPANY,
        ),
        ("customer-name-missing", {"customer": make_draft(name="", email="bad")}, CUSTOMER_NAME),
        (
            "partner-incomplete",
            {"partner": make_draft(company="", name="", email="bad")},
            PARTNER_INCOMPLETE,
        ),
        ("contact-rule", {"customer": make_draft(email="bad")}, EMAIL),
    ]


def _cumulative(ctx: Ctx, index: int) -> dict[str, Any]:
    """index번째 이후의 모든 위반을 합친 입력. 같은 필드를 건드리면 앞선 사례의 값이 남는다."""
    merged: dict[str, Any] = {}
    for _, overrides, _ in reversed(_steps(ctx)[index:]):
        merged.update(overrides)
    return merged


STEP_NAMES = [
    "name-missing",
    "solution-without-vendor",
    "unknown-vendor",
    "solution-of-other-vendor",
    "owner-resigned",
    "amount-zero",
    "close-missing",
    "users-negative",
    "status-missing",
    "forecast-missing",
    "sync-mismatch",
    "bant-wrong-category",
    "procurement-long",
    "customer-company-missing",
    "customer-name-missing",
    "partner-incomplete",
    "contact-rule",
]


@pytest.mark.parametrize("index", range(len(STEP_NAMES)), ids=STEP_NAMES)
async def test_the_earliest_rule_in_the_agreed_order_is_reported_first(
    env: DealEnv, ctx: Ctx, index: int
) -> None:
    expected = _steps(ctx)[index][2]
    overrides = _cumulative(ctx, index)

    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(**overrides), SALES)


@pytest.mark.parametrize("index", range(len(STEP_NAMES)), ids=STEP_NAMES)
async def test_each_violation_alone_gives_its_own_message(
    env: DealEnv, ctx: Ctx, index: int
) -> None:
    _, overrides, expected = _steps(ctx)[index]

    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(**overrides), SALES)


async def test_a_failed_registration_stores_and_commits_nothing(env: DealEnv, ctx: Ctx) -> None:
    commits = env.uow.commits

    with pytest.raises(InvalidValueError):
        await env.register.execute(
            make_create_input(revenue_amount=0, customer=make_draft(company="새고객")), SALES
        )

    assert env.uow.commits == commits
    assert env.uow.deals._items == {}
    assert env.uow.contacts._items == {}  # 새 고객 연락처도 만들어지지 않았다
    assert env.uow.deal_history._items == {}


async def test_an_incomplete_partner_does_not_leave_the_new_customer_behind(
    env: DealEnv, ctx: Ctx
) -> None:
    with raises_with(InvalidValueError, PARTNER_INCOMPLETE):
        await env.register.execute(
            make_create_input(
                customer=make_draft(company="새고객"), partner=make_draft(company="", name="")
            ),
            SALES,
        )

    assert env.uow.contacts._items == {}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": "가" * 201}, NAME_LONG),
        ({"revenue_amount": -5}, AMOUNT),
        ({"revenue_amount": 2**53}, AMOUNT),
        ({"users": 2_147_483_648}, USERS),
        ({"users": -1}, USERS),
        ({"users": None}, USERS_REQUIRED),
        ({"status_key": "unknown_status"}, STATUS_MISSING),
        ({"forecast_key": "unknown_forecast"}, FORECAST_MISSING),
        ({"status_key": "prospecting", "forecast_key": "won"}, SYNC),
    ],
)
async def test_boundaries_and_unknown_codes_are_rejected_with_their_own_message(
    env: DealEnv, ctx: Ctx, overrides: dict[str, Any], expected: str
) -> None:
    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(**overrides), SALES)


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": 1},
        {"revenue_amount": 2**53 - 1},
        {"users": 0},
        {"users": 1},
        {"users": 2_147_483_647},
        {"name": "가" * 200},
        {"procurement": "가" * 500},
        {"vendor_id": None, "solution_id": None},
        {"revenue_date": date(2026, 12, 31)},
    ],
)
async def test_boundary_values_are_accepted(
    env: DealEnv, ctx: Ctx, overrides: dict[str, Any]
) -> None:
    view = await env.register.execute(make_create_input(**overrides), SALES)

    assert view.item.deal.id.value


async def test_an_admin_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=ctx.admin_owner), SALES)


async def test_an_unknown_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=new_id()), SALES)


async def test_a_read_only_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    viewer = await seed_user(env.uow_factory, "viewer", Role.USER)

    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=viewer.id), SALES)


@pytest.mark.parametrize(
    ("customer", "expected"),
    [
        (make_draft(company="네 오인"), "공백은 입력할 수 없습니다."),
        (make_draft(name="김 철수"), "공백은 입력할 수 없습니다."),
        (make_draft(email="no-at-sign"), EMAIL),
        (make_draft(phone="abc"), "전화번호 형식이 올바르지 않습니다."),
    ],
)
async def test_contact_format_rules_apply_to_the_draft(
    env: DealEnv,
    ctx: Ctx,
    customer: ContactDraftInput,
    expected: str,
) -> None:
    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(customer=customer), SALES)


async def test_the_old_vendor_text_input_is_gone() -> None:
    with pytest.raises(TypeError):
        make_create_input(vendor="SAP")


async def test_vendor_without_solution_is_accepted(env: DealEnv, ctx: Ctx) -> None:
    view = await env.register.execute(make_create_input(vendor_id=ctx.sap), SALES)

    assert (view.item.deal.details.vendor_id, view.item.deal.details.solution_id) == (ctx.sap, None)
