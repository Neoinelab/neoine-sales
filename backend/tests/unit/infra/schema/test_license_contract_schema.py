"""head 스키마의 license_contracts·license_contract_attachments(AC1·AC3·AC5·AC21·AC22).

제약은 원시 INSERT로 직접 어겨 보고 제약·인덱스 이름으로 거절되는지 확인한다(도메인 검증을
거치지 않는다). 임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.contract_rows import (
    insert_contract,
    insert_contract_attachment,
    insert_issued_contract,
)
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import MAX_ID, MISSING_ID
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

ENDED_ON = date(2026, 6, 1)
COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable, column_default,"
    " is_identity, identity_generation, identity_maximum"
    " from information_schema.columns where table_schema = 'public' and table_name = :table"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, a.attname"
    " from pg_constraint c"
    " join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = cast(cast(:table as text) as regclass) and c.contype = 'f'"
)
INDEXES = (
    "select indexname, indexdef from pg_indexes where schemaname = 'public' and tablename = :table"
)
CONSTRAINT_NAMES = (
    "select conname from pg_constraint where conrelid = cast(cast(:table as text) as regclass)"
)


async def _deal(session: AsyncSession, login: str = "lc-owner") -> tuple[str, int]:
    """(Deal code, 사용자 id)."""
    user = await insert_user(session, login)
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner_user_id=user)
    return code, user


async def test_license_contracts_columns_types_and_nullability(session: AsyncSession) -> None:
    """license_contracts 컬럼의 타입과 NULL 허용 여부가 명세와 같다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    rows = (await session.execute(text(COLUMNS), {"table": "license_contracts"})).all()
    # when: information_schema에서 컬럼을 읽는다
    columns = {
        r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows
    }

    # then: 컬럼 이름·타입·nullable이 명세와 같다
    assert columns == {
        "id": ("bigint", None, "NO"),
        "deal_id": ("bigint", None, "NO"),
        "status": ("character varying", 20, "NO"),
        "license_start": ("date", None, "YES"),
        "license_end": ("date", None, "YES"),
        "term_amount": ("smallint", None, "YES"),
        "term_unit": ("character varying", 10, "YES"),
        "tech_owner": ("character varying", 100, "NO"),
        "inspection_cycle": ("character varying", 20, "NO"),
        "note": ("text", None, "NO"),
        "renewed_from_id": ("bigint", None, "YES"),
        "ended_on": ("date", None, "YES"),
        "created_by_user_id": ("bigint", None, "NO"),
        "updated_by_user_id": ("bigint", None, "NO"),
        "created_at": ("timestamp with time zone", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


@pytest.mark.parametrize("table", ["license_contracts", "license_contract_attachments"])
async def test_the_primary_key_is_a_bigint_identity_by_default(
    session: AsyncSession, table: str
) -> None:
    """PK id는 BY DEFAULT identity BIGINT이고 최댓값이 2^53-1이다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    rows = (await session.execute(text(COLUMNS), {"table": table})).all()
    # when: id 컬럼 정보를 읽는다
    row = next(r for r in rows if r.column_name == "id")

    # then: bigint, identity BY DEFAULT, 최대값 MAX_ID
    assert row.data_type == "bigint"
    assert row.is_identity == "YES"
    assert row.identity_generation == "BY DEFAULT"
    assert int(row.identity_maximum) == MAX_ID == 9_007_199_254_740_991


async def test_contract_attachment_columns_types_and_nullability(session: AsyncSession) -> None:
    """license_contract_attachments 컬럼의 타입과 NULL 허용 여부가 명세와 같다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    rows = (await session.execute(text(COLUMNS), {"table": "license_contract_attachments"})).all()
    # when: information_schema에서 컬럼을 읽는다
    columns = {
        r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows
    }

    # then: 컬럼 이름·타입·nullable이 명세와 같다
    assert columns == {
        "id": ("bigint", None, "NO"),
        "contract_id": ("bigint", None, "NO"),
        "file_name": ("character varying", 255, "NO"),
        "description": ("character varying", 100, "NO"),
        "mime": ("character varying", 255, "NO"),
        "size_bytes": ("bigint", None, "NO"),
        "storage_key": ("character varying", 32, "NO"),
        "uploaded_by_user_id": ("bigint", None, "NO"),
        "uploaded_at": ("timestamp with time zone", None, "NO"),
        "created_at": ("timestamp with time zone", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_contract_foreign_keys_and_delete_rules(session: AsyncSession) -> None:
    """계약의 외래 키와 삭제 규칙이 명세와 같다."""
    # when: 외래 키 정의를 읽는다 (전제: head 스키마의 임시 DB 세션과 Deal·사용자)
    rows = (await session.execute(text(FOREIGN_KEYS), {"table": "license_contracts"})).all()

    # then: Deal CASCADE, 사용자 RESTRICT, 원본 SET NULL
    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_license_contracts_deal_id_deals", "deals", "c", "deal_id"),
        (
            "fk_license_contracts_renewed_from_id_license_contracts",
            "license_contracts",
            "n",
            "renewed_from_id",
        ),
        ("fk_license_contracts_created_by_user_id_users", "users", "r", "created_by_user_id"),
        ("fk_license_contracts_updated_by_user_id_users", "users", "r", "updated_by_user_id"),
    }


async def test_contract_attachment_foreign_keys_and_delete_rules(session: AsyncSession) -> None:
    """첨부의 외래 키와 삭제 규칙이 명세와 같다."""
    # when: 외래 키 정의를 읽는다 (전제: head 스키마의 임시 DB 세션과 Deal·사용자)
    rows = (
        await session.execute(text(FOREIGN_KEYS), {"table": "license_contract_attachments"})
    ).all()

    # then: 계약 CASCADE, 업로더 RESTRICT
    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        (
            "fk_license_contract_attachments_contract_id_license_contracts",
            "license_contracts",
            "c",
            "contract_id",
        ),
        (
            "fk_license_contract_attachments_uploaded_by_user_id_users",
            "users",
            "r",
            "uploaded_by_user_id",
        ),
    }


async def test_the_contract_indexes_exist_and_only_the_issued_one_is_unique(
    session: AsyncSession,
) -> None:
    """계약 인덱스가 있고 유니크는 PK와 발급 부분 인덱스뿐이다.

    테스트 코드: LC-042
    """
    # when: 인덱스 정의를 읽는다 (전제: head 스키마의 임시 DB 세션과 Deal·사용자)
    definitions = {
        r.indexname: r.indexdef
        for r in (await session.execute(text(INDEXES), {"table": "license_contracts"})).all()
    }

    # then: 인덱스 목록이 명세와 같고 발급 인덱스는 deal_id 부분 유니크다
    assert set(definitions) == {
        "pk_license_contracts",
        "uq_license_contracts_deal_id_issued",
        "ix_license_contracts_deal_id",
        "ix_license_contracts_license_end_id",
        "ix_license_contracts_renewed_from_id",
        "ix_license_contracts_created_by_user_id",
        "ix_license_contracts_updated_by_user_id",
    }
    unique = sorted(name for name, d in definitions.items() if "UNIQUE" in d)
    assert unique == ["pk_license_contracts", "uq_license_contracts_deal_id_issued"]
    issued = definitions["uq_license_contracts_deal_id_issued"]
    assert "(deal_id)" in issued
    assert "issued_new" in issued
    assert "issued_renewal" in issued
    assert "(license_end, id)" in definitions["ix_license_contracts_license_end_id"]


async def test_the_contract_attachment_indexes_exist(session: AsyncSession) -> None:
    """첨부 인덱스(계약+파일명 유니크, 저장 키 유니크)가 있다.

    테스트 코드: LC-064
    """
    # when: 인덱스 정의를 읽는다 (전제: head 스키마의 임시 DB 세션과 Deal·사용자)
    definitions = {
        r.indexname: r.indexdef
        for r in (
            await session.execute(text(INDEXES), {"table": "license_contract_attachments"})
        ).all()
    }

    # then: 계약+이름, 저장 키 유니크 인덱스가 있다
    assert {
        "pk_license_contract_attachments",
        "ix_license_contract_attachments_contract_id_uploaded_at",
        "ix_license_contract_attachments_uploaded_by_user_id",
    } <= set(definitions)
    names = {
        r[0]
        for r in (
            await session.execute(text(CONSTRAINT_NAMES), {"table": "license_contract_attachments"})
        ).all()
    }
    assert "uq_license_contract_attachments_contract_id_file_name" in names | set(definitions)
    assert "uq_license_contract_attachments_storage_key" in names | set(definitions)


async def test_the_schema_has_no_integrity_violations(session: AsyncSession) -> None:
    """점검 도구가 계약 테이블에서 무결성 위반을 찾지 못한다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    exists = (
        await session.execute(text("select to_regclass('public.license_contracts')"))
    ).scalar()

    assert exists is not None  # 점검 대상 테이블이 있어야 의미가 있다
    # when: 스키마 무결성을 점검한다
    result = await check_schema(session)
    # then: 위반 목록이 비어 있다
    assert result == []


async def test_a_valid_not_issued_row_and_a_valid_issued_row_are_accepted(
    session: AsyncSession,
) -> None:
    """올바른 미발급 행과 발급 행은 저장된다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 미발급 행과 발급 행을 INSERT한다
    await insert_contract(session, code, user)
    await insert_issued_contract(session, code, user)

    count = (await session.execute(text("select count(*) from license_contracts"))).scalar_one()
    # then: 행이 2건이다
    assert count == 2


async def test_one_deal_may_have_many_non_issued_contracts(session: AsyncSession) -> None:
    """한 Deal에 미발급·종료 계약은 여러 건 둘 수 있다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    for _ in range(3):
        await insert_contract(session, code, user)  # 미발급은 여러 건 가능
    # when: 미발급 계약을 여러 건 INSERT한다
    await insert_contract(
        session,
        code,
        user,
        status="ended",
        license_start=date(2026, 1, 1),
        license_end=date(2026, 12, 31),
        term_amount=1,
        term_unit="year",
        ended_on=ENDED_ON,
    )

    # then: 행이 4건이다
    count = (await session.execute(text("select count(*) from license_contracts"))).scalar_one()
    assert count == 4


@pytest.mark.parametrize("second", ["issued_new", "issued_renewal"])
async def test_partial_unique_rejects_second_issued_for_deal(
    session: AsyncSession, second: str
) -> None:
    """한 Deal의 두 번째 발급 계약은 부분 유니크로 거절된다.

    테스트 코드: LC-042
    """
    # given: 발급 계약이 있는 Deal
    code, user = await _deal(session)
    await insert_issued_contract(session, code, user)

    # when: 두 번째 발급 계약을 INSERT한다
    with pytest.raises(IntegrityError, match="uq_license_contracts_deal_id_issued"):
        await insert_issued_contract(session, code, user, status=second)
    # then: IntegrityError uq_license_contracts_deal_id_issued


async def test_two_deals_may_each_have_an_issued_contract(session: AsyncSession) -> None:
    """Deal마다 발급 계약을 하나씩 둘 수 있다.

    테스트 코드: LC-042
    """
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)
    customer = await insert_contact(session)
    other = await insert_deal(session, customer, owner_user_id=user, code="20261016-A002")

    await insert_issued_contract(session, code, user)
    # when: 두 Deal에 발급 계약을 각각 INSERT한다
    await insert_issued_contract(session, other, user)
    # then: 오류 없이 저장된다


async def test_status_outside_the_four_values_is_rejected(session: AsyncSession) -> None:
    """네 값 밖의 상태는 CHECK로 거절된다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 위반하는 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_status"):
        await insert_contract(session, code, user, status="expired")
    # then: IntegrityError ck_license_contracts_status


async def test_inspection_cycle_outside_the_five_values_is_rejected(
    session: AsyncSession,
) -> None:
    """다섯 값 밖의 점검주기는 CHECK로 거절된다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 위반하는 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_inspection_cycle"):
        await insert_contract(session, code, user, inspection_cycle="weekly")
    # then: IntegrityError ck_license_contracts_inspection_cycle


@pytest.mark.parametrize("amount", [0, 100])
async def test_term_amount_outside_one_to_ninety_nine_is_rejected(
    session: AsyncSession, amount: int
) -> None:
    """기간 수량이 1~99 밖이면 CHECK로 거절된다.

    테스트 코드: LC-044
    """
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 위반하는 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_term_amount"):
        await insert_issued_contract(session, code, user, term_amount=amount)
    # then: IntegrityError ck_license_contracts_term_amount


async def test_term_unit_outside_month_and_year_is_rejected(session: AsyncSession) -> None:
    """기간 단위가 month·year 밖이면 CHECK로 거절된다.

    테스트 코드: LC-044
    """
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 위반하는 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_term_unit"):
        await insert_issued_contract(session, code, user, term_unit="week")
    # then: IntegrityError ck_license_contracts_term_unit


async def test_the_four_period_columns_are_all_null_or_all_set(session: AsyncSession) -> None:
    """기간 네 칸은 모두 NULL이거나 모두 채워져야 한다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 일부만 채운 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_term_complete"):
        await insert_issued_contract(session, code, user, term_amount=None)
    # then: IntegrityError ck_license_contracts_term_complete


async def test_a_not_issued_contract_cannot_have_a_period(session: AsyncSession) -> None:
    """미발급 계약에는 기간을 넣을 수 없다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 기간이 있는 미발급 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_not_issued_no_term"):
        await insert_contract(
            session,
            code,
            user,
            license_start=date(2026, 1, 1),
            license_end=date(2026, 12, 31),
            term_amount=1,
            term_unit="year",
        )
    # then: IntegrityError ck_license_contracts_not_issued_no_term


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal"])
async def test_an_issued_contract_must_have_a_period(session: AsyncSession, status: str) -> None:
    """발급 상태 계약에는 기간이 필수다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 기간 없는 발급 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_issued_has_term"):
        await insert_contract(session, code, user, status=status)
    # then: IntegrityError ck_license_contracts_issued_has_term


async def test_the_end_date_cannot_be_before_the_start_date(session: AsyncSession) -> None:
    """종료일이 시작일보다 앞서면 거절된다."""
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: 종료일이 시작일보다 앞선 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_end_after_start"):
        await insert_issued_contract(
            session, code, user, license_start=date(2026, 12, 31), license_end=date(2026, 1, 1)
        )
    # then: IntegrityError ck_license_contracts_end_after_start


async def test_ended_on_is_set_exactly_when_the_status_is_ended(session: AsyncSession) -> None:
    """종료 상태는 ended_on이 있어야 한다.

    테스트 코드: LC-087
    """
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: ended_on 없는 종료 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_ended_has_date"):
        await insert_issued_contract(session, code, user, status="ended")  # ended_on 없음
    # then: IntegrityError ck_license_contracts_ended_has_date


async def test_ended_on_without_the_ended_status_is_rejected(session: AsyncSession) -> None:
    """종료가 아닌 상태에 ended_on이 있으면 거절된다.

    테스트 코드: LC-087
    """
    # given: head 스키마의 임시 DB 세션과 Deal·사용자
    code, user = await _deal(session)

    # when: ended_on이 있는 비종료 행을 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contracts_ended_has_date"):
        await insert_contract(session, code, user, ended_on=ENDED_ON)
    # then: IntegrityError ck_license_contracts_ended_has_date


async def test_a_missing_deal_is_rejected_by_the_foreign_key(session: AsyncSession) -> None:
    """없는 Deal을 가리키는 계약은 외래 키로 거절된다."""
    # given: 사용자만 있는 임시 DB
    _, user = await _deal(session)

    # when: 없는 Deal 코드로 INSERT한다
    with pytest.raises(IntegrityError, match="fk_license_contracts_deal_id_deals"):
        await insert_contract(session, "20261016-A001", user, deal_id=MISSING_ID)
    # then: IntegrityError fk_license_contracts_deal_id_deals


async def test_a_missing_creator_is_rejected_by_the_foreign_key(session: AsyncSession) -> None:
    """없는 사용자가 등록자인 계약은 외래 키로 거절된다."""
    # given: Deal만 있는 임시 DB
    code, _ = await _deal(session)

    # when: 없는 사용자로 INSERT한다
    with pytest.raises(IntegrityError, match="fk_license_contracts_created_by_user_id_users"):
        await insert_contract(session, code, MISSING_ID)
    # then: IntegrityError fk_license_contracts_created_by_user_id_users


async def test_deleting_a_deal_cascades_to_contracts_and_their_attachments(
    session: AsyncSession,
) -> None:
    """Deal을 삭제하면 계약과 그 첨부가 함께 지워진다.

    테스트 코드: LC-080
    """
    # given: 첨부가 있는 발급 계약이 있는 Deal
    code, user = await _deal(session)
    contract = await insert_issued_contract(session, code, user)
    await insert_contract_attachment(session, contract, user)

    # when: Deal을 삭제한다
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    # then: 계약·첨부 행이 0건이다
    for table in ("license_contracts", "license_contract_attachments"):
        count = (await session.execute(text(f"select count(*) from {table}"))).scalar_one()  # noqa: S608
        assert count == 0, table


async def test_deleting_a_contract_cascades_to_its_attachments(session: AsyncSession) -> None:
    """계약을 삭제하면 그 첨부가 함께 지워진다.

    테스트 코드: LC-058
    """
    # given: 첨부가 있는 계약
    code, user = await _deal(session)
    contract = await insert_contract(session, code, user)
    await insert_contract_attachment(session, contract, user)

    # when: 계약을 삭제한다
    await session.execute(text("delete from license_contracts where id = :id"), {"id": contract})

    # then: 첨부 행이 0건이다
    count = (
        await session.execute(text("select count(*) from license_contract_attachments"))
    ).scalar_one()
    assert count == 0


async def test_deleting_the_origin_contract_sets_the_renewal_link_to_null(
    session: AsyncSession,
) -> None:
    """원본 계약을 삭제하면 후속 계약의 원본 연결이 NULL이 된다.

    테스트 코드: LC-060
    """
    # given: 원본 계약과 그 갱신 계약
    code, user = await _deal(session)
    origin = await insert_contract(
        session,
        code,
        user,
        status="ended",
        license_start=date(2026, 1, 1),
        license_end=date(2026, 12, 31),
        term_amount=1,
        term_unit="year",
        ended_on=ENDED_ON,
    )
    renewal = await insert_issued_contract(session, code, user, status="issued_renewal")
    await session.execute(
        text("update license_contracts set renewed_from_id = :o where id = :r"),
        {"o": origin, "r": renewal},
    )

    # when: 원본 계약을 삭제한다
    await session.execute(text("delete from license_contracts where id = :id"), {"id": origin})

    # then: renewed_from_id가 NULL이다
    link = (
        await session.execute(
            text("select renewed_from_id from license_contracts where id = :id"), {"id": renewal}
        )
    ).scalar_one()
    assert link is None


async def test_the_same_file_name_in_one_contract_is_rejected(session: AsyncSession) -> None:
    """한 계약의 같은 파일명은 유니크로 거절된다.

    테스트 코드: LC-064
    """
    # given: a.pdf가 있는 계약
    code, user = await _deal(session)
    contract = await insert_contract(session, code, user)
    await insert_contract_attachment(session, contract, user, file_name="a.pdf")

    # when: 같은 이름의 첨부를 INSERT한다
    with pytest.raises(
        IntegrityError, match="uq_license_contract_attachments_contract_id_file_name"
    ):
        await insert_contract_attachment(session, contract, user, file_name="a.pdf")
    # then: IntegrityError uq_license_contract_attachments_contract_id_file_name


async def test_the_same_file_name_in_two_contracts_is_accepted(session: AsyncSession) -> None:
    """다른 계약의 같은 파일명은 허용된다.

    테스트 코드: LC-064
    """
    # given: 같은 Deal의 계약 둘
    code, user = await _deal(session)
    first = await insert_contract(session, code, user)
    second = await insert_contract(session, code, user)

    await insert_contract_attachment(session, first, user, file_name="a.pdf")
    # when: 각 계약에 같은 이름의 첨부를 INSERT한다
    await insert_contract_attachment(session, second, user, file_name="a.pdf")
    # then: 오류 없이 저장된다


@pytest.mark.parametrize("size", [-1, 104_857_601])
async def test_attachment_size_outside_zero_to_100mb_is_rejected(
    session: AsyncSession, size: int
) -> None:
    """첨부 크기가 0~100MB 밖이면 CHECK로 거절된다.

    테스트 코드: LC-067
    """
    # given: 계약
    code, user = await _deal(session)
    contract = await insert_contract(session, code, user)

    # when: 음수 또는 100MB 초과 크기로 INSERT한다
    with pytest.raises(IntegrityError, match="ck_license_contract_attachments_size_range"):
        await insert_contract_attachment(session, contract, user, size_bytes=size)
    # then: IntegrityError ck_license_contract_attachments_size_range


@pytest.mark.parametrize("size", [0, 104_857_600])
async def test_attachment_size_boundaries_are_accepted(session: AsyncSession, size: int) -> None:
    """첨부 크기 0과 100MB 정확히는 허용된다.

    테스트 코드: LC-067
    """
    # given: 계약
    code, user = await _deal(session)
    contract = await insert_contract(session, code, user)

    # when: 경계 크기로 INSERT한다
    await insert_contract_attachment(session, contract, user, size_bytes=size)
    # then: 오류 없이 저장된다


async def test_a_duplicate_storage_key_is_rejected(session: AsyncSession) -> None:
    """저장 키가 겹치면 유니크로 거절된다."""
    # given: 첨부가 있는 계약
    code, user = await _deal(session)
    contract = await insert_contract(session, code, user)
    await insert_contract_attachment(
        session, contract, user, file_name="a.pdf", storage_key="k" * 32
    )

    # when: 같은 저장 키의 첨부를 INSERT한다
    with pytest.raises(IntegrityError, match="uq_license_contract_attachments_storage_key"):
        await insert_contract_attachment(
            session, contract, user, file_name="b.pdf", storage_key="k" * 32
        )
    # then: IntegrityError uq_license_contract_attachments_storage_key
