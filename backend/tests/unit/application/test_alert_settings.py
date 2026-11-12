"""경고 기준 유스케이스: 조회는 저장 기록이 없으면 기본값, 변경은 검증 뒤에만 저장한다.

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
    """저장한 적이 없으면 경고 기준은 14일이고 저장 기록이 비어 있다.

    테스트 코드: RK-043
    """
    # when: 경고 기준을 조회한다
    view = await get_settings.execute()

    # then: 14일이고 저장 시각·저장자가 없다
    assert view.thresholds == AlertThresholds.default()
    assert view.thresholds.stale_days == 14
    assert view.updated_at is None
    assert view.updated_by is None


async def test_get_returns_the_saved_values_and_the_saver_reference(
    get_settings: GetAlertSettings, update_settings: UpdateAlertSettings, admin: Principal
) -> None:
    """저장한 값·시각·저장자를 다시 읽어도 같다.

    테스트 코드: RK-044
    """
    # given: admin이 30일로 저장했다
    await update_settings.execute(actor=admin, stale_days=30)

    # when: 경고 기준을 다시 조회한다
    view = await get_settings.execute()

    # then: 30일, 저장 시각, 저장자(퇴사 아님)가 나온다
    assert view.thresholds.stale_days == 30
    assert view.updated_at == NOW
    assert view.updated_by is not None
    assert (view.updated_by.id, view.updated_by.resigned) == (admin.user_id, False)


async def test_get_shows_a_resigned_saver_as_resigned(
    get_settings: GetAlertSettings, uow_factory: UnitOfWorkFactory
) -> None:
    """저장자가 퇴사했으면 퇴사로 표시된다.

    테스트 코드: RK-050
    """
    # given: 퇴사 처리된 admin이 9일로 저장했다
    resigned = await seed_user(uow_factory, "gone", Role.ADMIN, resigned=True)
    async with uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=9), updated_by=resigned.id, now=NOW
        )
        await uow.commit()

    # when: 경고 기준을 조회한다
    view = await get_settings.execute()

    # then: 저장자 id가 그 admin이고 resigned가 true다
    assert view.updated_by is not None
    assert (view.updated_by.id, view.updated_by.resigned) == (resigned.id, True)


# ---- UpdateAlertSettings ----


async def test_update_saves_and_returns_actor_and_time(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    """admin이 저장하면 값·저장자·서버 시각이 결과에 나오고 저장소에도 남는다.

    테스트 코드: RK-044
    """
    # given: 서버 시계가 90초 흘렀다
    clock.advance(90)

    # when: admin이 7일로 저장한다
    view = await update_settings.execute(actor=admin, stale_days=7)

    # then: 결과와 저장소에 7일, admin, 서버 시각이 있다
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
    """경계값 1일과 365일은 저장된다.

    테스트 코드: RK-045
    """
    # when: 경계값을 저장한다
    await update_settings.execute(actor=admin, stale_days=days)

    # then: 저장소에 그 값이 있다
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
    """범위 밖 정수는 고정 문구로 거절되고 아무것도 저장되지 않는다.

    테스트 코드: RK-046
    """
    # when: 범위 밖 값을 저장한다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=days)

    # then: InvalidValueError(범위 문구)이고 저장소는 비어 있다
    assert await _stored(uow_factory) is None


async def test_update_out_of_range_keeps_the_previous_value(
    update_settings: UpdateAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    """범위 밖 정수로 저장하려 해도 저장된 값은 그대로다.

    테스트 코드: RK-046
    """
    # given: admin이 20일로 저장했다
    await update_settings.execute(actor=admin, stale_days=20)
    before = await _stored(uow_factory)
    clock.advance(60)

    # when: 0일로 저장하려 한다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=0)

    # then: InvalidValueError이고 저장된 값이 그대로다
    assert await _stored(uow_factory) == before


async def test_update_rejects_a_bool_as_the_value(
    update_settings: UpdateAlertSettings, uow_factory: UnitOfWorkFactory, admin: Principal
) -> None:
    """bool은 정수로 보지 않고 거절한다.

    테스트 코드: RK-047
    """
    # when: True로 저장하려 한다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        await update_settings.execute(actor=admin, stale_days=True)

    # then: InvalidValueError이고 저장되지 않는다
    assert await _stored(uow_factory) is None


async def test_last_save_wins(
    update_settings: UpdateAlertSettings,
    get_settings: GetAlertSettings,
    uow_factory: UnitOfWorkFactory,
    admin: Principal,
    clock: FixedClock,
) -> None:
    """다른 admin이 다시 저장하면 값·저장자·시각이 모두 마지막 저장으로 바뀐다.

    테스트 코드: RK-049
    """
    # given: admin A가 7일로 저장했고 1분이 지났다
    await update_settings.execute(actor=admin, stale_days=7)
    other = (await seed_user(uow_factory, "boss2", Role.ADMIN)).to_principal()
    clock.advance(60)

    # when: 다른 admin B가 21일로 저장한다
    await update_settings.execute(actor=other, stale_days=21)

    view = await get_settings.execute()
    # then: 조회하면 21일, B, B의 저장 시각이다
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
    """저장자 참조는 저장 트랜잭션 안(commit 전)에서 읽는다."""
    # given: 저장자 참조를 읽는 시점의 commit 수를 기록하도록 감쌌다
    original = uow.users.get_refs
    commits_before = uow.commits
    seen: list[int] = []

    async def get_refs(user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        seen.append(uow.commits - commits_before)
        return await original(user_ids)

    monkeypatch.setattr(uow.users, "get_refs", get_refs)

    # when: admin이 12일로 저장한다
    view = await update_settings.execute(actor=admin, stale_days=12)

    # then: 저장자 참조 읽기는 commit 전 한 번이고 결과의 저장자가 admin이다
    assert seen == [0]
    assert view.updated_by is not None
    assert view.updated_by.id == admin.user_id
