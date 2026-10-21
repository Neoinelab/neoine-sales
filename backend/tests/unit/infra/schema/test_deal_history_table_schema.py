"""head 스키마의 deal_history(AC-06·25·30·28, 계획 6.1): 구분 CHECK, 길이, 사용자 FK, 인덱스.

(파일 이름: `test_deal_history_schema.py`는 활동 이력 리비전을 고정해 검증하는 과거 테스트다.)
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_history, insert_user
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = {
    "id",
    "deal_id",
    "changed_at",
    "changed_by_user_id",
    "category",
    "target",
    "before_text",
    "after_text",
}
CATEGORIES = [
    "created",
    "status",
    "forecast",
    "amount",
    "expectedClose",
    "owner",
    "partner",
    "contact",
    "bant",
    "action",
    "attachment",
    "other",
]
FOREIGN_KEYS = (
    "select confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_history'::regclass and contype = 'f'"
)
INSERT_WITH_TEXTS = (
    "insert into deal_history (deal_id, changed_at, changed_by_user_id, category, target,"
    " before_text, after_text) values ((select id from deals where deal_code = :code), now(),"
    " :user, 'other', :target, :before, :after)"
)


async def _deal_and_user(session: AsyncSession) -> tuple[str, int]:
    user = await insert_user(session, "author")
    code = await insert_deal(session, await insert_contact(session), owner_user_id=user)
    return code, user


async def test_the_columns_and_indexes_exist(session: AsyncSession) -> None:
    columns = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "select column_name from information_schema.columns"
                    " where table_name = 'deal_history'"
                )
            )
        ).all()
    }
    indexes = {
        r[0]
        for r in (
            await session.execute(
                text("select indexname from pg_indexes where tablename = 'deal_history'")
            )
        ).all()
    }

    assert columns == COLUMNS
    assert {
        "ix_deal_history_deal_id_changed_at",
        "ix_deal_history_changed_by_user_id",
    } <= indexes


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_author(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    assert {(r[0], r[1].strip()) for r in rows} == {("deals", "c"), ("users", "r")}


async def test_the_id_is_generated_and_increasing(session: AsyncSession) -> None:
    code, user = await _deal_and_user(session)
    for _ in range(3):
        await insert_history(session, code, user)

    ids = [
        r[0] for r in (await session.execute(text("select id from deal_history order by id"))).all()
    ]

    assert len(ids) == 3
    assert ids == sorted(set(ids))


@pytest.mark.parametrize("category", CATEGORIES)
async def test_each_frontend_category_is_accepted(session: AsyncSession, category: str) -> None:
    code, user = await _deal_and_user(session)

    await insert_history(session, code, user, category=category)


async def test_an_unknown_category_is_rejected(session: AsyncSession) -> None:
    code, user = await _deal_and_user(session)

    with pytest.raises(IntegrityError, match="ck_deal_history"):
        await insert_history(session, code, user, category="unknown")


async def test_the_target_is_limited_to_300_characters(session: AsyncSession) -> None:
    code, user = await _deal_and_user(session)
    params = {"code": code, "user": user, "before": "", "after": ""}
    await session.execute(text(INSERT_WITH_TEXTS), {**params, "target": "가" * 300})

    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(text(INSERT_WITH_TEXTS), {**params, "target": "가" * 301})


async def test_before_and_after_texts_may_be_long(session: AsyncSession) -> None:
    code, user = await _deal_and_user(session)

    await session.execute(
        text(INSERT_WITH_TEXTS),
        {"code": code, "user": user, "target": "구매절차", "before": "가" * 2000, "after": ""},
    )


async def test_a_missing_author_is_rejected(session: AsyncSession) -> None:
    code, _ = await _deal_and_user(session)

    with pytest.raises(IntegrityError, match="fk_deal_history_changed_by_user_id_users"):
        await insert_history(session, code, MISSING_ID)


async def test_a_user_with_history_cannot_be_deleted(session: AsyncSession) -> None:
    code = await insert_deal(session, await insert_contact(session))
    author = await insert_user(session, "author")
    await insert_history(session, code, author)

    with pytest.raises(IntegrityError, match="fk_deal_history_changed_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": author})


async def test_deleting_the_deal_deletes_its_history(session: AsyncSession) -> None:
    code, user = await _deal_and_user(session)
    await insert_history(session, code, user)

    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    count = (await session.execute(text("select count(*) from deal_history"))).scalar_one()
    assert count == 0
