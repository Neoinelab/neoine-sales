"""codes·bant_labels 테이블의 DB 제약(실제 PostgreSQL): 제약 이름과 위반 시 거절을 고정한다.

Repository가 도메인 오류로 바꾸는 유니크 위반은 계약 테스트가, 여기서는 SQL로 직접 넣어
앱을 우회하는 입력도 DB가 막는지 본다. 위반 INSERT는 SAVEPOINT 안에서 실행해 세션을 계속 쓴다.
"""

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infra.db.user_repository import SqlUserRepository
from tests.factories_auth import make_user
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CODE_COLUMNS = "id, kind, key, name, sort_order, outcome, probability_hint, created_at, updated_at"
LABEL_COLUMNS = (
    "id, category, name, is_default, default_order, created_by_user_id, created_at, updated_at"
)


def _code(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    values: dict[str, Any] = {
        "id": new_id(),
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
        "id": new_id(),
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
    """올바른 코드 행과 Label 행은 저장된다."""
    # when: 올바른 코드 행을 넣는다 (전제: 실제 PostgreSQL)
    await _insert_code(session, _code())
    # when: 올바른 Label 행을 넣는다 (오류 없이 저장되면 통과)
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
    """CHECK를 어기는 코드 행은 거부한다."""
    # when: 제약을 어기는 코드 행을 넣는다
    message = await _rejected(session, _insert_code(session, _code(**overrides)))

    # then: 오류 문구에 해당 제약 이름이 있다
    assert constraint in message


async def test_code_key_is_unique_per_kind(session: AsyncSession) -> None:
    """코드 키는 구분 안에서 유일하다."""
    # given: 같은 구분·키의 코드 행
    await _insert_code(session, _code(name="ZZ One"))

    # when: 이름만 다른 같은 키 행을 넣는다
    message = await _rejected(session, _insert_code(session, _code(name="ZZ Two")))

    # then: kind+key 유니크 제약 위반이다
    assert "uq_codes_kind_key" in message


async def test_code_name_is_unique_per_kind_ignoring_case(session: AsyncSession) -> None:
    """코드 이름은 구분 안에서 대소문자 무시로 유일하다."""
    # given: 이름이 있는 코드 행
    await _insert_code(session, _code(key="zz_one", name="ZZ Name"))

    # when: 대소문자만 다른 이름의 행을 넣는다
    message = await _rejected(session, _insert_code(session, _code(key="zz_two", name="zz name")))

    # then: 소문자 이름 유니크 제약 위반이다
    assert "uq_codes_kind_name_lower" in message


async def test_same_code_key_and_name_are_allowed_in_the_other_kind(session: AsyncSession) -> None:
    """같은 키·이름도 다른 구분에서는 허용한다."""
    # given: forecast 구분의 코드 행
    await _insert_code(session, _code(kind="forecast"))

    # when: 같은 키·이름을 status 구분에 넣는다 (오류 없이 저장되면 통과)
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
    """CHECK를 어기는 Label 행은 거부한다."""
    # when: 제약을 어기는 Label 행을 넣는다
    message = await _rejected(session, _insert_label(session, _label(**overrides)))

    # then: 오류 문구에 해당 제약 이름이 있다
    assert constraint in message


async def test_label_name_is_unique_per_category_ignoring_case(session: AsyncSession) -> None:
    """Label 이름은 구분 안에서 대소문자 무시로 유일하다."""
    # given: 이름이 있는 Label 행
    await _insert_label(session, _label(name="ZZ Name"))

    # when: 대소문자만 다른 이름의 행을 넣는다
    message = await _rejected(session, _insert_label(session, _label(name="zz name")))

    # then: 구분+소문자 이름 유니크 제약 위반이다
    assert "uq_bant_labels_category_name_lower" in message


async def test_same_label_name_is_allowed_in_another_category(session: AsyncSession) -> None:
    """같은 Label 이름도 다른 구분에서는 허용한다."""
    # given: need 구분의 Label 행
    await _insert_label(session, _label(category="need"))

    # when: 같은 이름을 budget 구분에 넣는다 (오류 없이 저장되면 통과)
    await _insert_label(session, _label(category="budget"))


async def test_label_creator_must_be_an_existing_user(session: AsyncSession) -> None:
    """Label 생성자는 존재하는 사용자여야 한다."""
    # when·then: 없는 사용자를 생성자로 넣으면 거부된다
    await _rejected(session, _insert_label(session, _label(created_by_user_id=new_id())))


async def test_user_who_created_a_label_cannot_be_deleted_directly(session: AsyncSession) -> None:
    """Label을 만든 사용자는 직접 삭제할 수 없다(RESTRICT라 퇴사 처리해야 한다)."""
    # given: 사용자
    creator = make_user("zz-label-creator")
    await SqlUserRepository(session).add(creator)
    # given: 그 사용자가 만든 Label
    await _insert_label(session, _label(created_by_user_id=creator.id))

    # when·then: 사용자를 삭제하면 무결성 오류다
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("delete from users where id = :id"), {"id": creator.id})
