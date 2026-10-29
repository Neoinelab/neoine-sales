from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.auth.throttle import LoginThrottle
    from app.application.ports.clock import Clock
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class AuthDeps:
    """로그인·최초 admin 설정이 함께 쓰는 의존성 묶음(생성자 인자 수를 줄인다)."""

    uow_factory: UnitOfWorkFactory
    clock: Clock
    directory: DirectoryAuthenticator
    throttle: LoginThrottle
    cipher: SecretCipher
    hasher: PasswordHasher
