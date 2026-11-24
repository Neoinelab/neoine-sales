"""ldap3 어댑터(MOCK_SYNC)의 전화번호 속성 읽기(AU-R8a): mobile 우선, 비면 telephoneNumber."""

from typing import TYPE_CHECKING, cast

import pytest

from tests.support.ldap_adapter import PASSWORD, login

if TYPE_CHECKING:
    from tests.support.ldap_mock import MockDirectory


async def test_login_requests_mobile_and_telephone_number_attributes(
    directory: MockDirectory,
) -> None:
    """사용자 검색은 mobile과 telephoneNumber 속성을 함께 요청한다."""
    # when: 로그인한다 (전제: 모의 디렉터리에 kim이 있다)
    await login(directory)

    # then: 사용자 검색(RootDSE 제외)의 요청 속성에 두 속성이 모두 있다
    requested = {
        name.lower()
        for connection in directory.connections
        for args in connection.search_args
        if args.get("search_base") != ""
        for name in cast("list[str]", args.get("attributes") or [])
    }
    assert {"mobile", "telephonenumber"} <= requested


@pytest.mark.parametrize(
    ("mobile", "telephone", "expected"),
    [
        ("010-1234-5678", "02-123-4567", "010-1234-5678"),
        ("  010-1234-5678  ", None, "010-1234-5678"),
        ("010.1234.5678 내선 12", "02-123-4567", "010.1234.5678 내선 12"),
        (None, "02-123-4567", "02-123-4567"),
        ("", "02-123-4567", "02-123-4567"),
        ("   ", "+82 2-123-4567", "+82 2-123-4567"),
        (None, None, None),
        ("  ", "  ", None),
        (["010-1111-2222", "010-3333-4444"], None, "010-1111-2222"),
        (None, ["02-111-2222", "02-333-4444"], "02-111-2222"),
    ],
    ids=[
        "mobile-wins",
        "mobile-trimmed",
        "mobile-any-format-wins",
        "telephone-when-mobile-missing",
        "telephone-when-mobile-empty",
        "telephone-when-mobile-blank",
        "neither",
        "both-blank",
        "mobile-first-of-many",
        "telephone-first-of-many",
    ],
)
async def test_directory_phone_is_mobile_then_telephone_number(
    directory: MockDirectory,
    mobile: str | list[str] | None,
    telephone: str | list[str] | None,
    expected: str | None,
) -> None:
    """DirectoryUser.phone은 공백을 지운 mobile이 비지 않으면 그 값, 아니면 telephoneNumber다.

    테스트 코드: AU-090
    """
    # given: 경우마다 mobile·telephoneNumber를 가진(또는 없는) 사용자
    directory.add_user("phoned", PASSWORD, display_name="전화", mobile=mobile, telephone=telephone)

    # when: 그 사용자로 로그인한다
    user = await login(directory, "phoned")

    # then: 고른 값(없으면 None)이 phone이다
    assert user.phone == expected
