"""경고 기준 유스케이스(P3 AC-05~07): 조회는 저장 기록이 없으면 기본값, 변경은 검증 뒤에만 저장한다.

admin 판정은 web 라우터 의존성이 하므로 유스케이스는 권한을 다시 보지 않는다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.alert.get_alert_settings import GetAlertSettings
from app.application.alert.update_alert_settings import UpdateAlertSettings
from app.domain.alert.thresholds import AlertThresholds
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.alert.settings import StoredAlertSettings
    from app.domain.auth.principal import Principal
    from app.domain.user.value_objects import UserId, UserRef
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

RANGE_MESSAGE = "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredAlertSettings | None:
    async with uow_factory() as uow:
        return await uow.alert_settings.get()


@pytest.fixture
async def admin(uow_factory: UnitOfWorkFactory) -> Principal:
    return (await seed_user(uow_factory, "root", Role.ADMIN)).to_principal()


@pytest.fixture
def get_settings(uow_factory: UnitOfWorkFactory) -> GetAlertSettings:
    return GetAlertSettings(uow_factory)


@pytest.fixture
def update_settings(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> UpdateAlertSettings:
    return UpdateAlertSettings(uow_factory, clock)


# ---- GetAlertSettings ----


async def test_get_without_saved_row_returns_default(get_settings: GetAlertSettings) -> None:
    view = await get_settings.execute()

    assert view.thresholds == AlertThresholds.default()
    assert view.thresholds.stale_days == 14
    assert view.updated_at is None
    assert view.updated_by is None


async def test_get_returns_the_saved_values_and_the_saver_reference(
    get_settings: GetAlertSettings, update_settings: UpdateAlertSettings, admin: Principal
) -> None:
    await update_settings.execute(actor=admin, stale_days=30)

    view = await get_settings.execute()

    assert view.thresholds.stale_days == 30
    assert view.updated_at == NOW
    assert view.updated_by is not None
    assert (view.updated_by.id, view.updated_by.resigned) == (admin.user_id, False)


async def test_get_shows_a_resigned_saver_as_resigned(
    get_settings: GetAlertSettings, uow_factory: UnitOfWorkFactory
) -> None:
    resigned = await seed_user(uow_factory, "gone", Role.ADMIN, resigned=True)
    async with uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=9), updated_by=resigned.id, now=NOW
        )
        await uow.commit()

    view = await get_settings.execute()

    assert view.updated_by is not None
    assert (view.updated_by.id, view.updated_by.resigned) == (resigned.id, True)


# ---- UpdateAlertSettings ----


async def test_update_saves_and_returns_actor_and_time(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    clock.advance(90)

    view = await update_settings.execute(actor=admin, stale_days=7)

    assert view.thresholds == AlertThresholds(stale_days=7)
    assert view.updated_at == NOW + timedelta(seconds=90)
    assert view.updated_by is not None
    assert view.updated_by.id == admin.user_id
    stored = await _stored(uow_factory)
    assert stored is not None
    assert (stored.thresholds.stale_days, stored.updated_by, stored.updated_at) == (
        7,
        admin.user_id,
        NOW + timedelta(seconds=90),
    )


@pytest.mark.parametrize("days", [1, 365])
async def test_update_accepts_the_bounds(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    days: int,
) -> None:
    await update_settings.execute(actor=admin, stale_days=days)

    stored = await _stored(uow_factory)
    assert stored is not None
    assert stored.thresholds.stale_days == days


@pytest.mark.parametrize("days", [0, 366, -5])
async def test_update_out_of_range_saves_nothing(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    days: int,
) -> None:
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=days)

    assert await _stored(uow_factory) is None


async def test_update_out_of_range_keeps_the_previous_value(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    await update_settings.execute(actor=admin, stale_days=20)
    before = await _stored(uow_factory)
    clock.advance(60)

    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=0)

    assert await _stored(uow_factory) == before


async def test_update_rejects_a_bool_as_the_value(
    update_settings: UpdateAlertSettings, uow_factory: UnitOfWorkFactory, admin: Principal
) -> None:
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=True)

    assert await _stored(uow_factory) is None


async def test_last_save_wins(
    update_settings: UpdateAlertSettings,
    get_settings: GetAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    await update_settings.execute(actor=admin, stale_days=7)
    other = (await seed_user(uow_factory, "boss2", Role.ADMIN)).to_principal()
    clock.advance(60)

    await update_settings.execute(actor=other, stale_days=21)

    view = await get_settings.execute()
    assert view.thresholds.stale_days == 21
    assert view.updated_at == NOW + timedelta(seconds=60)
    assert view.updated_by is not None
    assert view.updated_by.id == other.user_id


async def test_update_reads_the_saver_reference_before_commit(
    update_settings: UpdateAlertSettings,
    uow: FakeUnitOfWork,
    admin: Principal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """저장자 참조는 저장 트랜잭션 안(commit 전)에서 읽는다(R1 리뷰 Minor)."""
    original = uow.users.get_refs
    commits_before = uow.commits
    seen: list[int] = []

    async def get_refs(user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        seen.append(uow.commits - commits_before)
        return await original(user_ids)

    monkeypatch.setattr(uow.users, "get_refs", get_refs)

    view = await update_settings.execute(actor=admin, stale_days=12)

    assert seen == [0]
    assert view.updated_by is not None
    assert view.updated_by.id == admin.user_id
