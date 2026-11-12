"""head 스키마의 deal_attachments: 컬럼, 체크, 유니크, FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
storage_settings는 test_storage_settings_schema.py.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.attachment_rows import insert_attachment
from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import MISSING_ID, new_id
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = 'deal_attachments'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_attachments'::regclass and contype = 'f'"
)
CONSTRAINT_NAMES = "select conname from pg_constraint where conrelid = 'deal_attachments'::regclass"
INDEX_NAMES = "select indexname from pg_indexes where tablename = 'deal_attachments'"
COUNT = "select count(*) from deal_attachments"
MAX_BYTES = 104_857_600
COLUMNS = {
    "id",
    "deal_id",
    "file_name",
    "description",
    "mime",
    "size_bytes",
    "storage_key",
    "uploaded_by_user_id",
    "uploaded_at",
    "created_at",
    "updated_at",
}


async def _columns(session: AsyncSession) -> dict[str, tuple[str, int | None, str]]:
    rows = (await session.execute(text(COLUMN_INFO))).all()
    return {r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows}


async def _names(session: AsyncSession, statement: str) -> set[str]:
    return {str(r[0]) for r in (await session.execute(text(statement))).all()}


async def _user(session: AsyncSession) -> int:
    return await insert_user(session, f"u{uuid4().hex[:10]}")


async def _deal(session: AsyncSession, code: str = "20261016-A001") -> tuple[str, int]:
    user = await _user(session)
    return await insert_deal(session, await insert_contact(session), user, code=code), user


async def test_the_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    """deal_attachments 테이블은 계획한 컬럼과 타입을 가진다."""
    # when: 컬럼 정보를 읽는다 (전제: head 스키마)
    columns = await _columns(session)

    # then: 컬럼 집합·길이·타입이 계획과 같다
    assert set(columns) == COLUMNS
    assert {name: columns[name][:2] for name in ("file_name", "description", "mime")} == {
        "file_name": ("character varying", 255),
        "description": ("character varying", 100),
        "mime": ("character varying", 255),
    }
    assert columns["storage_key"][:2] == ("character varying", 32)
    assert columns["size_bytes"][0] == "bigint"
    assert columns["id"][0] == "bigint"
    assert columns["deal_id"][0] == "bigint"
    assert columns["uploaded_by_user_id"][0] == "bigint"
    for name in ("uploaded_at", "created_at", "updated_at"):
        assert columns[name][0] == "timestamp with time zone", name


async def test_every_column_is_required(session: AsyncSession) -> None:
    """모든 컬럼은 NOT NULL이다."""
    # when: 컬럼 정보를 읽는다 (전제: head 스키마)
    columns = await _columns(session)

    # then: NOT NULL인 컬럼이 전체 컬럼과 같다
    assert {name for name, info in columns.items() if info[2] == "NO"} == COLUMNS


async def test_description_defaults_to_an_empty_string(session: AsyncSession) -> None:
    """설명을 생략하고 넣으면 빈 문자열이 기본값이다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when: 설명 없이 행을 넣는다
    await session.execute(
        text(
            "insert into deal_attachments (id, deal_id, file_name, mime, size_bytes,"
            " storage_key, uploaded_by_user_id, uploaded_at, created_at, updated_at) values"
            " (:id, (select id from deals where deal_code = :deal), 'a.pdf', 'application/pdf',"
            " 1, :key, :user, now(), now(), now())"
        ),
        {"id": new_id(), "deal": deal, "key": uuid4().hex, "user": user},
    )

    # then: 설명이 ""다
    assert (await session.execute(text("select description from deal_attachments"))).scalar() == ""


@pytest.mark.parametrize("size", [0, 1, MAX_BYTES])
async def test_a_size_inside_the_range_is_accepted(session: AsyncSession, size: int) -> None:
    """0·1·100MB 크기는 허용된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when: 경계 크기로 행을 넣는다
    await insert_attachment(session, deal, user, size_bytes=size)

    # then: 넣은 크기가 저장된다
    assert (await session.execute(text("select size_bytes from deal_attachments"))).scalar() == size


@pytest.mark.parametrize("size", [-1, MAX_BYTES + 1])
async def test_a_size_outside_the_range_is_rejected(session: AsyncSession, size: int) -> None:
    """음수·100MB 초과 크기는 체크 제약으로 거절된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when·then: 범위 밖 크기로 넣으면 크기 범위 제약 오류다
    with pytest.raises(IntegrityError, match="ck_deal_attachments_size_range"):
        await insert_attachment(session, deal, user, size_bytes=size)


async def test_a_description_of_100_characters_is_accepted(session: AsyncSession) -> None:
    """설명 100자는 허용된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when: 100자 설명으로 넣는다
    await insert_attachment(session, deal, user, description="가" * 100)

    # then: 저장된 길이가 100이다
    length = await session.execute(text("select length(description) from deal_attachments"))
    assert length.scalar() == 100


async def test_a_description_over_100_characters_is_rejected(session: AsyncSession) -> None:
    """설명 101자는 거절된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when·then: 101자 설명으로 넣으면 DB 오류다
    with pytest.raises(DBAPIError):
        await insert_attachment(session, deal, user, description="가" * 101)


async def test_a_file_name_of_255_characters_is_accepted(session: AsyncSession) -> None:
    """파일 이름 255자는 허용된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when: 255자 이름으로 넣는다
    await insert_attachment(session, deal, user, file_name="가" * 255)

    # then: 저장된 길이가 255다
    length = await session.execute(text("select length(file_name) from deal_attachments"))
    assert length.scalar() == 255


async def test_a_file_name_over_255_characters_is_rejected(session: AsyncSession) -> None:
    """파일 이름 256자는 거절된다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when·then: 256자 이름으로 넣으면 DB 오류다
    with pytest.raises(DBAPIError):
        await insert_attachment(session, deal, user, file_name="가" * 256)


async def test_the_same_file_name_twice_in_one_deal_is_rejected(session: AsyncSession) -> None:
    """한 Deal에 같은 이름을 두 번 넣으면 유니크 제약으로 거절된다."""
    # given: "same.pdf"가 들어 있는 Deal
    deal, user = await _deal(session)
    await insert_attachment(session, deal, user, file_name="same.pdf")

    # when·then: 같은 이름을 또 넣으면 이름 유니크 제약 오류다
    with pytest.raises(IntegrityError, match="uq_deal_attachments_deal_id_file_name"):
        await insert_attachment(session, deal, user, file_name="same.pdf")


async def test_the_same_file_name_in_different_deals_is_accepted(session: AsyncSession) -> None:
    """다른 Deal의 같은 이름은 허용된다."""
    # given: 두 Deal
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")

    # when: 두 Deal에 같은 이름을 넣는다
    await insert_attachment(session, deal, user, file_name="same.pdf")
    await insert_attachment(session, other_deal, user, file_name="same.pdf")

    # then: 행이 2건이다
    assert (await session.execute(text(COUNT))).scalar() == 2


async def test_file_names_that_differ_only_in_case_are_different_names(
    session: AsyncSession,
) -> None:
    """대소문자만 다른 이름은 다른 이름이다."""
    # given: Deal과 사용자
    deal, user = await _deal(session)

    # when: 대소문자만 다른 두 이름을 넣는다
    await insert_attachment(session, deal, user, file_name="Report.pdf")
    await insert_attachment(session, deal, user, file_name="report.pdf")

    # then: 행이 2건이다
    assert (await session.execute(text(COUNT))).scalar() == 2


async def test_the_same_storage_key_twice_is_rejected_even_across_deals(
    session: AsyncSession,
) -> None:
    """저장 키는 Deal이 달라도 유일해야 한다."""
    # given: 두 Deal과 한 Deal에 저장된 키
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")
    key = uuid4().hex
    await insert_attachment(session, deal, user, storage_key=key)

    # when·then: 다른 Deal에 같은 키를 넣으면 키 유니크 제약 오류다
    with pytest.raises(IntegrityError, match="uq_deal_attachments_storage_key"):
        await insert_attachment(session, other_deal, user, storage_key=key, file_name="b.pdf")


async def test_an_attachment_of_a_missing_deal_is_rejected(session: AsyncSession) -> None:
    """없는 Deal의 첨부는 FK로 거절된다."""
    # given: 사용자만 있다
    user = await _user(session)

    # when·then: 없는 Deal id로 넣으면 Deal FK 오류다
    with pytest.raises(IntegrityError, match="fk_deal_attachments_deal_id_deals"):
        await insert_attachment(session, "20260101-ZZZZ", user, deal_id=MISSING_ID)


async def test_an_attachment_of_a_missing_uploader_is_rejected(session: AsyncSession) -> None:
    """없는 업로더의 첨부는 FK로 거절된다."""
    # given: Deal만 있다
    deal, _ = await _deal(session)

    # when·then: 없는 사용자 id로 넣으면 업로더 FK 오류다
    with pytest.raises(IntegrityError, match="fk_deal_attachments_uploaded_by_user_id_users"):
        await insert_attachment(session, deal, new_id())


async def test_deleting_the_deal_deletes_its_attachments(session: AsyncSession) -> None:
    """Deal을 지우면 그 첨부도 지워진다(CASCADE)."""
    # given: 첨부 두 건이 있는 Deal
    deal, user = await _deal(session)
    await insert_attachment(session, deal, user, file_name="a.pdf")
    await insert_attachment(session, deal, user, file_name="b.pdf")

    # when: Deal을 지운다
    await session.execute(text("delete from deals where deal_code = :code"), {"code": deal})

    # then: 첨부 행이 0건이다
    assert (await session.execute(text(COUNT))).scalar() == 0


async def test_deleting_the_deal_keeps_the_attachments_of_other_deals(
    session: AsyncSession,
) -> None:
    """Deal을 지워도 다른 Deal의 첨부는 남는다."""
    # given: 두 Deal에 각각 첨부가 있다
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")
    await insert_attachment(session, deal, user)
    await insert_attachment(session, other_deal, user)

    # when: 한 Deal을 지운다
    await session.execute(text("delete from deals where deal_code = :code"), {"code": deal})

    # then: 다른 Deal의 첨부만 남는다
    rows = await session.execute(
        text("select d.deal_code from deal_attachments a join deals d on d.id = a.deal_id")
    )
    assert rows.scalars().all() == [other_deal]


async def test_a_user_who_uploaded_an_attachment_cannot_be_deleted(session: AsyncSession) -> None:
    """첨부를 올린 사용자는 지울 수 없다(RESTRICT)."""
    # given: 첨부를 올린 사용자
    deal, _ = await _deal(session)
    uploader = await _user(session)
    await insert_attachment(session, deal, uploader)

    # when·then: 그 사용자를 지우면 업로더 FK 오류다
    with pytest.raises(IntegrityError, match="fk_deal_attachments_uploaded_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": uploader})


async def test_the_foreign_keys_cascade_from_the_deal_and_restrict_the_user(
    session: AsyncSession,
) -> None:
    """FK는 Deal에서 CASCADE, 사용자에서 RESTRICT다."""
    # when: 외래 키 정보를 읽는다 (전제: head 스키마)
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}

    # then: Deal은 CASCADE, 사용자는 RESTRICT 두 개뿐이다
    assert fks == {
        ("fk_deal_attachments_deal_id_deals", "deals", "c"),
        ("fk_deal_attachments_uploaded_by_user_id_users", "users", "r"),
    }


async def test_the_planned_constraints_and_indexes_exist(session: AsyncSession) -> None:
    """계획한 제약과 인덱스가 있다."""
    # when: 제약과 인덱스 이름을 읽는다 (전제: head 스키마)
    constraints = await _names(session, CONSTRAINT_NAMES)
    indexes = await _names(session, INDEX_NAMES)

    # then: PK·유니크 두 개·크기 체크와 두 인덱스가 있다
    assert {
        "pk_deal_attachments",
        "uq_deal_attachments_deal_id_file_name",
        "uq_deal_attachments_storage_key",
        "ck_deal_attachments_size_range",
    } <= constraints
    assert {
        "ix_deal_attachments_uploaded_by_user_id",
        "ix_deal_attachments_deal_id_uploaded_at",
    } <= indexes


async def test_the_table_passes_the_schema_integrity_rules(session: AsyncSession) -> None:
    """테이블이 스키마 무결성 규칙을 통과한다."""
    # when: 스키마 무결성 규칙을 검사한다
    violations = await check_schema(session, only_tables={"deal_attachments"})

    # then: 위반이 없다
    assert violations == []
