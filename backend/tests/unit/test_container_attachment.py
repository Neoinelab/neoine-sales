"""조립(Container)의 첨부 계약(P2b R2): 첨부 유스케이스 5종이 조립된다."""

from typing import TYPE_CHECKING

import pytest_asyncio
from app.application.attachment.delete_attachment import DeleteAttachment
from app.application.attachment.download_attachment import DownloadAttachment
from app.application.attachment.get_attachment import GetAttachment
from app.application.attachment.list_attachments import ListAttachments
from app.application.attachment.upload_attachment import UploadAttachment

from app.application.deal.delete_deal import DeleteDeal
from app.container import Container
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL))  # 엔진만 만들 뿐 DB에는 접속하지 않는다
    yield built
    await built.dispose()


async def test_container_builds_the_attachment_use_cases(container: Container) -> None:
    assert isinstance(container.list_attachments(), ListAttachments)
    assert isinstance(container.get_attachment(), GetAttachment)
    assert isinstance(container.upload_attachment(), UploadAttachment)
    assert isinstance(container.delete_attachment(), DeleteAttachment)
    assert isinstance(container.download_attachment(), DownloadAttachment)


async def test_container_still_builds_delete_deal_with_the_file_storage(
    container: Container,
) -> None:
    assert isinstance(container.delete_deal(), DeleteDeal)
