"""ldap3 어댑터(MOCK_SYNC) 사용자 바인드 이름(AU-R7a): 도메인이 있으면 UPN, 없으면 찾은 DN."""

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
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_settings
from tests.support.ldap_adapter import PASSWORD, make_adapter

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory

DOMAIN = "neoine.co.kr"
KIM_DN = f"cn=kim,ou=users,{BASE_DN}"
KIM_UPN = f"kim@{DOMAIN}"


def _bind_users(directory: MockDirectory) -> list[str | None]:
    """만들어진 연결의 바인드 이름(첫째는 서비스 계정, 그 뒤가 사용자 바인드)."""
    return [user for _, user, _ in directory.factory_calls]


async def _authenticate(
    directory: MockDirectory,
    login_id: object = "kim",
    *,
    domain: str | None = DOMAIN,
    **overrides: Any,  # noqa: ANN401
) -> DirectoryUser:
    adapter = make_adapter(directory, user_bind_domain=domain)
    typed = LoginId(login_id) if isinstance(login_id, str) else login_id
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
    assert (user.login_id, user.display_name, user.email) == ("kim", "김영업", "kim@corp.test")
    assert directory.factory_calls[0][1:] == (KIM_UPN, PASSWORD)
    assert len(directory.connections) == 1
    assert KIM_DN not in _bind_users(directory)
    searches = [a for c in directory.connections for a in c.search_args]
    assert len(searches) == 1
    assert directory.connections[0].search_args == searches
    assert searches[0]["search_base"] == BASE_DN
    assert "kim" in str(searches[0]["search_filter"])
    assert directory.calls.count("unbind") == 1


async def test_user_bind_uses_the_found_dn_without_a_domain(directory: MockDirectory) -> None:
    """도메인이 없으면 찾은 항목의 DN으로 바인드한다.

    테스트 코드: AU-094
    """
    with pytest.raises(DirectoryMisconfiguredError):
        await _authenticate(directory, domain=None)
    assert directory.factory_calls == []


async def test_search_outcomes_are_unchanged_with_a_domain(directory: MockDirectory) -> None:
    """도메인이 있어도 검색 0건은 자격 증명 오류, 2건 이상은 search 오류다(사용자 바인드 없음).

    테스트 코드: AU-095
    """
    # given: 도메인 어댑터, 아이디 nobody는 항목이 없다
    directory.upn_passwords[f"nobody@{DOMAIN}"] = PASSWORD
    # when: nobody로 인증한다
    with pytest.raises(InvalidCredentialsError) as zero:
        await _authenticate(directory, "nobody")

    # then: search 단계 자격 증명 오류, 서비스 계정 연결 하나뿐
    assert zero.value.stage is VerificationStage.SEARCH
    assert _bind_users(directory) == [f"nobody@{DOMAIN}"]

    # given: 필터가 여러 항목에 걸린다
    many = type(directory)()
    many.add_user("kim", PASSWORD)
    many.add_user("lee", PASSWORD)
    many.upn_passwords[KIM_UPN] = PASSWORD

    # when: 인증한다
    with pytest.raises(DirectoryMisconfiguredError) as multiple:
        await _authenticate(many, user_filter="(|(cn={login_id})(objectClass=user))")

    # then: search 단계 설정 오류, 서비스 계정 연결 하나뿐이고 UPN 바인드는 없다
    assert multiple.value.stage is VerificationStage.SEARCH
    assert _bind_users(many) == [KIM_UPN]


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
    assert (type(caught.value) is InvalidCredentialsError) == invalid
    assert KIM_UPN not in str(caught.value)
    assert PASSWORD not in str(caught.value)


async def test_domain_bind_name_uses_the_normalized_login_id(directory: MockDirectory) -> None:
    """바인드 이름은 정규화한 아이디(" KIM " -> kim)와 도메인으로 만든다.

    테스트 코드: AU-097
    """
    # given: 정리된 도메인 neoine.co.kr (설정 정리는 test_settings_ad_login_domain)
    directory.upn_passwords[KIM_UPN] = PASSWORD

    # when: 아이디 " KIM "으로 인증한다
    await _authenticate(directory, " KIM ")

    # then: 사용자 바인드 이름은 kim@neoine.co.kr이다
    assert _bind_users(directory)[0] == KIM_UPN


async def test_rejected_upn_bind_logs_only_safe_ad_diagnostics(
    directory: MockDirectory, caplog: pytest.LogCaptureFixture
) -> None:
    """AD 계정 잠금 사유만 기록하고 LDAP 원문과 자격증명은 숨긴다."""
    # given: LDAP 49와 AD 잠금 코드가 포함된 바인드 거절 응답
    directory.bind_codes_by_user[KIM_UPN] = 49
    directory.bind_diagnostic = f"LDAP diagnostic data 775, {KIM_UPN} {PASSWORD}"

    # when·then: 로그인은 거절되고 안전한 진단 값만 로그에 남는다
    with pytest.raises(InvalidCredentialsError):
        await _authenticate(directory)
    assert "reason=ad_account_locked" in caplog.text
    assert "ldap_code=49" in caplog.text
    assert KIM_UPN not in caplog.text
    assert PASSWORD not in caplog.text


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
    assert _bind_users(directory) == []
