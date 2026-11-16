"""head 스키마의 deals 테이블: 컬럼, PK, CHECK, codes 복합 FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from typing import TYPE_CHECKING, Any, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import MISSING_ID, new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = {
    "id",  # BIGINT 대리 키(내부 전용). 업무 키는 deal_code
    "deal_code",
    "name",
    "owner_user_id",
    "vendor_id",  # Vendor 관리: 등록 목록의 id(NULL = 선택 안 함)
    "product",  # 자유 텍스트(NOT NULL, 미입력 "")
    "users",
    "status_kind",
    "status_key",
    "forecast_kind",
    "forecast_key",
    "revenue_amount",
    "revenue_date",
    "customer_id",
    "quote_submitted",
    "quote_submitted_date",
    "poc_state",
    "poc_completed_date",
    "procurement",
    "created_at",
    "updated_at",
    "status_changed_on",  # 현재 Status에 들어온 업무 날짜(date)
}
REMOVED_COLUMNS = {"code", "stage", "partner_id", "registered_by_user_id", "revenue_currency"}
INDEXES = {
    "ix_deals_owner_user_id",
    "ix_deals_status_key",
    "ix_deals_forecast_key",
    "ix_deals_revenue_date",
    "ix_deals_updated_at",
    "ix_deals_customer_id",
    "ix_deals_vendor_id",
}
COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = 'deals'"
)
PRIMARY_KEY = (
    "select a.attname from pg_constraint c join pg_attribute a"
    " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = 'deals'::regclass and c.contype = 'p'"
)
UNIQUE_KEYS = (
    "select c.conname, array_agg(a.attname) from pg_constraint c join pg_attribute a"
    " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = 'deals'::regclass and c.contype = 'u' group by c.conname"
)
CONSTRAINT_NAMES = "select conname from pg_constraint where conrelid = 'deals'::regclass"
INDEX_NAMES = "select indexname from pg_indexes where schemaname = 'public' and tablename = :t"
CODE_FKS = (
    "select conname, confdeltype::text, array_length(conkey, 1) from pg_constraint"
    " where conrelid = 'deals'::regclass and confrelid = 'codes'::regclass"
)
CODES_UNIQUE = (
    "select conname from pg_constraint"
    " where conrelid = 'codes'::regclass and contype = 'u' and conname = 'uq_codes_kind_key'"
)


async def _customer(session: AsyncSession) -> int:
    return await insert_contact(session)


async def test_the_columns_are_exactly_the_new_model(session: AsyncSession) -> None:
    """deals 컬럼은 새 모델과 정확히 같다."""
    # when: 컬럼 정보를 조회한다 (전제: head 스키마의 임시 DB)
    rows = (await session.execute(text(COLUMN_INFO))).all()
    columns = {r.column_name: r for r in rows}

    # then: 컬럼 집합·타입·필수 여부가 새 모델과 같고 제거된 컬럼은 없다
    assert set(columns) == COLUMNS
    assert not REMOVED_COLUMNS & set(columns)
    assert columns["deal_code"].character_maximum_length == 13
    assert columns["revenue_amount"].data_type == "bigint"
    assert columns["users"].data_type == "integer"
    assert columns["users"].is_nullable == "NO"
    for required in (
        "name",
        "owner_user_id",
        "users",
        "status_key",
        "forecast_key",
        "revenue_date",
    ):
        assert columns[required].is_nullable == "NO", required


async def test_id_is_the_primary_key_and_deal_code_is_unique(session: AsyncSession) -> None:
    """id가 PK이고 deal_code는 유니크다."""
    # when: PK와 유니크 키를 조회한다
    pk_columns = {r[0] for r in (await session.execute(text(PRIMARY_KEY))).all()}
    unique = (await session.execute(text(UNIQUE_KEYS))).all()

    # then: PK는 id, 유니크 키는 deal_code 하나다
    assert pk_columns == {"id"}
    assert [(r[0], list(r[1])) for r in unique] == [("uq_deals_deal_code", ["deal_code"])]


async def test_the_old_stage_change_table_is_gone(session: AsyncSession) -> None:
    """옛 단계 변경 테이블은 없고 새 테이블들이 있다."""
    # when: 테이블 목록을 조회한다
    tables = {
        r[0]
        for r in (
            await session.execute(
                text("select tablename from pg_tables where schemaname = 'public'")
            )
        ).all()
    }

    # then: deal_stage_changes는 없고 새 Deal 관련 테이블이 있다
    assert "deal_stage_changes" not in tables
    assert {"deals", "deal_partners", "deal_bant_labels", "deal_history", "deal_actions"} <= tables


async def test_the_named_check_constraints_exist(session: AsyncSession) -> None:
    """이름 있는 CHECK 제약이 존재한다."""
    # when: deals의 제약 이름을 조회한다
    names = {r[0] for r in (await session.execute(text(CONSTRAINT_NAMES))).all()}

    # then: 정해진 CHECK 제약이 모두 있다
    assert {
        "ck_deals_code_format",
        "ck_deals_users_positive",
        "ck_deals_status_kind",
        "ck_deals_forecast_kind",
        "ck_deals_amount_range",
        "ck_deals_won_sync",
    } <= names


async def test_the_filter_and_sort_indexes_exist(session: AsyncSession) -> None:
    """필터·정렬 인덱스가 존재한다."""
    # when: deals의 인덱스 이름을 조회한다
    indexes = {r[0] for r in (await session.execute(text(INDEX_NAMES), {"t": "deals"})).all()}

    # then: 정해진 인덱스가 모두 있다
    assert indexes >= INDEXES


async def test_status_and_forecast_reference_codes_with_a_composite_restrict_key(
    session: AsyncSession,
) -> None:
    """Status와 Forecast는 codes를 복합키 RESTRICT FK로 참조한다."""
    # when: codes를 참조하는 FK를 조회한다
    rows = (await session.execute(text(CODE_FKS))).all()

    # then: 두 FK가 RESTRICT이고 키가 두 컬럼이며 codes에 유니크 키가 있다
    assert {(r[0], r[1].strip(), r[2]) for r in rows} == {
        ("fk_deals_status_code", "r", 2),
        ("fk_deals_forecast_code", "r", 2),
    }
    assert (await session.execute(text(CODES_UNIQUE))).scalar_one() == "uq_codes_kind_key"


@pytest.mark.parametrize("code", ["20261016-a001", "2026101-A001", "20261016-A00", "DEAL-001", "x"])
async def test_a_malformed_deal_code_is_rejected(session: AsyncSession, code: str) -> None:
    """형식이 틀린 Deal 코드는 거부한다."""
    # given: 고객 연락처 (잘못된 코드)
    customer = await _customer(session)

    # when·then: 잘못된 코드로 Deal을 넣으면 코드 형식 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_deals_code_format"):
        await insert_deal(session, customer, code=code)


async def test_a_well_formed_deal_code_is_accepted(session: AsyncSession) -> None:
    """형식이 맞는 Deal 코드는 저장된다."""
    # given: 고객 연락처 (올바른 코드)
    customer = await _customer(session)

    # when: 올바른 코드로 Deal을 넣는다
    result = await insert_deal(session, customer, code="20261016-Z9A0")
    # then: 그 코드가 반환된다
    assert result == "20261016-Z9A0"


@pytest.mark.parametrize("amount", [0, -1, 2**53])
async def test_an_amount_outside_one_to_the_safe_maximum_is_rejected(
    session: AsyncSession, amount: int
) -> None:
    """금액이 1~안전 최댓값 밖이면 거부한다."""
    # given: 고객 연락처 (금액 범위 밖)
    customer = await _customer(session)

    # when·then: 범위 밖 금액으로 넣으면 금액 범위 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_deals_amount_range"):
        await insert_deal(session, customer, amount=amount)


@pytest.mark.parametrize("amount", [1, 2**53 - 1])
async def test_the_amount_boundaries_are_accepted(session: AsyncSession, amount: int) -> None:
    """금액 경계값은 허용한다."""
    # given: 고객 연락처 (금액 경계값)
    customer = await _customer(session)

    # when·then: 경계 금액으로 넣으면 오류 없이 저장된다
    await insert_deal(session, customer, amount=amount)


async def test_negative_users_is_rejected(session: AsyncSession) -> None:
    """음수 사용자 수는 거부한다."""
    # given: 고객 연락처 (음수 사용자 수)
    customer = await _customer(session)

    # when·then: users -1로 넣으면 users 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_deals_users_positive"):
        await insert_deal(session, customer, users=-1)


@pytest.mark.parametrize("users", [0, 1, 2_147_483_647])
async def test_users_accepts_zero_up_to_the_integer_maximum(
    session: AsyncSession, users: int
) -> None:
    """사용자 수는 0부터 정수 최댓값까지 허용한다."""
    # given: 고객 연락처 (사용자 수 경계값)
    customer = await _customer(session)

    # when·then: 경계 값으로 넣으면 오류 없이 저장된다
    await insert_deal(session, customer, users=users)


async def test_users_is_required(session: AsyncSession) -> None:
    """사용자 수는 필수다."""
    # given: 고객 연락처 (사용자 수 누락)
    customer = await _customer(session)

    # when·then: users를 비워 넣으면 NOT NULL 위반이다
    with pytest.raises(IntegrityError, match=r"not-null|null value"):
        await insert_deal(session, customer, users=None)


async def test_users_check_is_a_non_negative_bound(session: AsyncSession) -> None:
    """사용자 수 CHECK는 0 이상 경계이고 NULL을 허용하지 않는다."""
    # when: 제약 정의를 조회한다
    definition = await session.scalar(
        text(
            "select pg_get_constraintdef(oid) from pg_constraint"
            " where conname = 'ck_deals_users_positive'"
        )
    )

    # then: 정의는 users >= 0이며 IS NULL 분기가 없다
    assert definition is not None
    assert "users >= 0" in definition
    assert "IS NULL" not in definition.upper()


@pytest.mark.parametrize(
    ("status_key", "forecast_key"),
    [("contract_completed", "pipeline"), ("contract_completed", "lost"), ("prospecting", "won")],
)
async def test_closed_status_and_won_forecast_must_come_together(
    session: AsyncSession, status_key: str, forecast_key: str
) -> None:
    """종료 Status와 Won Forecast는 함께여야 한다."""
    # given: 고객 연락처 (종료 Status·Forecast 조합)
    customer = await _customer(session)

    # when·then: 짝이 맞지 않는 조합으로 넣으면 Won 동기화 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_deals_won_sync"):
        await insert_deal(session, customer, status_key=status_key, forecast_key=forecast_key)


async def test_a_consistent_closed_deal_is_accepted(session: AsyncSession) -> None:
    """일관된 종료 Deal은 저장된다."""
    # given: 고객 연락처 (일관된 종료 Deal)
    customer = await _customer(session)

    # when·then: 계약완료와 Won 조합으로 넣으면 오류 없이 저장된다
    await insert_deal(session, customer, status_key="contract_completed", forecast_key="won")


async def test_an_unknown_status_key_is_rejected_by_the_codes_foreign_key(
    session: AsyncSession,
) -> None:
    """없는 Status 키는 codes FK가 거부한다."""
    # given: 고객 연락처 (없는 Status 키)
    customer = await _customer(session)

    # when·then: 없는 Status 키로 넣으면 Status FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_status_code"):
        await insert_deal(session, customer, status_key="unknown_status")


async def test_an_unknown_forecast_key_is_rejected_by_the_codes_foreign_key(
    session: AsyncSession,
) -> None:
    """없는 Forecast 키는 codes FK가 거부한다."""
    # given: 고객 연락처 (없는 Forecast 키)
    customer = await _customer(session)

    # when·then: 없는 Forecast 키로 넣으면 Forecast FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_forecast_code"):
        await insert_deal(session, customer, forecast_key="unknown_forecast")


async def test_a_forecast_key_cannot_be_used_as_a_status_key(session: AsyncSession) -> None:
    """Forecast 키를 Status 키로 쓸 수 없다."""
    # given: 고객 연락처 (Forecast 키를 Status로 사용)
    customer = await _customer(session)

    # when·then: Forecast 키를 Status로 넣으면 Status FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_status_code"):
        await insert_deal(session, customer, status_key="pipeline", forecast_key="pipeline")


async def test_a_code_in_use_cannot_be_deleted(session: AsyncSession) -> None:
    """사용 중인 코드는 삭제할 수 없다."""
    # given: 고객 연락처 (사용 중인 코드)
    customer = await _customer(session)
    # given: 해당 Status를 쓰는 Deal
    await insert_deal(session, customer, status_key="introduction")

    # when·then: 그 코드를 삭제하면 Status FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_status_code"):
        await session.execute(
            text("delete from codes where kind = 'status' and key = 'introduction'")
        )


@pytest.mark.parametrize("field", ["quote_submitted", "poc_state"])
async def test_quote_and_poc_values_are_closed_sets(session: AsyncSession, field: str) -> None:
    """견적·PoC 값은 닫힌 집합이다."""
    # given: 고객 연락처 (견적·PoC 값)
    customer = await _customer(session)

    # when·then: 집합 밖 값으로 넣으면 무결성 오류다
    with pytest.raises(IntegrityError):
        await insert_deal(
            session, customer, **cast("dict[str, Any]", {field: "ZZZ"})
        )  # 3자라 길이는 통과, 닫힌 집합 밖


@pytest.mark.parametrize(
    ("field", "value"),
    [("quote_submitted", "YES"), ("quote_submitted", "NO"), ("poc_state", "ING")],
)
async def test_quote_and_poc_wire_values_are_accepted(
    session: AsyncSession, field: str, value: str
) -> None:
    """견적·PoC의 전송 값은 허용한다."""
    # given: 고객 연락처 (견적·PoC wire 값)
    customer = await _customer(session)

    # when·then: 허용된 값으로 넣으면 오류 없이 저장된다
    await insert_deal(session, customer, **cast("dict[str, Any]", {field: value}))


async def test_a_missing_customer_is_rejected(session: AsyncSession) -> None:
    """없는 고객은 거부한다."""
    # when·then: 없는 고객 id로 넣으면 고객 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_customer_id_contacts"):
        await insert_deal(session, MISSING_ID)


async def test_a_missing_owner_is_rejected(session: AsyncSession) -> None:
    """없는 담당자는 거부한다."""
    # given: 고객 연락처 (없는 담당자)
    customer = await _customer(session)

    # when·then: 없는 사용자 id를 담당자로 넣으면 담당자 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_owner_user_id_users"):
        await insert_deal(session, customer, owner_user_id=new_id())


async def test_a_contact_used_by_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    """Deal이 쓰는 연락처는 삭제할 수 없다."""
    # given: 고객 연락처 (연락처 삭제 시도)
    customer = await _customer(session)
    # given: 그 연락처를 쓰는 Deal
    await insert_deal(session, customer)

    # when·then: 연락처를 삭제하면 고객 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_customer_id_contacts"):
        await session.execute(text("delete from contacts where id = :id"), {"id": customer})


async def test_a_user_who_owns_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    """Deal을 소유한 사용자는 삭제할 수 없다."""
    # given: 고객 연락처 (소유자 삭제 시도)
    customer = await _customer(session)
    # given: 담당 사용자
    owner = await insert_user(session, "owner-x")
    # given: 그 사용자가 소유한 Deal
    await insert_deal(session, customer, owner_user_id=owner)

    # when·then: 사용자를 삭제하면 담당자 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_owner_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": owner})
