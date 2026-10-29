"""AD 설정 테스트용 생성 도우미. 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다.

새 도메인 모듈(`SecurityMode`, `DirectoryConnection` 등)을 가져오므로 사용자·세션 테스트가 쓰는
`factories_auth`와 나눈다.
"""

from typing import Any

from app.domain.auth.credentials import Password
from app.domain.directory.settings import DirectoryConnection, DirectorySettings, SecurityMode
from tests.factories_auth import BIND_ACCOUNT, BIND_PASSWORD, USER_FILTER

DEFAULT_HOST = "dc1.corp.test"


def make_directory_connection(**overrides: object) -> DirectoryConnection:
    """비밀이 아닌 접속 정보. 기본은 SSL 636."""
    values: dict[str, Any] = {
        "host": DEFAULT_HOST,
        "port": 636,
        "security": SecurityMode.SSL,
        "bind_account": BIND_ACCOUNT,
        "user_filter": USER_FILTER,
        "connect_timeout_seconds": 5,
    }
    return DirectoryConnection(**{**values, **overrides})


def make_directory_settings(
    *,
    bind_password: str = BIND_PASSWORD,
    **overrides: Any,  # noqa: ANN401
) -> DirectorySettings:
    """접속 정보 + 평문 바인드 비밀번호. overrides는 접속 정보 필드를 바꾼다."""
    return DirectorySettings(
        connection=make_directory_connection(**overrides), bind_password=Password(bind_password)
    )
