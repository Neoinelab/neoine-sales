from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from app.application.ports.customer_repository import CustomerRepository
    from app.application.ports.deal_action_repository import DealActionRepository
    from app.application.ports.deal_repository import DealRepository
    from app.application.ports.deal_stage_change_repository import DealStageChangeRepository
    from app.application.ports.directory_settings_repository import DirectorySettingsRepository
    from app.application.ports.login_failure_repository import LoginFailureRepository
    from app.application.ports.partner_repository import PartnerRepository
    from app.application.ports.session_repository import SessionRepository
    from app.application.ports.user_repository import UserRepository


class UnitOfWork(Protocol):
    """하나의 트랜잭션 경계. `async with`로 열고, commit한 변경만 남는다.

    - 블록 안에서는 repository를 통해 변경 사항을 볼 수 있다.
    - commit 없이 블록을 벗어나거나 예외가 나면 변경은 폐기된다(commit 이후의 변경도 폐기).
    """

    @property
    def customers(self) -> CustomerRepository: ...

    @property
    def partners(self) -> PartnerRepository: ...

    @property
    def deals(self) -> DealRepository: ...

    @property
    def deal_actions(self) -> DealActionRepository: ...

    @property
    def deal_stage_changes(self) -> DealStageChangeRepository: ...

    @property
    def sessions(self) -> SessionRepository: ...

    @property
    def users(self) -> UserRepository: ...

    @property
    def login_failures(self) -> LoginFailureRepository: ...

    @property
    def directory_settings(self) -> DirectorySettingsRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *exc: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


# 유스케이스는 요청마다 새 UoW(새 세션)를 쓰도록 UoW 자체가 아니라 팩토리를 주입받는다.
type UnitOfWorkFactory = Callable[[], UnitOfWork]
