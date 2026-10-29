"""head 스키마에 원시 SQL로 directory_settings·user_password_hashes 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_SETTINGS = (
    "insert into directory_settings (id, revision, host, port, security, bind_account,"
    " bind_password_encrypted, base_dn, user_filter, connect_timeout_seconds, updated_at)"
    " values (:id, :revision, :host, :port, :security, :bind_account, :bind_password_encrypted,"
    " :base_dn, :user_filter, :connect_timeout_seconds, now())"
)
INSERT_HASH = (
    "insert into user_password_hashes (user_id, password_hash, updated_at)"
    " values (:user_id, :password_hash, now())"
)


async def insert_settings(session: AsyncSession, **overrides: Any) -> None:  # noqa: ANN401
    """설정 한 행. 기본값은 모든 제약을 통과한다."""
    values: dict[str, Any] = {
        "id": 1,
        "revision": 1,
        "host": "dc1.corp.test",
        "port": 636,
        "security": "ssl",
        "bind_account": "cn=svc,ou=services,dc=corp,dc=test",
        "bind_password_encrypted": "gAAAAA-sealed-token",
        "base_dn": "dc=corp,dc=test",
        "user_filter": "(sAMAccountName={login_id})",
        "connect_timeout_seconds": 5,
    }
    await session.execute(text(INSERT_SETTINGS), {**values, **overrides})


async def insert_password_hash(session: AsyncSession, user_id: int, **overrides: Any) -> None:  # noqa: ANN401
    values: dict[str, Any] = {
        "user_id": user_id,
        "password_hash": "scrypt$ln=14,r=8,p=1$c2FsdA$aGFzaA",
    }
    await session.execute(text(INSERT_HASH), {**values, **overrides})
