from typing import TYPE_CHECKING

from app.application.auth.mode import ensure_directory_mode
from app.application.directory.result import SUCCESS_MESSAGE, TestResult

__all__ = ["SUCCESS_MESSAGE", "TestDirectorySettings", "TestResult"]

if TYPE_CHECKING:
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettings


class TestDirectorySettings:
    __test__ = False

    def __init__(self, uow_factory: UnitOfWorkFactory, verify: VerifyDirectorySettings) -> None:
        self._uow_factory = uow_factory
        self._verify = verify

    async def execute(self, *, actor: Principal, settings: DirectorySettings) -> TestResult:
        async with self._uow_factory() as uow:
            await ensure_directory_mode(uow)
        return await self._verify.execute(settings, f"admin:{actor.user_id}")
