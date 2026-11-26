"""RegisterDeal 입력 검증(R-8): 목업 `validateDealFields`의 순서·문구.

모든 위반은 InvalidValueError 계열(422)이다. 순서 시험은 누적 방식이다. i번째 사례는 i번째 이후의
모든 위반을 함께 가지고 있고, 가장 앞선 i번째 문구가 나와야 한다. 실패하면 아무것도 저장하지 않는다.
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.deal.dto import NamedRef
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
USERS = "Users count는 0 이상의 정수로 입력하세요."
USERS_REQUIRED = "Users count를 입력하세요."
STATUS_MISSING = "Status를 선택하세요."
FORECAST_MISSING = "Forecast를 선택하세요."
SYNC = "Status와 Forecast의 동기화가 맞지 않습니다."
LABEL = "BANT Label이 올바르지 않습니다."
PROCUREMENT = "구매절차는 500자 이내로 입력하세요."
CUSTOMER_COMPANY = "고객 회사명을 입력하세요."
CUSTOMER_NAME = "고객 담당자명을 입력하세요."
PARTNER_INCOMPLETE = "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."
EMAIL = "이메일 형식이 올바르지 않습니다."
VENDOR_REQUIRED = "Vendor를 선택하세요."
PRODUCT_LONG = "Product는 200자 이내로 입력하세요."
UNKNOWN_VENDOR = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."


@dataclass
class Ctx:
    resigned_owner: int
    admin_owner: int
    other_category_label: int
    sap: int


@pytest.fixture
async def ctx(env: DealEnv) -> Ctx:
    resigned = await seed_user(env.uow_factory, "gone", Role.SALES, resigned=True)
    admin = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")
    sap = await env.new_vendor("SAP")
    return Ctx(resigned.id, admin.id, need.id, sap.id)


def _steps(ctx: Ctx) -> list[tuple[str, dict[str, Any], str]]:
    """(이름, 위반 입력, 기대 문구) - 순서대로."""
    return [
        ("name-missing", {"name": "  "}, NAME_MISSING),
        ("vendor-missing", {"vendor_id": None}, VENDOR_REQUIRED),
        ("unknown-vendor", {"vendor_id": new_id()}, UNKNOWN_VENDOR),
        ("product-long", {"product": "a" * 201}, PRODUCT_LONG),
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
    "vendor-missing",
    "unknown-vendor",
    "product-long",
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
    """여러 값이 틀리면 정해진 검증 순서의 첫 문구만 나온다(BANT는 동기화 다음, 구매절차 앞).

    테스트 코드: DE-009, DE-022
    """
    # given: i번째 이후의 모든 위반을 함께 가진 입력(누적).
    expected = _steps(ctx)[index][2]
    overrides = _cumulative(ctx, index)

    # when·then: 그 입력으로 등록한다 → i번째 규칙의 문구만 나온다.
    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(**overrides), SALES)


@pytest.mark.parametrize("index", range(len(STEP_NAMES)), ids=STEP_NAMES)
async def test_each_violation_alone_gives_its_own_message(
    env: DealEnv, ctx: Ctx, index: int
) -> None:
    """필드 값 위반은 각자의 문구로 거절된다.

    테스트 코드: DE-008, DE-018, DE-015
    """
    # given: 위반 하나만 가진 입력(이름·Vendor·Product·Owner·금액 등).
    _, overrides, expected = _steps(ctx)[index]

    # when·then: 그 입력으로 등록한다 → 그 위반의 문구(422 invalid-value)가 나온다.
    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(**overrides), SALES)


async def test_a_failed_registration_stores_and_commits_nothing(env: DealEnv, ctx: Ctx) -> None:
    """검증에 실패한 등록은 Deal·새 연락처·이력을 저장하지 않고 커밋하지 않는다.

    테스트 코드: DE-008
    """
    # given: 새 고객 입력과 금액 0.
    commits = env.uow.commits

    # when: 등록한다.
    with pytest.raises(InvalidValueError):
        await env.register.execute(
            make_create_input(revenue_amount=0, customer=make_draft(company="새고객")), SALES
        )

    # then: 오류이고 커밋·Deal·연락처·이력이 모두 없다.
    assert env.uow.commits == commits
    assert env.uow.deals._items == {}
    assert env.uow.contacts._items == {}  # 새 고객 연락처도 만들어지지 않았다
    assert env.uow.deal_history._items == {}


async def test_an_incomplete_partner_does_not_leave_the_new_customer_behind(
    env: DealEnv, ctx: Ctx
) -> None:
    """파트너가 반쪽이면 문구로 거절하고 새 고객 연락처도 남지 않는다.

    테스트 코드: DE-023
    """
    # when: 등록한다. (전제: 새 고객 입력과 회사명·담당자명이 빈 파트너)
    with raises_with(InvalidValueError, PARTNER_INCOMPLETE):
        await env.register.execute(
            make_create_input(
                customer=make_draft(company="새고객"), partner=make_draft(company="", name="")
            ),
            SALES,
        )

    # then: '파트너를 입력하면 …' 오류이고 연락처가 없다.
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
    """경계 밖 값과 없는 코드는 각자의 문구로 거절된다.

    테스트 코드: DE-008, DE-018
    """
    # when: 경계 밖 값(이름 201자·금액 -5·2^53·Users count 등)이나 없는 Status/Forecast, 동기화
    #   위반으로 등록한다.
    # then: 각 값의 문구(422)가 나온다.
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
        {"product": ""},
        {"product": "a" * 200},
        {"product": "  ITDR  "},
        {"revenue_date": date(2026, 12, 31)},
    ],
)
async def test_boundary_values_are_accepted(
    env: DealEnv, ctx: Ctx, overrides: dict[str, Any]
) -> None:
    """경계값(금액 1·2^53-1, Users count 0·최대, 이름 200자, 구매절차 500자 등)은 등록된다.

    테스트 코드: DE-007
    """
    # when: 경계값으로 등록한다.
    view = await env.register.execute(make_create_input(**overrides), SALES)

    # then: 등록되고 응답 값이 보낸 값이다.
    details = view.item.deal.details
    assert view.item.deal.id.value
    if "revenue_amount" in overrides:
        assert details.revenue_amount.value == overrides["revenue_amount"]
    if "users" in overrides:
        assert details.users == overrides["users"]
    if "name" in overrides:
        assert details.name == overrides["name"]
    if "procurement" in overrides:
        assert details.procurement == overrides["procurement"]
    if "revenue_date" in overrides:
        assert details.revenue_date == overrides["revenue_date"]


async def test_an_admin_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    """admin을 Owner로 지정하면 거절한다.

    테스트 코드: DE-012
    """
    # when·then: admin 사용자를 Owner로 등록한다
    # → 'Owner는 재직 중인 영업 담당자여야 합니다.' 오류다.
    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=ctx.admin_owner), SALES)


async def test_an_unknown_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    """없는 사용자를 Owner로 지정하면 거절한다.

    테스트 코드: DE-012
    """
    # when·then: 없는 id를 Owner로 등록한다 → 'Owner는 재직 중인 영업 담당자여야 합니다.' 오류다.
    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=new_id()), SALES)


async def test_a_read_only_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    """읽기 전용 user를 Owner로 지정하면 거절한다.

    테스트 코드: DE-012
    """
    # when: user 역할을 Owner로 등록한다.
    viewer = await seed_user(env.uow_factory, "viewer", Role.USER)

    # then: 'Owner는 재직 중인 영업 담당자여야 합니다.' 오류다.
    with raises_with(InvalidValueError, OWNER_NOT_SALES):
        await env.register.execute(make_create_input(owner_user_id=viewer.id), SALES)


@pytest.mark.parametrize(
    ("customer", "expected"),
    [
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
    """고객 입력에 연락처 형식 규칙(공백·이메일·전화)이 적용된다.

    테스트 코드: DE-024
    """
    # when·then: 공백이 든 회사명·이름, 틀린 이메일·전화로 등록한다
    # → 연락처 형식 문구(422)가 나온다.
    with raises_with(InvalidValueError, expected):
        await env.register.execute(make_create_input(customer=customer), SALES)


async def test_the_old_vendor_text_input_is_gone() -> None:
    """예전 Vendor 텍스트 입력 필드는 없다."""
    # when·then: vendor 인자로 등록 입력을 만든다 → TypeError다.
    with pytest.raises(TypeError):
        make_create_input(vendor="SAP")


@pytest.mark.parametrize("blank", ["", "  ", "\t"])
async def test_blank_product_is_stored_as_empty(env: DealEnv, ctx: Ctx, blank: str) -> None:
    """비었거나 공백뿐인 Product 등록은 오류 없이 빈 Product로 저장된다.

    테스트 코드: DE-115
    """
    # when: 빈 문자열·공백·탭 Product로 등록한다.
    view = await env.register.execute(make_create_input(product=blank), SALES)

    # then: 등록되고 저장된 Product가 ''다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert view.item.deal.details.product == ""
    assert stored.details.product == ""


async def test_vendor_with_a_product_is_accepted(env: DealEnv, ctx: Ctx) -> None:
    """Vendor와 Product를 함께 보내 등록할 수 있다.

    테스트 코드: DE-014
    """
    # when: Vendor id와 Product로 등록한다. (전제: Vendor SAP가 있다)
    view = await env.register.execute(make_create_input(vendor_id=ctx.sap), SALES)

    # then: Vendor id와 Product가 저장된다.
    assert (view.item.deal.details.vendor_id, view.item.deal.details.product) == (
        ctx.sap,
        "S/4HANA",
    )
    assert view.vendor == NamedRef(ctx.sap, "SAP")


async def test_vendor_without_a_product_is_accepted(env: DealEnv, ctx: Ctx) -> None:
    """Vendor만 있고 Product가 빈 값이어도 등록할 수 있다.

    테스트 코드: DE-014
    """
    # when: Vendor SAP, Product ''로 등록한다.
    view = await env.register.execute(make_create_input(vendor_id=ctx.sap, product=""), SALES)

    # then: Vendor는 SAP이고 Product는 ''다.
    assert (view.item.deal.details.vendor_id, view.item.deal.details.product) == (ctx.sap, "")


async def test_missing_vendor_is_rejected_and_stores_nothing(env: DealEnv, ctx: Ctx) -> None:
    """Vendor 없이 등록하면 "Vendor를 선택하세요."로 거절되고 저장되지 않는다.

    테스트 코드: DE-009
    """
    # when·then: vendor_id None으로 등록한다 → 'Vendor를 선택하세요.' 오류다.
    with raises_with(InvalidValueError, VENDOR_REQUIRED):
        await env.register.execute(make_create_input(vendor_id=None, product="ITDR"), SALES)

    # then: Deal이 없다.
    assert env.uow.deals._items == {}


async def test_unknown_vendor_is_reported_before_long_product(env: DealEnv, ctx: Ctx) -> None:
    """없는 Vendor id와 201자 Product가 함께 있으면 Vendor 문구가 먼저 나온다.

    테스트 코드: DE-015
    """
    # when·then: 없는 Vendor id와 201자 Product로 등록한다 → '선택한 Vendor가 없습니다…' 오류다.
    with raises_with(InvalidValueError, UNKNOWN_VENDOR):
        await env.register.execute(make_create_input(vendor_id=new_id(), product="a" * 201), SALES)


async def test_long_product_is_reported_before_owner(env: DealEnv, ctx: Ctx) -> None:
    """201자 Product와 퇴사 Owner가 함께 있으면 Product 문구가 먼저 나온다.

    테스트 코드: DE-017
    """
    # when·then: 201자 Product와 퇴사 Owner로 등록한다 → 'Product는 200자 이내…' 오류다.
    #   (전제: 퇴사한 sales와 Vendor SAP)
    with raises_with(InvalidValueError, PRODUCT_LONG):
        await env.register.execute(
            make_create_input(
                vendor_id=ctx.sap, product="a" * 201, owner_user_id=ctx.resigned_owner
            ),
            SALES,
        )


async def test_product_with_nul_is_rejected_and_stores_nothing(env: DealEnv, ctx: Ctx) -> None:
    """Product의 NUL 문자는 거절되고 저장되지 않는다.

    테스트 코드: DE-011
    """
    # when: 'a\x00b' Product로 등록한다.
    with pytest.raises(InvalidValueError):
        await env.register.execute(make_create_input(product="a\x00b"), SALES)

    # then: InvalidValueError이고 Deal이 없다.
    assert list(env.uow.deals._items) == []


@pytest.mark.parametrize(
    ("field", "column"),
    [("name", "Deal Name"), ("product", "Product"), ("procurement", "구매절차")],
)
async def test_nul_in_a_text_field_is_an_invalid_value_and_stores_nothing(
    env: DealEnv, ctx: Ctx, field: str, column: str
) -> None:
    """Deal Name·Product·구매절차의 NUL 문자는 서버 오류 없이 칸 이름이 든 422 문구다.

    테스트 코드: DE-011
    """
    # when: 그 칸에 NUL이 든 값을 넣어 등록한다 (전제: NUL 문자가 공백으로 감싸진 값)
    with raises_with(InvalidValueError, f"{column}에는 NUL 문자를 쓸 수 없습니다"):
        await env.register.execute(make_create_input(**{field: " a\x00b "}), SALES)

    # then: 칸 이름이 든 NUL 문구의 오류이고 아무것도 저장되지 않는다
    assert env.uow.deals._items == {}


async def test_a_resigned_sales_user_cannot_be_the_owner(env: DealEnv, ctx: Ctx) -> None:
    """퇴사한 sales를 Owner로 지정하면 퇴사 문구의 422다.

    테스트 코드: DE-013
    """
    # when: 그 사용자를 Owner로 등록한다 (전제: 퇴사 처리된 sales (ctx))
    with raises_with(InvalidValueError, OWNER_RESIGNED):
        await env.register.execute(make_create_input(owner_user_id=ctx.resigned_owner), SALES)

    # then: 퇴사 문구의 오류이고 Deal이 없다
    assert env.uow.deals._items == {}


@pytest.mark.parametrize(
    ("customer", "expected"),
    [
        (make_draft(company=""), CUSTOMER_COMPANY),
        (make_draft(name=""), CUSTOMER_NAME),
    ],
)
async def test_a_blank_customer_company_or_name_is_rejected_and_no_contact_is_left(
    env: DealEnv, ctx: Ctx, customer: ContactDraftInput, expected: str
) -> None:
    """고객 회사명·담당자명이 비면 Deal 폼 문구로 거절하고 새 연락처도 남지 않는다.

    테스트 코드: DE-023
    """
    # when: 고객 회사명 또는 담당자명을 비우고 파트너는 새 입력으로 등록한다
    with raises_with(InvalidValueError, expected):
        await env.register.execute(
            make_create_input(customer=customer, partner=make_draft(company="코어테크", name="민")),
            SALES,
        )

    # then: 해당 문구의 오류이고 Deal·연락처가 하나도 없다
    assert env.uow.deals._items == {}
    assert env.uow.contacts._items == {}
