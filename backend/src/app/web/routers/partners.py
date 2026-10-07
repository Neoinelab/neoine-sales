from uuid import UUID

from fastapi import APIRouter, Response, status

from app.domain.partner.value_objects import PartnerId
from app.web.dependencies import DEFAULT_LIMIT, Limit, Offset, Provider
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.partner import PartnerPage, PartnerRequest, PartnerResponse

router = APIRouter(prefix="/api/v1/partners", tags=["partners"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=PartnerResponse, responses=WRITE_ERRORS
)
async def register_partner(
    body: PartnerRequest, response: Response, provider: Provider
) -> PartnerResponse:
    partner = await provider.register_partner().execute(body.to_input())
    response.headers["Location"] = f"{router.prefix}/{partner.id}"
    return PartnerResponse.from_entity(partner)


@router.get("", response_model=PartnerPage, responses=READ_ERRORS)
async def list_partners(
    provider: Provider, offset: Offset = 0, limit: Limit = DEFAULT_LIMIT
) -> PartnerPage:
    partners = await provider.list_partners().execute(offset=offset, limit=limit)
    items = [PartnerResponse.from_entity(c) for c in partners]
    return PartnerPage(items=items, offset=offset, limit=limit)


@router.get("/{partner_id}", response_model=PartnerResponse, responses=READ_ERRORS)
async def get_partner(partner_id: UUID, provider: Provider) -> PartnerResponse:
    partner = await provider.get_partner().execute(PartnerId(partner_id))
    return PartnerResponse.from_entity(partner)


@router.put("/{partner_id}", response_model=PartnerResponse, responses=WRITE_ERRORS)
async def update_partner(
    partner_id: UUID, body: PartnerRequest, provider: Provider
) -> PartnerResponse:
    partner = await provider.update_partner().execute(PartnerId(partner_id), body.to_input())
    return PartnerResponse.from_entity(partner)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS)
async def delete_partner(partner_id: UUID, provider: Provider) -> None:
    await provider.delete_partner().execute(PartnerId(partner_id))
