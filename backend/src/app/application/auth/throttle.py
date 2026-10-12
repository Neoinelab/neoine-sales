import hashlib
import hmac
from typing import TYPE_CHECKING

from app.domain.auth.errors import TooManyAttemptsError
from app.domain.auth.login_failure import FailureCounter

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.auth.credentials import LoginId
    from app.domain.auth.login_failure import FailurePolicy

TOO_MANY_ATTEMPTS = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"


class LoginThrottle:
    """아이디별·IP별 로그인 실패를 DB에 세어 제한한다. 키는 비밀 기반 HMAC이라 원문이 남지 않는다.

    각 메서드는 자기 UoW를 열어 커밋한다(로그인 예외 뒤에도 실패 기록이 남아야 한다).
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        *,
        secret: str,
        account_policy: FailurePolicy,
        ip_policy: FailurePolicy,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._secret = secret.encode()
        self._account_policy = account_policy
        self._ip_policy = ip_policy

    def _key(self, text: str) -> str:
        return hmac.new(self._secret, text.encode(), hashlib.sha256).hexdigest()

    def _keys(self, login_id: LoginId, client_ip: str) -> tuple[str, str]:
        return self._key(f"acct:{login_id.value}"), self._key(f"ip:{client_ip}")

    def _counters(self, login_id: LoginId, client_ip: str) -> tuple[tuple[str, FailurePolicy], ...]:
        account_key, ip_key = self._keys(login_id, client_ip)
        return ((account_key, self._account_policy), (ip_key, self._ip_policy))

    async def ensure_allowed(self, login_id: LoginId, client_ip: str) -> None:
        """잠금을 확인하고 계정·IP 시도를 1회씩 선점한다(AD 호출 전, 같은 트랜잭션).

        선점은 실패로 센 것과 같다. 자격증명 실패는 그대로 두고, 성공·연결 장애는
        `succeeded`·`release`로 되돌린다. 병렬 요청도 한도를 넘어 AD까지 가지 못한다.
        """
        now = self._clock.now()
        async with self._uow_factory() as uow:
            for key, policy in self._counters(login_id, client_ip):
                counter = await uow.login_failures.get_for_update(key)
                counter = counter or FailureCounter(key, 0, now)
                if counter.is_locked(now):
                    raise TooManyAttemptsError(TOO_MANY_ATTEMPTS)
                await uow.login_failures.save(counter.record_failure(now, policy))
            await uow.commit()

    async def succeeded(self, login_id: LoginId, client_ip: str) -> None:
        """로그인 성공: 계정 카운터를 지우고 IP 선점을 되돌린다."""
        account_key, ip_key = self._keys(login_id, client_ip)
        async with self._uow_factory() as uow:
            await uow.login_failures.delete(account_key)
            await self._give_back(uow, ip_key, self._ip_policy)
            await uow.commit()

    async def release(self, login_id: LoginId, client_ip: str) -> None:
        """실패로 세지 않을 시도(연결 장애, 설정 확인 성공)의 선점을 계정·IP에서 되돌린다."""
        async with self._uow_factory() as uow:
            for key, policy in self._counters(login_id, client_ip):
                await self._give_back(uow, key, policy)
            await uow.commit()

    @staticmethod
    async def _give_back(uow: UnitOfWork, key: str, policy: FailurePolicy) -> None:
        counter = await uow.login_failures.get_for_update(key)
        if counter is None:
            return
        released = counter.release(policy)
        if released.failures == 0:
            await uow.login_failures.delete(key)
        else:
            await uow.login_failures.save(released)

    async def record_failure(self, login_id: LoginId, client_ip: str) -> None:
        now = self._clock.now()
        account_key, ip_key = self._keys(login_id, client_ip)
        async with self._uow_factory() as uow:
            for key, policy in ((account_key, self._account_policy), (ip_key, self._ip_policy)):
                counter = await uow.login_failures.get_for_update(key)
                counter = counter or FailureCounter(key, 0, now)
                await uow.login_failures.save(counter.record_failure(now, policy))
            await uow.commit()

    async def clear(self, login_id: LoginId) -> None:
        async with self._uow_factory() as uow:
            await uow.login_failures.delete(self._key(f"acct:{login_id.value}"))
            await uow.commit()
