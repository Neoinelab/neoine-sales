"""최초 설정 2단계 저장 위치 등록·쓰기 테스트(RegisterSetupStorage·TestSetupStorage): SU-015~SU-022.

web 계층의 본문 형식 위반(SU-020)은 `tests/unit/web/test_setup_routes.py`다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import AUTH_MODE_FIRST, DIRECTORY_FIRST
from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidStateError, InvalidValueError
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_storage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.storage_stack import StorageStack

NOT_ABSOLUTE = "절대 경로를 입력하세요."
TOO_LONG = "저장 경로는 1024자 이내로 입력하세요."
HAS_NUL = "저장 경로에는 NUL 문자를 쓸 수 없습니다"
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."


async def _saved_path(uow_factory: UnitOfWorkFactory) -> str | None:
    async with uow_factory() as uow:
        stored = await uow.storage_settings.get()
    return None if stored is None else stored.path.value


async def test_registering_normalizes_the_path_creates_it_and_leaves_no_probe_file(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    """저장 위치를 등록하면 정규화한 경로가 저장되고 관리자 단계가 남는다.

    테스트 코드: SU-015
    """
    # given: AD 서버가 등록되었고 디렉터리는 아직 없다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    assert not file_storage.dir_exists("/srv/su/new/nested")

    # when: 앞뒤 공백·중복 슬래시·'.'가 섞인 경로를 등록한다
    stored = await storage.register_setup.execute("  //srv//su//new/./nested/  ")

    # then: 정규화한 경로가 저장되고 상위까지 만들어졌으며 확인용 파일은 남지 않았다
    assert stored.path.value == "/srv/su/new/nested"
    assert stored.updated_by is None
    assert await _saved_path(uow_factory) == "/srv/su/new/nested"
    assert file_storage.dir_exists("/srv/su/new/nested")
    assert file_storage.entries("/srv/su/new/nested") == []


async def test_a_failed_overwrite_keeps_the_previous_path(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    """admin 전에는 저장 위치를 덮어쓸 수 있고 실패한 덮어쓰기는 이전 경로를 남긴다.

    테스트 코드: SU-016
    """
    # given: 저장 위치 /data/first가 등록되었다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await storage.register_setup.execute("/data/first")

    # when: /data/second로 등록하고, 이어서 쓸 수 없는 위치로 등록한다
    await storage.register_setup.execute("/data/second")
    file_storage.block("/blocked")
    with pytest.raises(InvalidValueError) as caught:
        await storage.register_setup.execute("/blocked/files")

    # then: 저장값은 /data/second, 실패는 "해당 위치에 쓸 수 없습니다."이며 /data/second 그대로
    assert str(caught.value) == NOT_WRITABLE
    assert await _saved_path(uow_factory) == "/data/second"


@pytest.mark.parametrize("raw", ["/data/x", "relative"])
async def test_registering_without_a_mode_is_auth_mode_first_before_any_path_check(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage, raw: str
) -> None:
    """방식 미선택이면 저장 위치는 경로 검사 전에 409다.

    테스트 코드: SU-017
    """
    # when: 올바른 경로와 상대 경로로 등록한다 (전제: (가) 방식을 고르지 않았다)
    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute(raw)

    # then: 둘 다 "먼저 인증 방식을 고르세요."이고 쓰기 확인은 일어나지 않는다
    assert str(caught.value) == AUTH_MODE_FIRST
    assert file_storage.checked == []


@pytest.mark.parametrize("raw", ["/data/x", "relative"])
async def test_registering_in_ad_mode_without_a_directory_is_directory_first(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage, raw: str
) -> None:
    """AD 방식에서 AD 설정이 없으면 저장 위치는 경로 검사 전에 409다.

    테스트 코드: SU-017
    """
    # given: (나) 방식 ad이고 AD 설정이 없다
    await seed_auth_mode(uow_factory, AuthMode.AD)

    # when: 올바른 경로와 상대 경로로 등록한다
    with pytest.raises(InvalidStateError) as caught:
        await storage.register_setup.execute(raw)

    # then: 둘 다 "먼저 AD 서버를 등록하세요"이고 쓰기 확인은 일어나지 않는다
    assert str(caught.value) == DIRECTORY_FIRST
    assert file_storage.checked == []


async def test_registering_in_local_mode_needs_no_directory(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 방식에서는 AD 설정이 없어도 저장 위치를 등록할 수 있다.

    테스트 코드: SU-017
    """
    # given: (다) 방식 local이고 AD 설정이 없다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    # when: /data/x로 등록한다
    stored = await storage.register_setup.execute("/data/x")

    # then: 저장된다
    assert stored.path.value == "/data/x"


async def test_registering_with_a_chosen_ad_mode_and_directory_works(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """방식 행 없이 AD 설정만 있어도(유효 방식 ad) 저장 위치를 등록할 수 있다.

    테스트 코드: SU-017
    """
    # given: (라) 방식 행 없이 AD 설정만 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)

    # when: /data/x로 등록한다
    stored = await storage.register_setup.execute("/data/x")

    # then: 저장된다
    assert stored.path.value == "/data/x"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", NOT_ABSOLUTE),
        ("data/files", NOT_ABSOLUTE),
        ("/data/../etc", NOT_ABSOLUTE),
        ("/" + "a" * 1024, TOO_LONG),
        ("/data/\u0000x", HAS_NUL),
    ],
    ids=["empty", "relative", "dotdot", "1025-chars", "nul"],
)
async def test_a_malformed_path_is_invalid_value_and_never_touches_the_disk(
    storage: StorageStack,
    uow_factory: UnitOfWorkFactory,
    file_storage: FakeFileStorage,
    raw: str,
    message: str,
) -> None:
    """형식이 틀린 저장 경로는 422이고 디스크를 건드리지 않는다.

    테스트 코드: SU-018
    """
    # given: 저장 위치를 등록할 수 있는 상태다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)

    # when: 형식이 틀린 경로로 등록한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.register_setup.execute(raw)

    # then: 해당 문구의 invalid-value, 쓰기 확인 0회, 저장값 없음
    assert str(caught.value) == message
    assert file_storage.checked == []
    assert await _saved_path(uow_factory) is None


async def test_an_unwritable_location_has_a_fixed_message_and_saves_nothing(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    """쓸 수 없는 위치는 고정 문구의 422이고 저장되지 않는다.

    테스트 코드: SU-019
    """
    # given: 저장 위치를 등록할 수 있는 상태이고 쓰기 확인이 실패한다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    file_storage.block("/secret")

    # when: 그 경로로 등록한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.register_setup.execute("/secret/files")

    # then: 고정 문구이고 경로가 문구에 없으며 저장값은 없다
    assert str(caught.value) == NOT_WRITABLE
    assert "/secret" not in str(caught.value)
    assert await _saved_path(uow_factory) is None


async def test_the_write_test_saves_nothing_and_needs_no_mode_or_directory(
    storage: StorageStack, uow_factory: UnitOfWorkFactory, file_storage: FakeFileStorage
) -> None:
    """쓰기 테스트는 저장하지 않으며 방식·AD 설정 없이도 된다.

    테스트 코드: SU-021
    """
    # when: /data/test로 쓰기 테스트를 한다 (전제: 방식·AD 설정이 없다)
    await storage.test_setup.execute("/data/test")

    # then: 쓰기 확인은 했지만 저장 위치는 저장되지 않았고 진행 상태도 그대로다
    assert file_storage.checked == ["/data/test"]
    assert await _saved_path(uow_factory) is None


async def test_the_write_test_keeps_an_already_saved_path(
    storage: StorageStack, uow_factory: UnitOfWorkFactory
) -> None:
    """이미 저장된 경로가 있어도 쓰기 테스트는 그 값을 바꾸지 않는다.

    테스트 코드: SU-021
    """
    # given: 저장 위치 /data/saved가 이미 있다
    await seed_storage(uow_factory, "/data/saved")

    # when: /data/test로 쓰기 테스트를 한다
    await storage.test_setup.execute("/data/test")

    # then: 저장 위치는 /data/saved 그대로다
    assert await _saved_path(uow_factory) == "/data/saved"


@pytest.mark.parametrize("raw", ["relative", "", "/x/../y"])
async def test_the_write_test_rejects_a_malformed_path_like_registration(
    storage: StorageStack, raw: str
) -> None:
    """쓰기 테스트도 형식이 틀린 경로를 같은 문구로 알린다.

    테스트 코드: SU-022
    """
    # when: 상대 경로·빈 값·'..' 경로로 쓰기 테스트를 한다 (전제: 쓰기 테스트를 할 수 있는 상태다)
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_setup.execute(raw)

    # then: "절대 경로를 입력하세요."
    assert str(caught.value) == NOT_ABSOLUTE


async def test_the_write_test_rejects_an_unwritable_location(
    storage: StorageStack, file_storage: FakeFileStorage
) -> None:
    """쓰기 테스트도 쓸 수 없는 위치를 같은 문구로 알린다.

    테스트 코드: SU-022
    """
    # given: 쓸 수 없는 위치가 있다
    file_storage.block("/blocked")

    # when: 그 위치로 쓰기 테스트를 한다
    with pytest.raises(InvalidValueError) as caught:
        await storage.test_setup.execute("/blocked/files")

    # then: "해당 위치에 쓸 수 없습니다."
    assert str(caught.value) == NOT_WRITABLE
