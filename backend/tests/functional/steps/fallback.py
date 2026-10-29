"""AD 장애 중 대체 로그인 feature의 step: AD 장애·설정 없음 준비, 로그인 요청, 경고 확인.

대체 로그인은 AD 로그인에 성공한 적 있는 사용자(비밀번호 해시가 저장된 사용자)만 AD가 답하지 못할 때
들어올 수 있다. 사전 상태는 공개 API(로그인)로 만든다.
"""

from typing import TYPE_CHECKING

from tests.functional.steps.auth import given_logged_out, password_of
from tests.functional.steps.login import when_log_in
from tests.functional.steps.settings import directory_error, given_settings_row_removed

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

# 대체 로그인 판정 대상 단계 -> AD 장애 모양 (kind, VerificationStage 값)
OUTAGES = {
    "connect": ("unavailable", "connect"),
    "tls": ("unavailable", "tls"),
    "service_bind": ("misconfigured", "service_bind"),
    "base_dn": ("misconfigured", "base_dn"),
    "search": ("misconfigured", "search"),  # 검색 결과가 2건 이상(사용자 필터 오류)
}
STALE_PHRASE = "이전에 로그인한 비밀번호로 로그인했습니다"


async def given_signed_in_through_directory_once(api: Api, *, login_id: str) -> None:
    """AD로 한 번 로그인해 대체 로그인용 해시가 저장돼 있고, 로그아웃한 상태다."""
    response = await when_log_in(api, login_id=login_id)
    assert response.status_code == 200, response.text
    await given_logged_out(api)


async def given_directory_is_down(api: Api, *, stage: str = "connect") -> None:
    """회사 AD가 해당 단계에서 답하지 못한다(Base DN 탐색과 사용자 인증 모두)."""
    kind, value = OUTAGES[stage]
    api.directory.fail_all_with(directory_error(kind, value))


def given_directory_recovers(api: Api) -> None:
    api.directory.fail_all_with(None)


async def given_directory_settings_are_missing(api: Api) -> None:
    """저장된 AD 설정 행이 없다(공개 API로는 만들 수 없어 DB에서 직접 지운다)."""
    await given_settings_row_removed(api)


async def when_log_in_with_the_directory_password(api: Api, *, login_id: str) -> Response:
    return await when_log_in(api, login_id=login_id, password=password_of(login_id))


def then_signed_in_with_warning(response: Response, *, stage: str) -> None:
    """200으로 로그인됐고 응답에 해당 단계의 경고(안내 문구 포함)가 있다."""
    from app.application.auth.messages import FALLBACK_MESSAGES  # noqa: PLC0415 - 구현 지연 import

    assert response.status_code == 200, response.text
    warning = response.json()["directory_warning"]
    assert warning is not None, response.text
    assert warning["stage"] == stage
    assert warning["message"] == FALLBACK_MESSAGES[stage]  # type: ignore[index]
    assert STALE_PHRASE in warning["message"]
    assert set(warning) == {"stage", "message"}


def then_signed_in_without_warning(response: Response) -> None:
    assert response.status_code == 200, response.text
    assert response.json()["directory_warning"] is None


def then_login_is_refused_as_unavailable(response: Response) -> None:
    """AD 불가 응답 그대로 거절된다: 503 directory-unavailable, 세션 쿠키 없음, 경고 없음."""
    assert response.status_code == 503, response.text
    assert str(response.json()["type"]).endswith("directory-unavailable")
    assert "set-cookie" not in response.headers


async def given_bind_password_sealed_with_another_key(api: Api) -> None:
    """저장된 바인드 비밀번호가 다른 암호화 키로 봉인된 것이 되었다(키 변경·분실 상황).

    설정된 키로는 풀 수 없다. 공개 API로는 만들 수 없어 DB의 암호문을 직접 바꾼다.
    """
    from cryptography.fernet import Fernet  # noqa: PLC0415

    from tests.factories_auth import BIND_PASSWORD  # noqa: PLC0415
    from tests.functional.steps.login_db import sql_rows  # noqa: PLC0415
    from tests.support.crypto_keys import OTHER_FERNET_KEY  # noqa: PLC0415

    foreign = Fernet(OTHER_FERNET_KEY.encode()).encrypt(BIND_PASSWORD.encode()).decode()
    await sql_rows(
        api, "update directory_settings set bind_password_encrypted = :token", token=foreign
    )
