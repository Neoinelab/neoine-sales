"""저장 위치 설정 관리 유스케이스(admin 전용은 web 계층): 조회·변경·쓰기 테스트."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.ports.file_storage import StorageNotWritableError
from app.application.storage.probe import ensure_writable
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.storage.path import StoragePath
from tests.factories import NOW
from tests.support.auth_seed import seed_auth_mode, seed_storage, seed_user

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
    """저장 위치가 없으면 조회는 NotFoundError다.

    테스트 코드: IN-044
    """
    # when·then: 저장 위치를 조회한다 → NotFoundError다 (전제: 저장 위치 행이 없다)
    with pytest.raises(NotFoundError):
        await storage.get_settings.execute()


async def test_get_storage_settings_returns_the_saved_settings(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장 위치를 조회하면 저장된 경로·시각·저장자가 나온다.

    테스트 코드: IN-043
    """
    # when: 저장 위치를 조회한다 (전제: 경로가 저장되어 있다)
    saved = await seed_storage(uow_factory, "/data/saved")

    # then: 저장된 설정이 그대로 나온다
    assert await storage.get_settings.execute() == saved


# ---- UpdateStorageSettings ----


async def test_update_storage_settings_records_the_actor_and_the_time(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    clock: FixedClock,
) -> None:
    """저장 위치를 바꾸면 새 경로·저장자·서버 시각이 기록되고 다시 조회된다.

    테스트 코드: IN-045
    """
    # given: 저장 위치 /data/old와 90초 뒤의 서버 시계
    await seed_storage(uow_factory, "/data/old")
    clock.advance(90)

    # when: admin이 /data/new로 바꾼다
    stored = await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new")

    # then: 경로·저장자·시각이 기록되고 저장소에서 같은 값이 조회된다
    assert stored.path.value == "/data/new"
    assert stored.updated_by == admin_actor.user_id
    assert stored.updated_at == NOW + timedelta(seconds=90)
    assert await _stored(uow_factory) == stored


async def test_update_storage_settings_normalizes_the_path(
    storage: StorageStack, admin_actor: Principal
) -> None:
    """경로는 앞뒤 공백·중복 슬래시·끝 슬래시를 정리해 저장한다.

    테스트 코드: IN-046
    """
    # when: 공백과 중복 슬래시가 든 경로로 저장한다
    stored = await storage.update_settings.execute(
        actor=admin_actor, raw_path="  /data//new files/ "
    )

    # then: 정리된 경로가 저장된다
    assert stored.path.value == "/data/new files"


async def test_update_storage_settings_creates_the_missing_directory(
    storage: StorageStack, admin_actor: Principal, file_storage: FakeFileStorage
) -> None:
    """새 위치 디렉터리가 없으면 만들고 확인용 파일은 남기지 않는다.

    테스트 코드: IN-051
    """
    # when: 그 경로로 저장한다 (전제: /data/new/deep 디렉터리가 없다)
    await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new/deep")

    # then: 디렉터리가 생겼고 안에 파일이 없다
    assert file_storage.dir_exists("/data/new/deep")
    assert file_storage.entries("/data/new/deep") == []


async def test_update_storage_settings_works_when_no_path_was_saved_yet(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, admin_actor: Principal
) -> None:
    """저장 위치가 없는 시스템에서도 admin이 처음 등록할 수 있다.

    테스트 코드: IN-053
    """
    # when: admin이 /data/first로 저장한다 (전제: 저장 위치 행이 없다)
    stored = await storage.update_settings.execute(actor=admin_actor, raw_path="/data/first")

    # then: 저장소에 그 위치가 기록된다
    assert await _stored(uow_factory) == stored


async def test_update_storage_settings_rejects_an_unwritable_path_and_keeps_the_old_one(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    file_storage: FakeFileStorage,
) -> None:
    """쓸 수 없는 위치는 고정 문구로 거절되고 기존 위치는 그대로다.

    테스트 코드: IN-050
    """
    # given: 저장 위치 /data/old와 쓰기를 막은 Fake 저장소
    old = await seed_storage(uow_factory, "/data/old")
    file_storage.block(BLOCKED_ROOT)

    # when: 쓸 수 없는 경로로 저장한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.update_settings.execute(actor=admin_actor, raw_path=UNWRITABLE_PATH)

    # then: 고정 문구의 InvalidValueError이고 저장 위치는 /data/old다
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
    """절대 경로가 아니거나 ..가 있는 경로는 쓰기 확인 전에 거절되고 기존 위치는 그대로다.

    테스트 코드: IN-047
    """
    # given: 저장 위치 /data/old
    old = await seed_storage(uow_factory, "/data/old")

    # when: 빈 값·상대 경로·..가 있는 경로로 저장한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.update_settings.execute(actor=admin_actor, raw_path=raw)

    # then: '절대 경로를 입력하세요.' InvalidValueError이고 쓰기 확인 호출이 없으며 위치는 그대로다
    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []
    assert await _stored(uow_factory) == old


async def test_update_storage_settings_does_not_move_existing_files(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    admin_actor: Principal,
    file_storage: FakeFileStorage,
) -> None:
    """위치를 바꿔도 기존 파일은 옮기거나 복사하지 않는다.

    테스트 코드: IN-052
    """
    # given: /data/old에 첨부 파일이 있다
    from app.domain.deal.code import DealCode  # noqa: PLC0415
    from tests.fakes.file_storage import BytesSource, deal_location  # noqa: PLC0415

    old = await seed_storage(uow_factory, "/data/old")
    location = deal_location(DealCode("20261016-A001"), "a" * 32)
    await file_storage.save(old.path, location, BytesSource(b"payload"), max_bytes=100)

    # when: 저장 위치를 /data/new로 바꾼다
    await storage.update_settings.execute(actor=admin_actor, raw_path="/data/new")

    # then: /data/old의 파일은 그대로이고 /data/new에는 없다
    assert file_storage.contents_of(old.path, location) == b"payload"
    assert file_storage.contents_of(StoragePath.parse("/data/new"), location) is None


# ---- TestStorageSettings ----


async def test_storage_settings_test_saves_nothing(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """쓰기 테스트는 저장된 위치를 바꾸지 않는다.

    테스트 코드: IN-054
    """
    # given: 저장 위치 /data/old
    old = await seed_storage(uow_factory, "/data/old")

    # when: /data/other로 쓰기 테스트한다
    await storage.test_settings.execute("/data/other")

    # then: 저장된 위치는 그대로다
    assert await _stored(uow_factory) == old


async def test_storage_settings_test_succeeds_for_a_writable_path_even_without_saved_settings(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    """저장된 위치가 없어도 쓸 수 있는 경로의 쓰기 테스트는 성공한다.

    테스트 코드: IN-054
    """
    # when: /data/other로 쓰기 테스트한다 (전제: 저장 위치 행이 없다)
    await storage.test_settings.execute("/data/other")

    # then: 성공하고 저장소에는 행이 없다
    assert file_storage.dir_exists("/data/other")


async def test_storage_settings_test_rejects_an_unwritable_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    """쓸 수 없는 위치의 쓰기 테스트는 고정 문구로 거절된다.

    테스트 코드: IN-055
    """
    # given: 쓰기를 막은 Fake 저장소
    file_storage.block(BLOCKED_ROOT)

    # when: 쓸 수 없는 경로로 쓰기 테스트한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_settings.execute(UNWRITABLE_PATH)

    # then: 고정 문구의 InvalidValueError다
    assert str(caught.value) == NOT_WRITABLE


async def test_storage_settings_test_rejects_a_malformed_path(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    """형식이 틀린 경로의 쓰기 테스트는 쓰기 확인 없이 거절된다.

    테스트 코드: IN-055
    """
    # when: 상대 경로로 쓰기 테스트한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_settings.execute("relative")

    # then: '절대 경로를 입력하세요.' InvalidValueError이고 쓰기 확인 호출이 없다
    assert str(caught.value) == NOT_ABSOLUTE
    assert file_storage.checked == []


# ---- ensure_writable ----


async def test_ensure_writable_passes_for_a_writable_root(file_storage: FakeFileStorage) -> None:
    """쓸 수 있는 루트는 쓰기 확인을 통과하고 디렉터리가 만들어진다."""
    # when: 쓰기 확인을 한다
    await ensure_writable(file_storage, StoragePath.parse("/data/files"))

    # then: 오류 없이 디렉터리가 생긴다
    assert file_storage.dir_exists("/data/files")


async def test_ensure_writable_turns_the_storage_failure_into_the_fixed_user_message(
    file_storage: FakeFileStorage,
) -> None:
    """저장소의 쓰기 실패를 고정 사용자 문구로 바꾼다."""
    # given: 쓰기가 막힌 저장소
    file_storage.block(BLOCKED_ROOT)

    # when: 쓰기 확인을 한다
    with pytest.raises(InvalidValueError) as caught:
        await ensure_writable(file_storage, StoragePath.parse(UNWRITABLE_PATH))

    # then: 입력값 오류이고 문구가 고정 문구다
    assert str(caught.value) == NOT_WRITABLE


async def test_ensure_writable_does_not_leak_the_storage_error_text(
    file_storage: FakeFileStorage,
) -> None:
    """저장소 오류의 원인 문구(OS 오류·경로)는 사용자 문구에 새지 않는다.

    테스트 코드: IN-050
    """

    # given: 오류 문구에 내부 경로가 담긴 저장소가 쓰기 실패를 낸다
    class Leaky:
        async def check_writable(self, root: StoragePath) -> None:
            raise StorageNotWritableError("PermissionError: /secret/internal/path")

    # when: 쓰기 확인을 한다
    with pytest.raises(InvalidValueError) as caught:
        await ensure_writable(Leaky(), StoragePath.parse("/data/files"))  # type: ignore[arg-type, unused-ignore]

    # then: 사용자 문구는 고정 문구이고 내부 경로가 없다
    assert "secret" not in str(caught.value)
    assert str(caught.value) == NOT_WRITABLE


async def test_storage_settings_are_readable_and_changeable_in_local_mode(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, admin_actor: Principal
) -> None:
    """local 모드에서도 저장 위치를 그대로 조회하고 변경한다.

    테스트 코드: IN-057
    """
    # given: 인증 방식이 local이고 저장 위치가 /data/a다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory, "/data/a")

    # when: BOSS가 조회하고 /data/b로 바꾼다
    read = await storage.get_settings.execute()
    changed = await storage.update_settings.execute(actor=admin_actor, raw_path="/data/b")

    # then: 조회는 /data/a, 변경 결과와 저장된 값은 /data/b다
    assert read.path.value == "/data/a"
    assert changed.path.value == "/data/b"
    assert await _stored(uow_factory) == changed


@pytest.mark.parametrize(
    ("raw", "message"),
    [("", NOT_ABSOLUTE), ("/" + "a" * 2000, "저장 경로는 1024자 이내로 입력하세요.")],
)
async def test_empty_and_overlong_paths_are_refused_with_the_domain_message(
    storage: StorageStack, admin_actor: Principal, raw: str, message: str
) -> None:
    """빈 값과 너무 긴 경로는 요청 형식이 아니라 도메인 문구로 거절한다.

    테스트 코드: IN-056
    """
    # when: 빈 경로 또는 2000자 경로로 저장한다
    with pytest.raises(InvalidValueError) as caught:
        # then: 도메인 문구의 InvalidValueError다
        await storage.update_settings.execute(actor=admin_actor, raw_path=raw)

    assert str(caught.value) == message
