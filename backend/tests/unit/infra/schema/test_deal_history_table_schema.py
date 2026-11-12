"""head 스키마의 deal_history: 구분 CHECK, 길이, 사용자 FK, 인덱스.

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
    """deal_history 테이블에 정해진 열과 인덱스가 있다."""
    # when: 테이블의 열 이름과 인덱스 이름을 조회한다 (전제: head 스키마의 DB 세션)
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

    # then: 열 집합이 정확히 맞고 두 인덱스가 있다
    assert columns == COLUMNS
    assert {
        "ix_deal_history_deal_id_changed_at",
        "ix_deal_history_changed_by_user_id",
    } <= indexes


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_author(
    session: AsyncSession,
) -> None:
    """외래 키는 Deal에서 CASCADE, 작성자 사용자에서 RESTRICT다."""
    # when: 테이블의 외래 키를 조회한다 (전제: head 스키마의 DB 세션)
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    # then: deals는 cascade, users는 restrict다
    assert {(r[0], r[1].strip()) for r in rows} == {("deals", "c"), ("users", "r")}


async def test_the_id_is_generated_and_increasing(session: AsyncSession) -> None:
    """id는 자동 생성되고 증가한다."""
    # given: Deal과 작성자
    code, user = await _deal_and_user(session)
    # when: 이력을 3건 넣는다
    for _ in range(3):
        await insert_history(session, code, user)

    # then: id 3개가 서로 다르고 증가 순이다
    ids = [
        r[0] for r in (await session.execute(text("select id from deal_history order by id"))).all()
    ]

    assert len(ids) == 3
    assert ids == sorted(set(ids))


@pytest.mark.parametrize("category", CATEGORIES)
async def test_each_frontend_category_is_accepted(session: AsyncSession, category: str) -> None:
    """프런트엔드가 쓰는 구분 값은 모두 허용한다."""
    # given: Deal과 작성자
    code, user = await _deal_and_user(session)

    # when·then: 해당 구분으로 이력을 넣으면 제약에 걸리지 않는다
    await insert_history(session, code, user, category=category)


async def test_an_unknown_category_is_rejected(session: AsyncSession) -> None:
    """알 수 없는 구분 값은 CHECK 제약이 거부한다."""
    # given: Deal과 작성자
    code, user = await _deal_and_user(session)

    # when·then: 구분 'unknown'으로 넣으면 CHECK 위반이 난다
    with pytest.raises(IntegrityError, match="ck_deal_history"):
        await insert_history(session, code, user, category="unknown")


async def test_the_target_is_limited_to_300_characters(session: AsyncSession) -> None:
    """대상 칸은 300자까지만 허용한다."""
    # given: Deal과 작성자, 300자 대상 이력 한 건
    code, user = await _deal_and_user(session)
    params = {"code": code, "user": user, "before": "", "after": ""}
    await session.execute(text(INSERT_WITH_TEXTS), {**params, "target": "가" * 300})

    # when·then: 301자 대상으로 넣으면 길이 초과 오류가 난다
    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(text(INSERT_WITH_TEXTS), {**params, "target": "가" * 301})


async def test_before_and_after_texts_may_be_long(session: AsyncSession) -> None:
    """변경 전·후 텍스트는 길어도 허용한다."""
    # given: Deal과 작성자
    code, user = await _deal_and_user(session)

    # when·then: 2000자 변경 전 텍스트로 넣어도 오류가 나지 않는다
    await session.execute(
        text(INSERT_WITH_TEXTS),
        {"code": code, "user": user, "target": "구매절차", "before": "가" * 2000, "after": ""},
    )


async def test_a_missing_author_is_rejected(session: AsyncSession) -> None:
    """없는 작성자 사용자는 FK 제약이 거부한다."""
    # given: Deal
    code, _ = await _deal_and_user(session)

    # when·then: 없는 사용자 id로 넣으면 FK 위반이 난다
    with pytest.raises(IntegrityError, match="fk_deal_history_changed_by_user_id_users"):
        await insert_history(session, code, MISSING_ID)


async def test_a_user_with_history_cannot_be_deleted(session: AsyncSession) -> None:
    """이력을 남긴 사용자는 삭제할 수 없다."""
    # given: 이력을 남긴 작성자
    code = await insert_deal(session, await insert_contact(session))
    author = await insert_user(session, "author")
    await insert_history(session, code, author)

    # when·then: 그 사용자를 삭제하면 FK 위반이 난다
    with pytest.raises(IntegrityError, match="fk_deal_history_changed_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": author})


async def test_deleting_the_deal_deletes_its_history(session: AsyncSession) -> None:
    """Deal을 삭제하면 그 이력도 함께 삭제된다."""
    # given: 이력이 있는 Deal
    code, user = await _deal_and_user(session)
    await insert_history(session, code, user)

    # when: Deal을 삭제한다
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    # then: 이력이 하나도 남지 않는다
    count = (await session.execute(text("select count(*) from deal_history"))).scalar_one()
    assert count == 0
