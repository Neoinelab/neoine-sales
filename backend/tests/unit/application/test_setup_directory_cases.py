"""최초 설정 AD 서버 등록(RegisterSetupDirectory): SU-011~SU-013.

값 형식 위반(SU-014)은 요청 모델 검증이라 web 단위 테스트(`tests/unit/web/test_setup_routes.py`)다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import (
    DirectoryError,
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.mode import AuthMode
from tests.factories_auth import BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.auth_seed import seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack

LEAK = "internal-ldap-server-banner"
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


async def test_registering_the_directory_stores_the_found_base_dn_and_records_ad(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 서버를 등록하면 찾은 Base DN과 함께 저장되고 방식이 ad가 된다.

    테스트 코드: SU-011
    """
    # given: 새 시스템이고 AD가 Base DN dc=found,dc=test를 알려 준다
    auth.directory.base_dn = "dc=found,dc=test"
    settings = make_directory_settings()

    # when: 호스트·포트·보안 연결·바인드 계정·비밀번호·필터·제한 시간으로 AD 서버를 등록한다
    stored = await auth.register_directory.execute(settings)

    # then: Base DN 저장, revision 1, updated_by 없음, 비밀번호는 암호화 값, 방식 ad
    assert (stored.base_dn, stored.revision, stored.updated_by) == ("dc=found,dc=test", 1, None)
    assert stored.connection == settings.connection
    assert BIND_PASSWORD not in stored.sealed_bind_password.token
    assert auth.cipher.unseal(stored.sealed_bind_password) == BIND_PASSWORD
    # then: AD는 Base DN 탐색만 1회 받았고 사용자 인증은 받지 않았다
    assert len(auth.directory.discover_calls) == 1
    assert auth.directory.authenticate_calls == []
    # then: 방식은 ad, 진행 상태는 directory 끝·storage 필요
    async with uow_factory() as uow:
        mode = await uow.auth_settings.get()
    assert mode is not None
    assert mode.mode is AuthMode.AD
    status = await auth.status.execute()
    assert (status.needs_directory_setup, status.needs_storage_setup) == (False, True)


@pytest.mark.parametrize("chose_local_first", [False, True], ids=["resave", "after-local"])
async def test_registering_again_overwrites_and_switches_local_to_ad(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, *, chose_local_first: bool
) -> None:
    """admin 전에는 AD 서버를 다시 저장해 덮어쓰고 local을 골랐어도 ad로 바뀐다.

    테스트 코드: SU-012
    """
    # given: AD 서버가 한 번 등록되었다(또는 방식 local을 골라 두었다)
    if chose_local_first:
        await auth.choose_mode.execute(AuthMode.LOCAL)
    else:
        await auth.register_directory.execute(make_directory_settings())
    auth.directory.base_dn = "dc=other,dc=test"

    # when: 호스트 dc2.corp.test로 다시 등록한다
    stored = await auth.register_directory.execute(make_directory_settings(host="dc2.corp.test"))

    # then: revision은 이전 저장 수+1(처음이면 1), 새 호스트·Base DN, 방식 ad
    assert stored.revision == (1 if chose_local_first else 2)
    assert (stored.connection.host, stored.base_dn) == ("dc2.corp.test", "dc=other,dc=test")
    async with uow_factory() as uow:
        mode = await uow.auth_settings.get()
    assert mode is not None
    assert mode.mode is AuthMode.AD


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
async def test_a_failed_check_reports_only_the_stage_and_saves_nothing(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, error: DirectoryError, stage: str
) -> None:
    """AD 확인이 단계별로 실패하면 단계만 알리고 아무것도 저장하지 않는다.

    테스트 코드: SU-013
    """
    # given: 이전에 저장한 AD 설정이 있고, AD 확인이 원인 문구와 함께 그 단계에서 실패한다
    previous = await seed_directory(uow_factory)
    auth.directory.discover_fails_with = error

    # when: AD 서버를 등록한다
    with pytest.raises(DirectoryVerificationError) as caught:
        await auth.register_directory.execute(make_directory_settings(host="dc9.corp.test"))

    # then: 단계(없으면 connect)와 단계 문구만 담고 원인 문구·비밀번호는 없다
    assert str(caught.value.stage) == stage
    assert caught.value.message == STAGE_TEXT[VerificationStage(stage)]
    assert LEAK not in caught.value.message
    assert BIND_PASSWORD not in caught.value.message
    # then: 이전 AD 설정과 방식 행은 그대로(새로 기록되지 않음)
    async with uow_factory() as uow:
        assert await uow.directory_settings.get() == previous
        assert await uow.auth_settings.get() is None
