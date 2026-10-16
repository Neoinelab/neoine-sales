"""연락처(고객·파트너 통합). 회사/담당자 선택용 조회는 로그인 사용자, 목록과 변경은 admin 전용."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.domain.contact.values import ContactId
from app.web.dependencies import Provider
from app.web.permissions import require_admin
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.contact import (
    ByCompanyParams,
    CompaniesParams,
    ContactCreateRequest,
    ContactResponse,
    ContactRowPage,
    ContactRowResponse,
    ContactSearchParams,
    ContactUpdateRequest,
    row_page,
)
from app.web.security import CurrentUser

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])
ADMIN = [Depends(require_admin)]
ADMIN_ERRORS: dict[int | str, dict[str, Any]] = {403: PROBLEM}


@router.get(
    "",
    response_model=ContactRowPage,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, 422: PROBLEM},
)
async def search_contacts(
    params: Annotated[ContactSearchParams, Query()], provider: Provider
) -> ContactRowPage:
    return row_page(await provider.search_contacts().execute(params.to_query()))


@router.get("/companies", response_model=list[str], responses={422: PROBLEM})
async def list_contact_companies(
    params: Annotated[CompaniesParams, Query()], provider: Provider
) -> list[str]:
    return await provider.list_contact_companies().execute(params.kind)


@router.get("/by-company", response_model=list[ContactRowResponse], responses={422: PROBLEM})
async def list_contacts_of_company(
    params: Annotated[ByCompanyParams, Query()], provider: Provider
) -> list[ContactRowResponse]:
    usages = await provider.list_contacts_of_company().execute(params.kind, params.company)
    return [ContactRowResponse.from_usage(u) for u in usages]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ContactResponse,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **WRITE_ERRORS},
)
async def register_contact(
    body: ContactCreateRequest, response: Response, provider: Provider
) -> ContactResponse:
    contact = await provider.register_contact().execute(body.to_input())
    response.headers["Location"] = f"{router.prefix}/{contact.id}"
    return ContactResponse.from_entity(contact)


@router.put(
    "/{contact_id}",
    response_model=ContactResponse,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **WRITE_ERRORS},
)
async def update_contact(
    contact_id: UUID, body: ContactUpdateRequest, user: CurrentUser, provider: Provider
) -> ContactResponse:
    contact = await provider.update_contact().execute(
        ContactId(contact_id), body.to_input(), user.user_id
    )
    return ContactResponse.from_entity(contact)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **READ_ERRORS, 409: PROBLEM},
)
async def delete_contact(contact_id: UUID, provider: Provider) -> None:
    await provider.delete_contact().execute(ContactId(contact_id))
