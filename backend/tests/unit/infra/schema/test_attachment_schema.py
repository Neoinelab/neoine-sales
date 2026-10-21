"""head 스키마의 deal_attachments(P2b AC-17, M-P2b): 컬럼, 체크, 유니크, FK, 인덱스.

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
    columns = await _columns(session)

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
    columns = await _columns(session)

    assert {name for name, info in columns.items() if info[2] == "NO"} == COLUMNS


async def test_description_defaults_to_an_empty_string(session: AsyncSession) -> None:
    deal, user = await _deal(session)

    await session.execute(
        text(
            "insert into deal_attachments (id, deal_id, file_name, mime, size_bytes,"
            " storage_key, uploaded_by_user_id, uploaded_at, created_at, updated_at) values"
            " (:id, (select id from deals where deal_code = :deal), 'a.pdf', 'application/pdf',"
            " 1, :key, :user, now(), now(), now())"
        ),
        {"id": new_id(), "deal": deal, "key": uuid4().hex, "user": user},
    )

    assert (await session.execute(text("select description from deal_attachments"))).scalar() == ""


@pytest.mark.parametrize("size", [0, 1, MAX_BYTES])
async def test_a_size_inside_the_range_is_accepted(session: AsyncSession, size: int) -> None:
    deal, user = await _deal(session)

    await insert_attachment(session, deal, user, size_bytes=size)

    assert (await session.execute(text("select size_bytes from deal_attachments"))).scalar() == size


@pytest.mark.parametrize("size", [-1, MAX_BYTES + 1])
async def test_a_size_outside_the_range_is_rejected(session: AsyncSession, size: int) -> None:
    deal, user = await _deal(session)

    with pytest.raises(IntegrityError, match="ck_deal_attachments_size_range"):
        await insert_attachment(session, deal, user, size_bytes=size)


async def test_a_description_of_100_characters_is_accepted(session: AsyncSession) -> None:
    deal, user = await _deal(session)

    await insert_attachment(session, deal, user, description="가" * 100)

    length = await session.execute(text("select length(description) from deal_attachments"))
    assert length.scalar() == 100


async def test_a_description_over_100_characters_is_rejected(session: AsyncSession) -> None:
    deal, user = await _deal(session)

    with pytest.raises(DBAPIError):
        await insert_attachment(session, deal, user, description="가" * 101)


async def test_a_file_name_of_255_characters_is_accepted(session: AsyncSession) -> None:
    deal, user = await _deal(session)

    await insert_attachment(session, deal, user, file_name="가" * 255)

    length = await session.execute(text("select length(file_name) from deal_attachments"))
    assert length.scalar() == 255


async def test_a_file_name_over_255_characters_is_rejected(session: AsyncSession) -> None:
    deal, user = await _deal(session)

    with pytest.raises(DBAPIError):
        await insert_attachment(session, deal, user, file_name="가" * 256)


async def test_the_same_file_name_twice_in_one_deal_is_rejected(session: AsyncSession) -> None:
    deal, user = await _deal(session)
    await insert_attachment(session, deal, user, file_name="same.pdf")

    with pytest.raises(IntegrityError, match="uq_deal_attachments_deal_id_file_name"):
        await insert_attachment(session, deal, user, file_name="same.pdf")


async def test_the_same_file_name_in_different_deals_is_accepted(session: AsyncSession) -> None:
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")

    await insert_attachment(session, deal, user, file_name="same.pdf")
    await insert_attachment(session, other_deal, user, file_name="same.pdf")

    assert (await session.execute(text(COUNT))).scalar() == 2


async def test_file_names_that_differ_only_in_case_are_different_names(
    session: AsyncSession,
) -> None:
    deal, user = await _deal(session)

    await insert_attachment(session, deal, user, file_name="Report.pdf")
    await insert_attachment(session, deal, user, file_name="report.pdf")

    assert (await session.execute(text(COUNT))).scalar() == 2


async def test_the_same_storage_key_twice_is_rejected_even_across_deals(
    session: AsyncSession,
) -> None:
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")
    key = uuid4().hex
    await insert_attachment(session, deal, user, storage_key=key)

    with pytest.raises(IntegrityError, match="uq_deal_attachments_storage_key"):
        await insert_attachment(session, other_deal, user, storage_key=key, file_name="b.pdf")


async def test_an_attachment_of_a_missing_deal_is_rejected(session: AsyncSession) -> None:
    user = await _user(session)

    with pytest.raises(IntegrityError, match="fk_deal_attachments_deal_id_deals"):
        await insert_attachment(session, "20260101-ZZZZ", user, deal_id=MISSING_ID)


async def test_an_attachment_of_a_missing_uploader_is_rejected(session: AsyncSession) -> None:
    deal, _ = await _deal(session)

    with pytest.raises(IntegrityError, match="fk_deal_attachments_uploaded_by_user_id_users"):
        await insert_attachment(session, deal, new_id())


async def test_deleting_the_deal_deletes_its_attachments(session: AsyncSession) -> None:
    deal, user = await _deal(session)
    await insert_attachment(session, deal, user, file_name="a.pdf")
    await insert_attachment(session, deal, user, file_name="b.pdf")

    await session.execute(text("delete from deals where deal_code = :code"), {"code": deal})

    assert (await session.execute(text(COUNT))).scalar() == 0


async def test_deleting_the_deal_keeps_the_attachments_of_other_deals(
    session: AsyncSession,
) -> None:
    deal, user = await _deal(session, "20261016-A001")
    other_deal, _ = await _deal(session, "20261016-B002")
    await insert_attachment(session, deal, user)
    await insert_attachment(session, other_deal, user)

    await session.execute(text("delete from deals where deal_code = :code"), {"code": deal})

    rows = await session.execute(
        text("select d.deal_code from deal_attachments a join deals d on d.id = a.deal_id")
    )
    assert rows.scalars().all() == [other_deal]


async def test_a_user_who_uploaded_an_attachment_cannot_be_deleted(session: AsyncSession) -> None:
    deal, _ = await _deal(session)
    uploader = await _user(session)
    await insert_attachment(session, deal, uploader)

    with pytest.raises(IntegrityError, match="fk_deal_attachments_uploaded_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": uploader})


async def test_the_foreign_keys_cascade_from_the_deal_and_restrict_the_user(
    session: AsyncSession,
) -> None:
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}

    assert fks == {
        ("fk_deal_attachments_deal_id_deals", "deals", "c"),
        ("fk_deal_attachments_uploaded_by_user_id_users", "users", "r"),
    }


async def test_the_planned_constraints_and_indexes_exist(session: AsyncSession) -> None:
    constraints = await _names(session, CONSTRAINT_NAMES)
    indexes = await _names(session, INDEX_NAMES)

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
    assert await check_schema(session, only_tables={"deal_attachments"}) == []
