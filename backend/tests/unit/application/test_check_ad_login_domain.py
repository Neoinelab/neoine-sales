"""AD 로그인 도메인 기동 검사 CheckAdLoginDomain(AU-R7c): AU-103, AU-105.

effective mode(AU-R22)가 ad이고 서버에 APP_AD_LOGIN_DOMAIN이 없으면 기동 검사가 실패한다. 오류
문구에는
환경변수 값·DB 주소·AD 설정 값을 싣지 않고, 검사는 DB를 읽기만 한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.directory.errors import AuthModeUnreadableError, DirectoryLoginDomainMissingError
from tests.support.auth_seed import seed_auth_mode, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

MISSING_TEXT = (
    "인증 방식이 AD 연동인데 서버 환경변수 APP_AD_LOGIN_DOMAIN이 설정되지 않았습니다. "
    "값을 설정한 뒤 다시 시작하세요"
)
UNREADABLE_TEXT = "기동 검사 중 인증 방식을 읽지 못했습니다. DB 연결을 확인하세요"
DB_ERROR = "connection to postgresql+psycopg://u:secret@db:5432/app failed"


async def _given(uow_factory: UnitOfWorkFactory, state: str) -> None:
    if state == "ad":  # (가) auth_settings = ad
        await seed_auth_mode(uow_factory, AuthMode.AD)
    elif state == "no-mode-with-directory":  # (나) 행 없음 + AD 설정 행 있음
        await seed_directory(uow_factory)
    elif state == "no-mode-with-admin":  # (다) 행 없음 + 재직 admin 있음
        await seed_user(uow_factory, "boss", Role.ADMIN)
    elif state == "local":  # (라)
        await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    # (마) 미선택: 행·admin·AD 설정 모두 없음


@pytest.mark.parametrize("state", ["ad", "no-mode-with-directory", "no-mode-with-admin"])
async def test_an_ad_system_without_a_login_domain_fails_with_a_value_free_message(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, state: str
) -> None:
    """effective mode가 ad이고 도메인이 없으면 값 없는 문구의 오류이고 DB를 읽기만 한다.

    테스트 코드: AU-103
    """
    # given: (가) auth_settings = ad (나) 행 없음 + AD 설정 행 (다) 행 없음 + 재직 admin
    await _given(uow_factory, state)
    commits_before = uow.commits

    # when: 도메인 없음으로 검사한다
    with pytest.raises(DirectoryLoginDomainMissingError) as caught:
        await auth.check_ad_login_domain(domain_configured=False).execute()

    # then: 고정 문구이고 아무것도 쓰지 않았다
    assert str(caught.value) == MISSING_TEXT
    assert uow.commits == commits_before


@pytest.mark.parametrize("state", ["local", "unselected"])
async def test_a_local_or_unselected_system_starts_without_a_login_domain(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, state: str
) -> None:
    """local이거나 미선택(새 시스템)이면 도메인이 없어도 통과한다.

    테스트 코드: AU-103
    """
    # given: (라) auth_settings = local (마) 행·admin·AD 설정이 모두 없음
    await _given(uow_factory, state)

    # when·then: 도메인 없음으로 검사해도 오류가 없다
    await auth.check_ad_login_domain(domain_configured=False).execute()


@pytest.mark.parametrize(
    "state", ["ad", "no-mode-with-directory", "no-mode-with-admin", "local", "unselected"]
)
async def test_every_system_starts_when_a_login_domain_is_configured(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, state: str
) -> None:
    """도메인이 있으면 어떤 방식이든 통과하고 아무것도 쓰지 않는다.

    테스트 코드: AU-103
    """
    # given: 다섯 경우 중 하나
    await _given(uow_factory, state)
    commits_before = uow.commits

    # when·then: 도메인 있음으로 검사해도 오류가 없고 쓰기도 없다
    await auth.check_ad_login_domain(domain_configured=True).execute()
    assert uow.commits == commits_before


@pytest.mark.parametrize("domain_configured", [False, True])
async def test_an_unreadable_auth_mode_stops_the_startup_without_leaking_the_database_address(
    auth: AuthStack, uow: FakeUnitOfWork, *, domain_configured: bool
) -> None:
    """인증 방식 조회가 DB 오류로 실패하면 기동 중단 오류이고 문구에 DB 주소가 없다.

    테스트 코드: AU-105
    """

    # given: 인증 방식 조회가 DB 연결 오류(메시지에 DB 주소와 비밀번호 포함)로 실패하는 저장소
    async def broken_get() -> None:
        raise ConnectionError(DB_ERROR)

    uow.auth_settings.get = broken_get  # type: ignore[method-assign]

    # when: 검사한다(도메인 유무와 무관하다)
    with pytest.raises(AuthModeUnreadableError) as caught:
        await auth.check_ad_login_domain(domain_configured=domain_configured).execute()

    # then: 고정 문구이고 DB 주소·비밀번호·호스트가 문구에 없다
    assert str(caught.value) == UNREADABLE_TEXT
    for leaked in ("secret", "db:5432", "postgresql"):
        assert leaked not in str(caught.value)
