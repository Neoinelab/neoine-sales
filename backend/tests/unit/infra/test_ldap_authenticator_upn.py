"""ldap3 어댑터(MOCK_SYNC)의 사용자 바인드 이름(AU-R7a): 도메인이 있으면 `아이디@도메인`, 없으면 DN."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    DirectoryUser,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, make_adapter

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory

DOMAIN = "neoine.co.kr"
KIM_DN = f"cn=kim,ou=users,{BASE_DN}"
KIM_UPN = f"kim@{DOMAIN}"


def _bind_users(directory: MockDirectory) -> list[str | None]:
    """만들어진 연결의 바인드 이름(서비스 계정 연결 다음부터가 사용자 바인드)."""
    return [user for _, user, _ in directory.factory_calls]


async def _authenticate(
    directory: MockDirectory,
    login_id: object = "kim",
    *,
    domain: str | None = DOMAIN,
    **overrides: Any,  # noqa: ANN401
) -> DirectoryUser:
    adapter = make_adapter(directory, user_bind_domain=domain)
    typed = login_id if not isinstance(login_id, str) else LoginId(login_id)
    return await adapter.authenticate(
        make_directory_settings(**overrides), BASE_DN, cast("LoginId", typed), Password(PASSWORD)
    )


async def test_user_bind_uses_login_id_at_domain_when_a_domain_is_set(
    directory: MockDirectory,
) -> None:
    """도메인이 있으면 사용자 비밀번호 바인드는 아이디@도메인이고 검색·프로필은 그대로다.

    테스트 코드: AU-093
    """
    # given: 도메인 neoine.co.kr 어댑터, kim@neoine.co.kr 바인드가 비밀번호를 받아들인다
    directory.upn_passwords[KIM_UPN] = PASSWORD

    # when: kim이 인증한다
    user = await _authenticate(directory)

    # then: 프로필은 검색 결과에서 읽고, 연결은 서비스 계정, UPN 두 번이며 DN 바인드는 없다
    assert (user.login_id, user.display_name, user.email) == (
        "kim",
        "김영업",
        "kim@corp.test",
    )
    assert directory.factory_calls[0][1:] == (BIND_ACCOUNT, BIND_PASSWORD)
    assert directory.factory_calls[1][1:] == (KIM_UPN, PASSWORD)
    assert len(directory.connections) == 2
    assert KIM_DN not in _bind_users(directory)
    searches = [a for c in directory.connections for a in c.search_args]
    assert len(searches) == 1
    assert searches[0]["search_base"] == BASE_DN
    assert "kim" in str(searches[0]["search_filter"])
    assert directory.connections[0].search_args == searches
    assert directory.calls.count("unbind") == 2


@pytest.mark.parametrize("domain", [None], ids=["no-domain"])
async def test_user_bind_uses_the_found_dn_without_a_domain(
    directory: MockDirectory, domain: str | None
) -> None:
    """도메인이 없으면 찾은 항목의 DN으로 바인드한다.

    테스트 코드: AU-094
    """
    # when: 도메인 없는 어댑터로 kim이 인증한다
    user = await _authenticate(directory, domain=domain)

    # then: 성공하고 사용자 바인드 이름은 찾은 DN이다
    assert user.login_id == "kim"
    assert _bind_users(directory) == [BIND_ACCOUNT, KIM_DN]


async def test_search_outcomes_are_unchanged_with_a_domain(directory: MockDirectory) -> None:
    """도메인이 있어도 검색 0건은 자격 증명 오류, 2건 이상은 search 오류다(사용자 바인드 없음).

    테스트 코드: AU-095
    """
    # given: 도메인 어댑터, 아이디 nobody는 항목이 없다
    # when: nobody로 인증한다
    with pytest.raises(InvalidCredentialsError) as zero:
        await _authenticate(directory, "nobody")

    # then: search 단계 자격 증명 오류, 서비스 계정 연결 하나뿐
    assert zero.value.stage is VerificationStage.SEARCH
    assert _bind_users(directory) == [BIND_ACCOUNT]

    # given: 필터가 여러 항목에 걸린다
    many = type(directory)()
    many.add_user("kim", PASSWORD)
    many.add_user("lee", PASSWORD)

    # when: 인증한다
    with pytest.raises(DirectoryMisconfiguredError) as multiple:
        await _authenticate(many, user_filter="(objectClass=user)")

    # then: search 단계 설정 오류, 서비스 계정 연결 하나뿐이고 UPN 바인드는 없다
    assert multiple.value.stage is VerificationStage.SEARCH
    assert _bind_users(many) == [BIND_ACCOUNT]


@pytest.mark.parametrize(
    ("code", "invalid"),
    [(49, True), (50, True), (53, True), (51, False), (52, False)],
)
async def test_domain_bind_rejection_is_invalid_credentials_and_other_codes_are_unavailable(
    directory: MockDirectory, code: int, invalid: bool
) -> None:
    """도메인 바인드 거절(49·50·53)은 자격 증명 오류, 그 밖의 결과 코드는 AD 불가다.

    테스트 코드: AU-096
    """
    # given: 서비스 계정 바인드는 성공, kim@도메인 바인드는 결과 코드 code로 끝난다
    directory.bind_codes_by_user[KIM_UPN] = code

    # when: kim이 인증한다
    expected = InvalidCredentialsError if invalid else DirectoryUnavailableError
    with pytest.raises(expected) as caught:
        await _authenticate(directory)

    # then: bind 단계 오류이고 문구에 바인드 이름·비밀번호가 없다
    assert caught.value.stage is VerificationStage.BIND
    assert KIM_UPN not in str(caught.value)
    assert PASSWORD not in str(caught.value)
    assert (type(caught.value) is InvalidCredentialsError) == invalid


async def test_domain_bind_name_uses_the_normalized_login_id(directory: MockDirectory) -> None:
    """바인드 이름은 정규화한 아이디(" KIM " -> kim)와 도메인으로 만든다.

    테스트 코드: AU-097
    """
    # given: 정리된 도메인 neoine.co.kr (설정 정리는 test_settings_ad_login_domain)
    directory.upn_passwords[KIM_UPN] = PASSWORD

    # when: 아이디 " KIM "으로 인증한다
    await _authenticate(directory, " KIM ")

    # then: 사용자 바인드 이름은 kim@neoine.co.kr이다
    assert _bind_users(directory)[1] == KIM_UPN


@pytest.mark.parametrize("hostile", ["x,ou=admins+cn=y", "kim@evil.test"])
async def test_hostile_login_id_never_reaches_a_domain_bind(
    directory: MockDirectory, hostile: str
) -> None:
    """DN·도메인 주입을 노린 아이디로는 사용자 바인드를 하지 않는다.

    테스트 코드: AU-100
    """
    # given: LoginId 검증을 건너뛴 아이디(형식 검사는 AU-016이 막는다)
    directory.upn_passwords[f"{hostile}@{DOMAIN}"] = PASSWORD
    login = SimpleNamespace(value=hostile)

    # when: 인증한다
    with pytest.raises(InvalidCredentialsError):
        await _authenticate(directory, login)

    # then: 서비스 계정 연결 하나뿐이다(필터 값으로만 쓰여 어느 항목에도 맞지 않는다)
    assert _bind_users(directory) == [BIND_ACCOUNT]
