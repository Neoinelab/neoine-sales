"""head 스키마의 partner_meetings(파트너 Activity, 마이그레이션 순수 expand).

제약은 원시 INSERT로 직접 어겨 보고 제약·인덱스 이름으로 거절되는지 확인한다(도메인 검증을 거치지
않는다). 임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
실패하는 INSERT는 테스트마다 하나뿐이다.
대리 키 규칙(BIGINT IDENTITY)은 `test_bigint_ids_schema.py`가 이 테이블도 점검한다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_user
from tests.support.ids import MISSING_ID
from tests.support.partner_meeting_rows import insert_meeting
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable, column_default"
    " from information_schema.columns where table_schema = 'public'"
    " and table_name = 'partner_meetings'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, a.attname"
    " from pg_constraint c"
    " join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = 'partner_meetings'::regclass and c.contype = 'f'"
)
INDEXES = (
    "select indexname, indexdef from pg_indexes"
    " where schemaname = 'public' and tablename = 'partner_meetings'"
)


async def _deal(session: AsyncSession, author_login: str = "meeting-author") -> tuple[str, int]:
    author = await insert_user(session, author_login)
    customer = await insert_contact(session)
    code = await insert_deal(session, customer, owner_user_id=author)
    return code, author


async def test_partner_meetings_columns_types_and_nullability(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMNS))).all()
    columns = {
        r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows
    }

    assert columns == {
        "id": ("bigint", None, "NO"),
        "deal_id": ("bigint", None, "NO"),
        "partner_company": ("character varying", 200, "NO"),
        "meeting_date": ("date", None, "NO"),
        "content": ("text", None, "NO"),
        "created_by_user_id": ("bigint", None, "NO"),
        "created_at": ("timestamp with time zone", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_author(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_partner_meetings_deal_id_deals", "deals", "c", "deal_id"),
        ("fk_partner_meetings_created_by_user_id_users", "users", "r", "created_by_user_id"),
    }


async def test_the_planned_indexes_exist_and_none_is_unique(session: AsyncSession) -> None:
    definitions = {r.indexname: r.indexdef for r in (await session.execute(text(INDEXES))).all()}

    assert set(definitions) == {
        "pk_partner_meetings",
        "ix_partner_meetings_meeting_date_id",
        "ix_partner_meetings_deal_id",
        "ix_partner_meetings_created_by_user_id",
    }  # 쓰이지 않는 partner_company lower 인덱스는 없다
    assert "(meeting_date, id)" in definitions["ix_partner_meetings_meeting_date_id"]
    unique = [name for name, d in definitions.items() if "UNIQUE" in d]
    assert unique == ["pk_partner_meetings"]


async def test_the_schema_has_no_integrity_violations(session: AsyncSession) -> None:
    exists = (await session.execute(text("select to_regclass('public.partner_meetings')"))).scalar()

    assert exists is not None  # 점검 대상 테이블이 있어야 의미가 있다
    assert await check_schema(session) == []


async def test_a_valid_row_is_accepted_and_duplicates_are_allowed(session: AsyncSession) -> None:
    code, author = await _deal(session)

    await insert_meeting(session, code, author)
    await insert_meeting(session, code, author)  # 같은 Deal·날짜·내용 중복 허용

    count = (await session.execute(text("select count(*) from partner_meetings"))).scalar_one()
    assert count == 2


@pytest.mark.parametrize("day", ["1900-01-01", "2026-10-01", "2999-12-31"])
async def test_future_and_far_dates_are_accepted(session: AsyncSession, day: str) -> None:
    code, author = await _deal(session)

    await insert_meeting(session, code, author, meeting_date=day)


async def test_content_may_be_very_long_and_multiline(session: AsyncSession) -> None:
    code, author = await _deal(session)

    await insert_meeting(session, code, author, content="줄\n" * 200_000 + "끝")


@pytest.mark.parametrize("content", ["", "   ", "\n\t \n"])
async def test_blank_content_is_rejected_by_the_check(session: AsyncSession, content: str) -> None:
    code, author = await _deal(session)

    with pytest.raises(IntegrityError, match="ck_partner_meetings_content_not_blank"):
        await insert_meeting(session, code, author, content=content)


@pytest.mark.parametrize("company", ["", "한빛 파트너스", " 한빛", "한빛\t"])
async def test_empty_or_spaced_company_is_rejected_by_the_check(
    session: AsyncSession, company: str
) -> None:
    code, author = await _deal(session)

    with pytest.raises(IntegrityError, match="ck_partner_meetings_company_valid"):
        await insert_meeting(session, code, author, partner_company=company)


async def test_company_longer_than_200_characters_is_rejected(session: AsyncSession) -> None:
    code, author = await _deal(session)

    with pytest.raises(DBAPIError, match="too long"):
        await insert_meeting(session, code, author, partner_company="가" * 201)


async def test_a_missing_deal_is_rejected_by_the_foreign_key(session: AsyncSession) -> None:
    _code, author = await _deal(session)

    with pytest.raises(IntegrityError, match="fk_partner_meetings_deal_id_deals"):
        await insert_meeting(session, "20260101-ZZZZ", author, deal_id=MISSING_ID)


async def test_a_missing_author_is_rejected_by_the_foreign_key(session: AsyncSession) -> None:
    code, _author = await _deal(session)

    with pytest.raises(IntegrityError, match="fk_partner_meetings_created_by_user_id_users"):
        await insert_meeting(session, code, MISSING_ID)


async def test_deleting_the_deal_removes_its_meetings_only(session: AsyncSession) -> None:
    code, author = await _deal(session)
    other_customer = await insert_contact(session, name="다른담당")
    other = await insert_deal(session, other_customer, owner_user_id=author, code="20261016-A002")
    await insert_meeting(session, code, author, content="삭제될 기록")
    await insert_meeting(session, other, author, content="남을 기록")

    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    contents = (await session.execute(text("select content from partner_meetings"))).scalars().all()
    assert contents == ["남을 기록"]


async def test_a_user_who_wrote_a_meeting_cannot_be_physically_deleted(
    session: AsyncSession,
) -> None:
    code, _author = await _deal(session)
    writer = await insert_user(session, "meeting-writer")
    await insert_meeting(session, code, writer)

    with pytest.raises(IntegrityError, match="fk_partner_meetings_created_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": writer})
