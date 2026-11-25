"""최초 설정 AD 연결 테스트(TestSetupDirectory): SU-065~SU-067, SU-069.

형식 위반(SU-068)·로그인 없이 호출·비밀 비노출(SU-070)·openapi(SU-071)는 web 단위 테스트
(`tests/unit/web/test_setup_directory_test_routes.py`)다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import SETUP_CLOSED
from app.application.ports.directory import (
    DirectoryError,
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories_auth import BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack

LEAK = "internal-ldap-detail"
SUCCESS_MESSAGE = "AD 설정을 확인했습니다"
STAGE_TEXT = {
    VerificationStage.CONNECT: "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요",
    VerificationStage.TLS: (
        "TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요"
    ),
    VerificationStage.SERVICE_BIND: (
        "바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요"
    ),
    VerificationStage.BASE_DN: (
        "AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요"
    ),
}


async def test_a_successful_test_returns_the_found_base_dn_and_saves_nothing(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """연결 테스트가 성공하면 찾은 Base DN을 돌려주고 아무것도 저장하지 않는다.

    테스트 코드: SU-065
    """
    # given: 새 시스템이고 AD가 Base DN dc=found,dc=test를 알려 준다
    auth.directory.base_dn = "dc=found,dc=test"
    settings = make_directory_settings()

    # when: 입력 7칸으로 AD 연결 테스트를 한다
    result = await auth.test_setup_directory.execute(settings)

    # then: 성공 결과에 단계 없음·고정 문구·찾은 Base DN이 담긴다
    assert (result.success, result.stage, result.message, result.base_dn) == (
        True,
        None,
        SUCCESS_MESSAGE,
        "dc=found,dc=test",
    )
    # then: AD는 입력값으로 Base DN 탐색만 1회 받았고 사용자 인증은 받지 않았다
    assert auth.directory.discover_calls == [settings]
    assert auth.directory.authenticate_calls == []
    # then: AD 설정 행·방식은 없고 진행 상태는 처음 그대로다
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() is None
        assert await uow.auth_settings.get() is None
    status = await auth.status.execute()
    assert (status.needs_directory_setup, status.needs_storage_setup) == (True, True)


@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (DirectoryUnavailableError(LEAK, stage=VerificationStage.CONNECT), "connect"),
        (DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS), "tls"),
        (DirectoryMisconfiguredError(LEAK, stage=VerificationStage.SERVICE_BIND), "service_bind"),
        (DirectoryMisconfiguredError(LEAK, stage=VerificationStage.BASE_DN), "base_dn"),
        (DirectoryUnavailableError(LEAK), "connect"),
    ],
    ids=["connect", "tls", "service_bind", "base_dn", "no-stage"],
)
async def test_a_failed_check_is_a_failure_result_with_the_stage_message_only(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, error: DirectoryError, stage: str
) -> None:
    """확인이 단계별로 실패하면 예외 없이 실패 결과로 단계와 서버 문구만 알린다.

    테스트 코드: SU-066
    """
    # given: AD 확인이 원인 문구와 함께 그 단계에서 실패한다
    auth.directory.discover_fails_with = error

    # when: AD 연결 테스트를 한다
    result = await auth.test_setup_directory.execute(make_directory_settings())

    # then: success false, 단계(없으면 connect), 단계 문구, base_dn 없음
    assert result.success is False
    assert str(result.stage) == stage
    assert result.message == STAGE_TEXT[VerificationStage(stage)]
    assert result.base_dn is None
    # then: 원인 문구·바인드 비밀번호는 결과에 없고 아무것도 저장되지 않는다
    assert LEAK not in result.message
    assert BIND_PASSWORD not in result.message
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() is None
        assert await uow.auth_settings.get() is None


async def test_a_stored_directory_setting_is_neither_used_nor_changed(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 AD 설정이 있어도 입력값으로만 확인하고 저장된 설정은 바뀌지 않는다.

    테스트 코드: SU-067
    """
    # given: AD 서버(dc1.corp.test)가 revision 1로 등록되어 있다
    await auth.register_directory.execute(make_directory_settings())
    async with uow_factory() as uow:
        before = await uow.directory_settings.get()
        mode_before = await uow.auth_settings.get()
    assert before is not None
    new_settings = make_directory_settings(host="dc2.corp.test")

    # when: 호스트 dc2.corp.test로 연결 테스트를 한다
    result = await auth.test_setup_directory.execute(new_settings)

    # then: 성공이고 AD는 입력한 dc2 설정으로 확인되었다
    assert result.success is True
    assert auth.directory.discover_calls[-1] == new_settings
    # then: 저장된 설정(호스트·revision·암호문)과 방식 ad는 그대로다
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == before
        assert await uow.auth_settings.get() == mode_before
    assert before.connection.host == "dc1.corp.test"
    assert before.revision == 1
    assert mode_before is not None
    assert mode_before.mode is AuthMode.AD


async def test_a_chosen_local_mode_is_kept_when_testing(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """방식 local을 골라 둔 시스템도 테스트할 수 있고 방식·AD 설정 행은 그대로다.

    테스트 코드: SU-067
    """
    # given: 방식 local을 골랐고 AD 설정은 없다
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)

    # when: AD 연결 테스트를 한다
    result = await auth.test_setup_directory.execute(make_directory_settings())

    # then: 성공이고 방식은 local, AD 설정 행은 없으며 AD 단계는 끝나지 않았다
    assert result.success is True
    async with uow_factory() as uow:
        mode = await uow.auth_settings.get()
        assert await uow.directory_settings.get() is None
    assert mode is not None
    assert mode.mode is AuthMode.LOCAL
    assert (await auth.status.execute()).needs_directory_setup is False


@pytest.mark.parametrize("with_settings", [False, True], ids=["no-rows", "rows-kept"])
async def test_a_closed_setup_is_409_and_never_calls_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, *, with_settings: bool
) -> None:
    """재직 admin이 있으면 연결 테스트는 닫힘 오류이고 AD를 부르지 않는다.

    테스트 코드: SU-069
    """
    # given: 인증 방식이 저장된 재직 admin이 있다(AD 설정 행이 있거나 지워진 경우)
    await seed_auth_mode(uow_factory, AuthMode.AD)
    if with_settings:
        await seed_directory(uow_factory)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 올바른 입력으로 AD 연결 테스트를 한다
    with pytest.raises(InvalidStateError) as caught:
        await auth.test_setup_directory.execute(make_directory_settings())

    # then: 닫힘 문구이고 AD 확인 호출이 없다
    assert str(caught.value) == SETUP_CLOSED
    assert auth.directory.discover_calls == []
    assert auth.directory.authenticate_calls == []
