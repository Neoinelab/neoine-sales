"""저장 위치 설정 관리 유스케이스(admin 전용은 web 계층): 조회·변경·쓰기 테스트 (P2b AC-05·06)."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.ports.file_storage import StorageNotWritableError
from app.application.storage.probe import ensure_writable
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.storage.path import StoragePath
from tests.factories import NOW
from tests.support.auth_seed import seed_storage, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.storage.settings import StoredStorageSettings
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.storage_stack import StorageStack
    from tests.fakes.unit_of_work import FixedClock

NOT_ABSOLUTE = "절대 경로를 입력하세요."
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."
BLOCKED_ROOT = "/blocked"
UNWRITABLE_PATH = "/blocked/files"


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredStorageSettings | None:
    async with uow_factory() as uow:
        return await uow.storage_settings.get()


@pytest.fixture
async def admin_actor(uow_factory: UnitOfWorkFactory) -> Principal:
    return (await seed_user(uow_factory, "root", Role.ADMIN)).to_principal()


# ---- GetStorageSettings ----


async def test_get_storage_settings_without_a_saved_path_is_not_found(
    storage: StorageStack,
) -> None:
    with pytest.raises(NotFoundError):
        await storage.get_settings.execute()


async def test_get_storage_settings_returns_the_saved_settings(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    saved = await seed_storage(uow_factory, "/data/saved")

    assert await storage.get_settings.execute() == saved


# ---- UpdateStorageSettings ----


async def test_update_storage_settings_records_the_actor_and_the_time(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    clock: FixedClock,
) -> None:
    await seed_storage(uow_factory, "/data/old")
    clock.advance(90)

    stored = await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new")

    assert stored.path.value == "/data/new"
    assert stored.updated_by == admin_actor.user_id
    assert stored.updated_at == NOW + timedelta(seconds=90)
    assert await _stored(uow_factory) == stored


async def test_update_storage_settings_normalizes_the_path(
    storage: StorageStack, admin_actor: Principal
) -> None:
    stored = await storage.update_settings.execute(
        actor=admin_actor, raw_path="  /data//new files/ "
    )

    assert stored.path.value == "/data/new files"


async def test_update_storage_settings_creates_the_missing_directory(
    storage: StorageStack, admin_actor: Principal, file_storage: FakeFileStorage
) -> None:
    await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new/deep")

    assert file_storage.dir_exists("/data/new/deep")
    assert file_storage.entries("/data/new/deep") == []


async def test_update_storage_settings_works_when_no_path_was_saved_yet(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, admin_actor: Principal
) -> None:
    """dev·local처럼 admin이 이미 있고 저장 위치만 없는 DB에서 admin이 처음 등록한다."""
    stored = await storage.update_settings.execute(actor=admin_actor, raw_path="/data/first")

    assert await _stored(uow_factory) == stored


async def test_update_storage_settings_rejects_an_unwritable_path_and_keeps_the_old_one(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    file_storage: FakeFileStorage,
) -> None:
    old = await seed_storage(uow_factory, "/data/old")
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError) as caught:
        await storage.update_settings.execute(actor=admin_actor, raw_path=UNWRITABLE_PATH)

    assert str(caught.value) == NOT_WRITABLE
    assert await _stored(uow_factory) == old


@pytest.mark.parametrize("raw", ["", "relative", "/a/../b"])
async def test_update_storage_settings_rejects_a_malformed_path_without_probing(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    file_storage: FakeFileStorage,
    raw: str,
) -> None:
    old = await seed_storage(uow_factory, "/data/old")

    with pytest.raises(InvalidValueError) as caught:
        await storage.update_settings.execute(actor=admin_actor, raw_path=raw)

    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []
    assert await _stored(uow_factory) == old


async def test_update_storage_settings_does_not_move_existing_files(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    file_storage: FakeFileStorage,
) -> None:
    from app.application.ports.file_storage import StoredFileLocation  # noqa: PLC0415
    from app.domain.deal.code import DealCode  # noqa: PLC0415
    from tests.fakes.file_storage import BytesSource  # noqa: PLC0415

    old = await seed_storage(uow_factory, "/data/old")
    location = StoredFileLocation(deal_code=DealCode("20261016-A001"), key="a" * 32)
    await file_storage.save(old.path, location, BytesSource(b"payload"), max_bytes=100)

    await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new")

    assert file_storage.contents_of(old.path, location) == b"payload"
    assert file_storage.contents_of(StoragePath.parse("/data/new"), location) is None


# ---- TestStorageSettings ----


async def test_storage_settings_test_saves_nothing(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_storage(uow_factory, "/data/old")

    await storage.test_settings.execute("/data/other")

    assert await _stored(uow_factory) == old


async def test_storage_settings_test_succeeds_for_a_writable_path_even_without_saved_settings(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    await storage.test_settings.execute("/data/other")

    assert file_storage.dir_exists("/data/other")


async def test_storage_settings_test_rejects_an_unwritable_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError) as caught:
        await storage.test_settings.execute(UNWRITABLE_PATH)

    assert str(caught.value) == NOT_WRITABLE


async def test_storage_settings_test_rejects_a_malformed_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_settings.execute("relative")

    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []


# ---- ensure_writable ----


async def test_ensure_writable_passes_for_a_writable_root(file_storage: FakeFileStorage) -> None:
    await ensure_writable(file_storage, StoragePath.parse("/data/files"))

    assert file_storage.dir_exists("/data/files")


async def test_ensure_writable_turns_the_storage_failure_into_the_fixed_user_message(
    file_storage: FakeFileStorage,
) -> None:
    file_storage.block(BLOCKED_ROOT)

    with pytest.raises(InvalidValueError) as caught:
        await ensure_writable(file_storage, StoragePath.parse(UNWRITABLE_PATH))

    assert str(caught.value) == NOT_WRITABLE


async def test_ensure_writable_does_not_leak_the_storage_error_text(
    file_storage: FakeFileStorage,
) -> None:
    class Leaky:
        async def check_writable(self, root: StoragePath) -> None:
            raise StorageNotWritableError("PermissionError: /secret/internal/path")

    with pytest.raises(InvalidValueError) as caught:
        await ensure_writable(Leaky(), StoragePath.parse("/data/files"))  # type: ignore[arg-type, unused-ignore]

    assert "secret" not in str(caught.value)
    assert str(caught.value) == NOT_WRITABLE
