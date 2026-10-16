"""codes·bant_labels 테이블의 DB 제약(실제 PostgreSQL): 제약 이름과 위반 시 거절을 고정한다.

Repository가 도메인 오류로 바꾸는 유니크 위반은 계약 테스트가, 여기서는 SQL로 직접 넣어
앱을 우회하는 입력도 DB가 막는지 본다. 위반 INSERT는 SAVEPOINT 안에서 실행해 세션을 계속 쓴다.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infra.db.user_repository import SqlUserRepository
from tests.factories_auth import make_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CODE_COLUMNS = "id, kind, key, name, sort_order, outcome, probability_hint, created_at, updated_at"
LABEL_COLUMNS = (
    "id, category, name, is_default, default_order, created_by_user_id, created_at, updated_at"
)


def _code(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    values: dict[str, Any] = {
        "id": uuid4(),
        "kind": "forecast",
        "key": "zz_ok",
        "name": "ZZ OK",
        "sort_order": 50,
        "outcome": "open",
        "probability_hint": "1-2",
    }
    return {**values, **overrides}


def _label(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    values: dict[str, Any] = {
        "id": uuid4(),
        "category": "need",
        "name": "ZZ OK",
        "is_default": False,
        "default_order": None,
        "created_by_user_id": None,
    }
    return {**values, **overrides}


async def _insert_code(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(
        text(
            f"insert into codes ({CODE_COLUMNS}) values "  # noqa: S608 - 상수 열 이름
            "(:id, :kind, :key, :name, :sort_order, :outcome, :probability_hint, now(), now())"
        ),
        values,
    )


async def _insert_label(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(
        text(
            f"insert into bant_labels ({LABEL_COLUMNS}) values "  # noqa: S608 - 상수 열 이름
            "(:id, :category, :name, :is_default, :default_order, :created_by_user_id, "
            "now(), now())"
        ),
        values,
    )


async def _rejected(session: AsyncSession, insert: Any) -> str:  # noqa: ANN401
    """INSERT가 IntegrityError로 거절되는지 확인하고 오류 문구를 돌려준다."""
    with pytest.raises(IntegrityError) as raised:
        async with session.begin_nested():
            await insert
    return str(raised.value)


async def test_valid_code_and_label_rows_are_accepted(session: AsyncSession) -> None:
    await _insert_code(session, _code())
    await _insert_label(session, _label())


INVALID_CODES = [
    ("ck_codes_kind_valid", {"kind": "other"}),
    ("ck_codes_key_format", {"key": "Bad Key"}),
    ("ck_codes_key_format", {"key": "1start"}),
    ("ck_codes_order_positive", {"sort_order": 0}),
    ("ck_codes_outcome_valid", {"outcome": "maybe"}),
    (
        "ck_codes_status_outcome_open",
        {"kind": "status", "outcome": "won", "probability_hint": None},
    ),
    ("ck_codes_hint_forecast_only", {"kind": "status", "probability_hint": "1-2"}),
]


@pytest.mark.parametrize(("constraint", "overrides"), INVALID_CODES)
async def test_code_row_violating_a_check_is_rejected(
    session: AsyncSession, constraint: str, overrides: dict[str, Any]
) -> None:
    message = await _rejected(session, _insert_code(session, _code(**overrides)))

    assert constraint in message


async def test_code_key_is_unique_per_kind(session: AsyncSession) -> None:
    await _insert_code(session, _code(name="ZZ One"))

    message = await _rejected(session, _insert_code(session, _code(name="ZZ Two")))

    assert "uq_codes_kind_key" in message


async def test_code_name_is_unique_per_kind_ignoring_case(session: AsyncSession) -> None:
    await _insert_code(session, _code(key="zz_one", name="ZZ Name"))

    message = await _rejected(session, _insert_code(session, _code(key="zz_two", name="zz name")))

    assert "uq_codes_kind_name_lower" in message


async def test_same_code_key_and_name_are_allowed_in_the_other_kind(session: AsyncSession) -> None:
    await _insert_code(session, _code(kind="forecast"))

    await _insert_code(session, _code(kind="status", probability_hint=None))


INVALID_LABELS = [
    ("ck_bant_labels_category_valid", {"category": "money"}),
    ("ck_bant_labels_default_order", {"is_default": True, "default_order": None}),
    ("ck_bant_labels_default_order", {"is_default": False, "default_order": 1}),
]


@pytest.mark.parametrize(("constraint", "overrides"), INVALID_LABELS)
async def test_label_row_violating_a_check_is_rejected(
    session: AsyncSession, constraint: str, overrides: dict[str, Any]
) -> None:
    message = await _rejected(session, _insert_label(session, _label(**overrides)))

    assert constraint in message


async def test_label_name_is_unique_per_category_ignoring_case(session: AsyncSession) -> None:
    await _insert_label(session, _label(name="ZZ Name"))

    message = await _rejected(session, _insert_label(session, _label(name="zz name")))

    assert "uq_bant_labels_category_name_lower" in message


async def test_same_label_name_is_allowed_in_another_category(session: AsyncSession) -> None:
    await _insert_label(session, _label(category="need"))

    await _insert_label(session, _label(category="budget"))


async def test_label_creator_must_be_an_existing_user(session: AsyncSession) -> None:
    await _rejected(session, _insert_label(session, _label(created_by_user_id=uuid4())))


async def test_user_who_created_a_label_cannot_be_deleted_directly(session: AsyncSession) -> None:
    """RESTRICT: 삭제 대신 퇴사 처리하게 하는 근거다(AC-15)."""
    creator = make_user("zz-label-creator")
    await SqlUserRepository(session).add(creator)
    await _insert_label(session, _label(created_by_user_id=creator.id))

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("delete from users where id = :id"), {"id": creator.id})
