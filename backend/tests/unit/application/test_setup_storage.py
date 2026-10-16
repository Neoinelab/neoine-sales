"""최초 설정 2단계 RegisterSetupStorage·TestSetupStorage (P2b AC-02·03·06).

판정 순서: admin 있음(닫힘) → AD 설정 없음 → 경로 형식 → 쓰기 확인.
실패하면 아무것도 저장하지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from tests.factories import NOW
from tests.support.auth_seed import seed_directory, seed_storage, seed_user

if TYPE_CHECKING:
    from app.domain.storage.settings import StoredStorageSettings

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.storage_stack import StorageStack

NOT_ABSOLUTE = "절대 경로를 입력하세요."
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."
BLOCKED_ROOT = "/blocked"
UNWRITABLE_PATH = "/blocked/files"


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredStorageSettings | None:
    async with uow_factory() as uow:
        return await uow.storage_settings.get()


@pytest.fixture
async def directory_done(uow_factory: UnitOfWorkFactory) -> None:
    """최초 설정 1단계(AD 설정)가 끝난 상태."""
    await seed_directory(uow_factory)


# ---- RegisterSetupStorage ----


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_saves_the_normalized_path_without_a_saver(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    stored = await storage.register_setup.execute("  /data//neoine-sales/files/ ")

    assert stored.path.value == "/data/neoine-sales/files"
    assert (stored.updated_by, stored.updated_at) == (None, NOW)
    assert await _stored(uow_factory) == stored


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_creates_the_missing_directory_and_leaves_no_trace(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    assert not file_storage.dir_exists("/data/files/deep")

    await storage.register_setup.execute("/data/files/deep")

    assert file_storage.dir_exists("/data/files/deep")
    assert file_storage.entries("/data/files/deep") == []


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_can_be_overwritten_until_the_admin_exists(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    await storage.register_setup.execute("/data/first")

    second = await storage.register_setup.execute("/data/second")

    current = await _stored(uow_factory)
    assert current == second
    assert current is not None
    assert current.path.value == "/data/second"


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_rejects_an_unwritable_path_with_the_fixed_message(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError) as caught:
        await storage.register_setup.execute(UNWRITABLE_PATH)

    assert str(caught.value) == NOT_WRITABLE


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_unwritable_path_saves_nothing(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError):
        await storage.register_setup.execute(UNWRITABLE_PATH)

    assert await _stored(uow_factory) is None


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_unwritable_overwrite_keeps_the_previous_path(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    first = await storage.register_setup.execute("/data/first")
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError):
        await storage.register_setup.execute(UNWRITABLE_PATH)

    assert await _stored(uow_factory) == first


@pytest.mark.usefixtures("directory_done")
@pytest.mark.parametrize("raw", ["", "relative/path", "/a/../b"])
async def test_setup_storage_rejects_a_malformed_path_without_probing_the_disk(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    file_storage: FakeFileStorage,
    raw: str,
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await storage.register_setup.execute(raw)

    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []
    assert await _stored(uow_factory) is None


async def test_setup_storage_before_the_directory_step_is_rejected(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute("/data/files")

    assert str(caught.value) == DIRECTORY_FIRST
    assert file_storage.checked == []
    assert await _stored(uow_factory) is None


async def test_setup_storage_reports_the_directory_step_before_a_malformed_path(
    storage: StorageStack,
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute("relative")

    assert str(caught.value) == DIRECTORY_FIRST


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_is_closed_once_an_admin_exists(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    await seed_storage(uow_factory, "/data/original")
    await seed_user(uow_factory, "boss", Role.ADMIN)
    before = await _stored(uow_factory)

    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute("/data/other")

    assert str(caught.value) == SETUP_CLOSED
    assert await _stored(uow_factory) == before
    assert file_storage.checked == []


async def test_setup_storage_reports_closed_before_any_other_problem(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    """admin이 있으면 AD 설정이 없고 경로도 잘못되고 쓸 수도 없어도 '닫힘'이 먼저다."""
    await seed_user(uow_factory, "boss", Role.ADMIN)
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute("relative")

    assert str(caught.value) == SETUP_CLOSED
    assert file_storage.checked == []


# ---- TestSetupStorage ----


async def test_setup_storage_test_succeeds_without_saving_anything(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    await storage.test_setup.execute("/data/files")

    assert await _stored(uow_factory) is None
    assert file_storage.dir_exists("/data/files")
    assert file_storage.entries("/data/files") == []


async def test_setup_storage_test_does_not_require_the_directory_step(
    storage: StorageStack,
) -> None:
    await storage.test_setup.execute("/data/files")  # AD 설정이 없어도 예외가 없다


@pytest.mark.usefixtures("directory_done")
async def test_setup_storage_test_keeps_the_saved_path(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    saved = await storage.register_setup.execute("/data/saved")

    await storage.test_setup.execute("/data/other")

    assert await _stored(uow_factory) == saved


async def test_setup_storage_test_is_closed_once_an_admin_exists(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN)

    with pytest.raises(InvalidStateError) as caught:
        await storage.test_setup.execute("/data/files")

    assert str(caught.value) == SETUP_CLOSED
    assert file_storage.checked == []


async def test_setup_storage_test_rejects_a_malformed_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_setup.execute("relative")

    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []


async def test_setup_storage_test_rejects_an_unwritable_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError) as caught:
        await storage.test_setup.execute(UNWRITABLE_PATH)

    assert str(caught.value) == NOT_WRITABLE
