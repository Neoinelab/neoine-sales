"""Composition Root: Port와 구현체를 연결하고 유스케이스를 만들어 준다(UseCaseProvider 구현)."""

from datetime import timedelta
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.application.auth.authenticate import Authenticate
from app.application.auth.begin_login import BeginLogin
from app.application.auth.complete_login import CompleteLogin
from app.application.auth.dev_login import DevLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.login_state import LoginStateCodec
from app.application.auth.logout import Logout
from app.application.auth.role_mapping import RoleMapper
from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.get_customer import GetCustomer
from app.application.customer.list_customers import ListCustomers
from app.application.customer.register_customer import RegisterCustomer
from app.application.customer.update_customer import UpdateCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.get_deal_by_code import GetDealByCode
from app.application.deal.get_pipeline import GetDealPipeline
from app.application.deal.list_deals import ListDeals
from app.application.deal.list_stage_changes import ListDealStageChanges
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.search_deal_actions import SearchDealActions
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.application.partner.delete_partner import DeletePartner
from app.application.partner.get_partner import GetPartner
from app.application.partner.list_partners import ListPartners
from app.application.partner.register_partner import RegisterPartner
from app.application.partner.update_partner import UpdatePartner
from app.infra.auth.oidc import OidcConfig, OidcIdentityProvider
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from app.infra.system_clock import SystemClock

if TYPE_CHECKING:
    from app.config.base import Settings


def _oidc_config(settings: Settings) -> OidcConfig:
    secret = settings.oidc_client_secret
    if not (settings.oidc_issuer and settings.oidc_client_id and secret):
        raise RuntimeError("OIDC가 설정되지 않았습니다")
    if not settings.oidc_redirect_uri:
        raise RuntimeError("OIDC가 설정되지 않았습니다")
    return OidcConfig(
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        client_secret=secret.get_secret_value(),
        redirect_uri=settings.oidc_redirect_uri,
        scopes=settings.oidc_scopes,
        groups_claim=settings.oidc_groups_claim,
    )


class Container:
    def __init__(self, settings: Settings) -> None:
        self._engine: AsyncEngine = create_async_engine(
            str(settings.database_url),
            pool_size=settings.db_pool_size,
            echo=settings.db_echo,
            pool_pre_ping=True,
        )
        sessions = async_sessionmaker(self._engine, expire_on_commit=False)
        self._uow = sql_unit_of_work_factory(sessions)
        self._clock = SystemClock()
        self._http: httpx.AsyncClient | None = None
        self._idp: OidcIdentityProvider | None = None
        if settings.oidc_enabled:
            self._http = httpx.AsyncClient(timeout=10.0)
            self._idp = OidcIdentityProvider(_oidc_config(settings), self._http)
        self._login_state = LoginStateCodec(settings.jwt_secret.get_secret_value(), self._clock)
        self._roles = RoleMapper(settings.oidc_admin_groups, settings.oidc_sales_groups)
        self._issue_session = IssueSession(
            self._uow, self._clock, timedelta(hours=settings.session_ttl_hours)
        )

    async def check_ready(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("select 1"))

    async def dispose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
        await self._engine.dispose()

    def begin_login(self) -> BeginLogin:
        return BeginLogin(self._require_idp(), self._login_state)

    def complete_login(self) -> CompleteLogin:
        return CompleteLogin(
            self._require_idp(), self._login_state, self._roles, self._issue_session
        )

    def dev_login(self) -> DevLogin:
        return DevLogin(self._issue_session)

    def authenticate(self) -> Authenticate:
        return Authenticate(self._uow, self._clock)

    def logout(self) -> Logout:
        return Logout(self._uow, self._clock)

    def _require_idp(self) -> OidcIdentityProvider:
        if (
            self._idp is None
        ):  # 웹 계층이 oidc_enabled를 먼저 확인하므로 정상 흐름에서는 오지 않는다
            raise RuntimeError("OIDC가 설정되지 않았습니다")
        return self._idp

    def register_customer(self) -> RegisterCustomer:
        return RegisterCustomer(self._uow, self._clock)

    def get_customer(self) -> GetCustomer:
        return GetCustomer(self._uow)

    def list_customers(self) -> ListCustomers:
        return ListCustomers(self._uow)

    def update_customer(self) -> UpdateCustomer:
        return UpdateCustomer(self._uow, self._clock)

    def delete_customer(self) -> DeleteCustomer:
        return DeleteCustomer(self._uow, self._clock)

    def register_partner(self) -> RegisterPartner:
        return RegisterPartner(self._uow, self._clock)

    def get_partner(self) -> GetPartner:
        return GetPartner(self._uow)

    def list_partners(self) -> ListPartners:
        return ListPartners(self._uow)

    def update_partner(self) -> UpdatePartner:
        return UpdatePartner(self._uow, self._clock)

    def delete_partner(self) -> DeletePartner:
        return DeletePartner(self._uow, self._clock)

    def register_deal(self) -> RegisterDeal:
        return RegisterDeal(self._uow, self._clock)

    def get_deal(self) -> GetDeal:
        return GetDeal(self._uow)

    def get_deal_by_code(self) -> GetDealByCode:
        return GetDealByCode(self._uow)

    def list_deals(self) -> ListDeals:
        return ListDeals(self._uow)

    def update_deal(self) -> UpdateDeal:
        return UpdateDeal(self._uow, self._clock)

    def delete_deal(self) -> DeleteDeal:
        return DeleteDeal(self._uow, self._clock)

    def change_deal_stage(self) -> ChangeDealStage:
        return ChangeDealStage(self._uow, self._clock)

    def list_deal_stage_changes(self) -> ListDealStageChanges:
        return ListDealStageChanges(self._uow)

    def get_deal_pipeline(self) -> GetDealPipeline:
        return GetDealPipeline(self._uow)

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._uow, self._clock)

    def get_deal_action(self) -> GetDealAction:
        return GetDealAction(self._uow)

    def search_deal_actions(self) -> SearchDealActions:
        return SearchDealActions(self._uow)

    def update_deal_action(self) -> UpdateDealAction:
        return UpdateDealAction(self._uow, self._clock)

    def delete_deal_action(self) -> DeleteDealAction:
        return DeleteDealAction(self._uow, self._clock)
