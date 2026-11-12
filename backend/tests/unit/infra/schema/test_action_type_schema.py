"""head 스키마의 action_types 테이블: 이름 유니크 인덱스, 기본 순서 CHECK, 생성자 FK.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 위반 INSERT는 SAVEPOINT 안에서 실행한다.
"""

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infra.db.user_repository import SqlUserRepository
from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
from tests.factories_auth import make_user
from tests.support.ids import new_id
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = 'action_types'"
)
INSERT = (
    "insert into action_types (id, name, is_default, default_order, created_by_user_id,"
    " created_at, updated_at) values (:id, :name, :is_default, :default_order,"
    " :created_by_user_id, now(), now())"
)
SEED = "select name, default_order, is_default, created_by_user_id from action_types"


def _row(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    values: dict[str, Any] = {
        "id": new_id(),
        "name": "ZZ 유형",
        "is_default": False,
        "default_order": None,
        "created_by_user_id": None,
    }
    return {**values, **overrides}


async def _insert(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(text(INSERT), values)


async def _rejected(session: AsyncSession, values: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as raised:
        async with session.begin_nested():
            await _insert(session, values)
    return str(raised.value)


async def test_the_table_has_the_expected_columns(session: AsyncSession) -> None:
    """테이블은 기대한 컬럼·길이·널 허용을 가진다."""
    # when: 컬럼 정보를 읽는다
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    # then: 컬럼 집합, 이름 길이 50, 널 허용 여부가 기대와 같다
    assert set(columns) == {
        "id",
        "name",
        "is_default",
        "default_order",
        "created_by_user_id",
        "created_at",
        "updated_at",
    }
    assert (columns["name"].data_type, columns["name"].character_maximum_length) == (
        "character varying",
        50,
    )
    assert columns["name"].is_nullable == "NO"
    assert columns["is_default"].is_nullable == "NO"
    assert columns["default_order"].is_nullable == "YES"
    assert columns["created_by_user_id"].is_nullable == "YES"


async def test_a_valid_custom_row_is_accepted(session: AsyncSession) -> None:
    """올바른 직접 만든 유형 행은 저장된다."""
    # when·then: 제약을 지킨 행을 넣으면 오류가 없다
    await _insert(session, _row())


async def test_name_is_unique_ignoring_case(session: AsyncSession) -> None:
    """이름은 대소문자를 무시하고 유일하다."""
    # given: "ZZ Name" 행
    await _insert(session, _row(name="ZZ Name"))

    # when: 대소문자만 다른 이름을 넣는다
    message = await _rejected(session, _row(name="zz name"))

    # then: 이름 유니크 인덱스로 거부된다
    assert "uq_action_types_name_lower" in message


async def test_a_name_of_a_seeded_default_type_is_taken_ignoring_case(
    session: AsyncSession,
) -> None:
    """시드 기본 유형 이름도 대소문자 무시 유니크에 걸린다."""
    # when: 시드와 같은 이름 "미팅"을 넣는다
    message = await _rejected(session, _row(name="미팅"))

    # then: 이름 유니크 인덱스로 거부된다
    assert "uq_action_types_name_lower" in message


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_default": True, "default_order": None},
        {"is_default": False, "default_order": 1},
    ],
    ids=["default-without-order", "custom-with-order"],
)
async def test_default_order_must_match_is_default(
    session: AsyncSession, overrides: dict[str, Any]
) -> None:
    """기본 여부와 기본 순서는 서로 맞아야 한다."""
    # when: 기본인데 순서가 없거나 직접 만든 것인데 순서가 있는 행을 넣는다
    message = await _rejected(session, _row(**overrides))

    # then: 기본 순서 CHECK로 거부된다
    assert "ck_action_types_default_order" in message


async def test_creator_must_be_an_existing_user(session: AsyncSession) -> None:
    """생성자는 존재하는 사용자여야 한다."""
    # when: 없는 사용자를 생성자로 넣는다
    message = await _rejected(session, _row(created_by_user_id=new_id()))

    # then: 생성자 FK로 거부된다
    assert "fk_action_types_created_by_user_id_users" in message


async def test_user_who_created_a_type_cannot_be_deleted_directly(session: AsyncSession) -> None:
    """RESTRICT: 삭제 대신 퇴사 처리하게 하는 근거다."""
    # given: 유형을 만든 사용자
    creator = make_user("zz-type-creator")
    await SqlUserRepository(session).add(creator)
    await _insert(session, _row(created_by_user_id=creator.id))

    # when·then: 그 사용자를 직접 삭제하면 FK(RESTRICT)로 거부된다
    with pytest.raises(IntegrityError, match="fk_action_types_created_by_user_id_users"):
        async with session.begin_nested():
            await session.execute(text("delete from users where id = :id"), {"id": creator.id})


async def test_the_migration_seeds_the_eight_default_types_in_order(session: AsyncSession) -> None:
    """마이그레이션은 기본 유형 8개를 순서대로 시드한다."""
    # when: 기본 유형을 기본 순서로 읽는다
    rows = (
        await session.execute(
            text(SEED + " where is_default order by default_order"),
        )
    ).all()

    # then: 이름·순서가 정해진 8개이고 생성자는 없다
    assert [(r.name, r.default_order) for r in rows] == [
        (name, order) for order, name in enumerate(DEFAULT_ACTION_TYPE_NAMES, start=1)
    ]
    assert all(r.created_by_user_id is None for r in rows)


async def test_the_table_has_no_integrity_violations(session: AsyncSession) -> None:
    """생성자 FK의 선두 컬럼 인덱스(ix_action_types_created_by_user_id) 등 규칙 점검."""
    # when: 테이블 존재를 확인하고 스키마 규칙을 점검한다
    exists = await session.execute(text("select to_regclass('public.action_types')"))
    assert exists.scalar_one() is not None  # 테이블이 없으면 점검할 것이 없어 통과하므로 먼저 확인
    # then: 위반이 없다
    assert await check_schema(session, only_tables={"action_types"}) == []


async def test_the_creator_index_exists(session: AsyncSession) -> None:
    """이름 유니크 인덱스와 생성자 인덱스가 있다."""
    # when: 테이블의 인덱스 이름을 읽는다
    indexes = {
        r[0]
        for r in (
            await session.execute(
                text("select indexname from pg_indexes where tablename = 'action_types'")
            )
        ).all()
    }

    # then: 두 인덱스가 모두 있다
    assert {"uq_action_types_name_lower", "ix_action_types_created_by_user_id"} <= indexes
