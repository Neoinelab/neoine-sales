from typing import TYPE_CHECKING

import pytest

from tests.factories import NOW
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.support.user_ids import ACTOR_ID, CHANGER_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.storage_stack import StorageStack
    from tests.unit.application.action_env import ActionEnv
    from tests.unit.application.attachment_env import AttachmentEnv
    from tests.unit.application.deal_env import DealEnv
    from tests.unit.application.partner_meeting_env import MeetingEnv


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def seeded(uow: FakeUnitOfWork) -> FakeUnitOfWork:
    """마이그레이션 시드와 같은 기본 코드(Status 7·Forecast 6)와 기본 Label 23개가 있는 UoW."""
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415 - 도메인 모듈 지연 import

    seed_catalog(uow)
    return uow


@pytest.fixture
def uow_factory(uow: FakeUnitOfWork) -> UnitOfWorkFactory:
    """항상 같은 Fake를 돌려준다. 실제 구현은 호출할 때마다 새 UoW(새 세션)를 만든다."""
    return lambda: uow


@pytest.fixture
def suffix_source() -> FakeDealCodeSuffixSource:
    """Deal code suffix 대역: 호출마다 겹치지 않는 값(0001, 0002, ...)을 낸다. 충돌 시나리오는
    `FakeDealCodeSuffixSource("A7K2", "A7K2", ...)`로 직접 만든다."""
    return FakeDealCodeSuffixSource()


@pytest.fixture
async def env(  # noqa: PLR0913, PLR0917 - 유스케이스 환경이 모으는 fixture
    seeded: FakeUnitOfWork,
    default_users: None,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    suffix_source: FakeDealCodeSuffixSource,
    file_storage: FakeFileStorage,
) -> DealEnv:
    """Deal 유스케이스 환경: 기본 코드·Label 시드, 기본 Owner(재직 sales), Fake suffix 대역."""
    from tests.unit.application.deal_env import build_env  # noqa: PLC0415 - Deal 구현 지연 import

    return build_env(seeded, uow_factory, clock, suffix_source, file_storage)


@pytest.fixture
async def action_env(env: DealEnv) -> ActionEnv:
    """Action 유스케이스 환경(P2): Deal 하나, 기본 Action 유형 8개, 요청자(kim·park, boss, viewer).

    Action 이력의 변경자 표기(`get_refs`)가 풀리도록 요청자 사용자 행을 둔다. 준비용 commit은
    커밋 횟수 단언에 섞이지 않도록 0으로 되돌린다.
    """
    from tests.fakes.catalog_seed import seed_action_types  # noqa: PLC0415 - 도메인 지연 import
    from tests.unit.application.action_env import (  # noqa: PLC0415 - Action 구현 지연 import
        BOSS,
        KIM,
        PARK,
        VIEWER,
        build_action_env,
    )

    seed_action_types(env.uow)  # 마이그레이션이 넣는 기본 유형 8개
    async with env.uow_factory() as active:
        await ensure_users(active.users, KIM.user_id, PARK.user_id, BOSS.user_id, VIEWER.user_id)
        await active.commit()
    env.uow.commits = 0
    return build_action_env(env, await env.new_deal())


@pytest.fixture
async def attachment_env(env: DealEnv) -> AttachmentEnv:
    """첨부 유스케이스 환경(P2b R2): Deal 하나, 저장 위치, 요청자 사용자들.

    kim·park(sales), boss(admin), viewer(user)와 퇴사한 gone-sales·gone-admin·gone-viewer를 role대로
    둔다. 준비용 commit은 커밋 횟수 단언에 섞이지 않도록 0으로 되돌린다.
    """
    from tests.unit.application.attachment_env import (  # noqa: PLC0415 - 첨부 구현 지연 import
        build_attachment_env,
        prepare_users,
    )

    await prepare_users(env)
    return build_attachment_env(env, await env.new_deal())


@pytest.fixture
async def meeting_env(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> MeetingEnv:
    """파트너 Activity 유스케이스 환경: 요청자(kim·park sales, boss admin, viewer user)가 있는 UoW.

    Deal·파트너 연락처는 `meeting_env.deal(...)`로 둔다. 준비용 commit은 커밋 횟수 단언에 섞이지
    않도록 0으로 되돌린다.
    """
    from tests.unit.application.partner_meeting_env import (  # noqa: PLC0415 - 구현 지연 import
        build_meeting_env,
    )

    return await build_meeting_env(uow, uow_factory, clock)


@pytest.fixture
async def default_users(uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork) -> None:
    """팩토리 기본 Owner·활동자·변경자(OWNER_ID/ACTOR_ID/CHANGER_ID)를 재직 sales 사용자로 둔다.

    Deal·활동은 재직 사용자만 지정할 수 있으므로 해당 테스트 모듈은 이 fixture를 쓴다.
    준비용 commit은 커밋 횟수 단언(`uow.commits`)에 섞이지 않도록 0으로 되돌린다.
    """
    async with uow_factory() as active:
        await ensure_users(active.users, OWNER_ID, ACTOR_ID, CHANGER_ID)
        await active.commit()
    uow.commits = 0


@pytest.fixture
def directory() -> FakeDirectoryAuthenticator:
    """AD에 kim/pw-kim 계정이 있다(표시 이름·메일 포함)."""
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-kim", display_name="김영업", email="kim@corp.test")
    return fake


@pytest.fixture
def auth(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, directory: FakeDirectoryAuthenticator
) -> AuthStack:
    from tests.fakes.auth_stack import build_auth_stack  # noqa: PLC0415 - 지연 import

    return build_auth_stack(uow_factory, clock, directory)


@pytest.fixture
def storage(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> StorageStack:
    """저장 위치 유스케이스 5종과 FakeFileStorage(`storage.storage`)."""
    from tests.fakes.storage_stack import build_storage_stack  # noqa: PLC0415 - 지연 import

    return build_storage_stack(uow_factory, clock)


@pytest.fixture
def file_storage(storage: StorageStack) -> FakeFileStorage:
    """저장 위치 유스케이스가 쓰는 FakeFileStorage(디렉터리·파일 상태를 직접 본다)."""
    return storage.storage


@pytest.fixture
def admin(
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
) -> AdminStack:
    """사용자·AD 설정 관리 유스케이스. AD에는 관리자 root/pw-root 계정이 있다."""
    from tests.fakes.admin_stack import (  # noqa: PLC0415 - 지연 import
        ADMIN_LOGIN,
        ADMIN_PASSWORD,
        build_admin_stack,
    )

    directory.add_account(ADMIN_LOGIN, ADMIN_PASSWORD)
    return build_admin_stack(auth, uow_factory, clock)
