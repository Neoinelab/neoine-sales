"""DealRepository.deletion_impact의 첨부 건수: Fake와 SQL에 같은 기대값."""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealDeletionImpact
from tests.factories import make_deal_code
from tests.factories_attachment import make_attachment

if TYPE_CHECKING:
    from tests.unit.repositories.attachment_case import AttachmentCase

DEAL = make_deal_code("A001")
OTHER = make_deal_code("A002")


async def test_a_deal_without_attachments_counts_zero(attachment_case: AttachmentCase) -> None:
    """첨부가 없는 Deal의 삭제 영향 첨부 건수는 0이다.

    테스트 코드: AT-040
    """
    # given: 첨부가 없는 Deal
    await attachment_case.ensure_deal(DEAL)

    # when: 삭제 영향을 읽는다
    impact = await attachment_case.deals.deletion_impact(DEAL)

    # then: 모든 건수가 0이다
    assert impact == DealDeletionImpact(
        history_count=0, action_count=0, attachment_count=0, license_contract_count=0
    )


async def test_each_attachment_of_the_deal_is_counted_once(attachment_case: AttachmentCase) -> None:
    """Deal의 첨부는 하나씩 한 번 센다."""
    # given: 첨부 세 건이 있는 Deal
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        await attachment_case.add(make_attachment(deal_code=DEAL, name=name))

    # when: 삭제 영향을 읽는다
    impact = await attachment_case.deals.deletion_impact(DEAL)

    # then: 첨부 건수가 3이다
    assert impact.attachment_count == 3


async def test_other_deals_attachments_are_not_counted(attachment_case: AttachmentCase) -> None:
    """다른 Deal의 첨부는 세지 않는다.

    테스트 코드: AT-040
    """
    # given: 한 Deal에 1건, 다른 Deal에 2건
    await attachment_case.add(make_attachment(deal_code=DEAL, name="a.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER, name="b.pdf"))
    await attachment_case.add(make_attachment(deal_code=OTHER, name="c.pdf"))

    # when: 삭제 영향을 읽는다
    impact = (await attachment_case.deals.deletion_impact(DEAL)).attachment_count

    # then: 첨부 건수가 1이다
    assert impact == 1
    assert (await attachment_case.deals.deletion_impact(OTHER)).attachment_count == 2


async def test_the_count_is_what_a_delete_would_remove(attachment_case: AttachmentCase) -> None:
    """센 건수는 Deal 삭제가 실제로 지우는 건수와 같다."""
    # given: 첨부 1건과 그때의 삭제 영향
    attachment = make_attachment(deal_code=DEAL)
    await attachment_case.add(attachment)
    impact = await attachment_case.deals.deletion_impact(DEAL)

    # when: Deal을 삭제한다
    await attachment_case.deals.delete(DEAL)

    # then: 센 건수는 1이고 삭제 뒤 첨부가 없다
    assert impact.attachment_count == 1
    assert await attachment_case.names(DEAL) == []


async def test_a_deleted_attachment_is_no_longer_counted(attachment_case: AttachmentCase) -> None:
    """지운 첨부는 더 이상 세지 않는다.

    테스트 코드: AT-040
    """
    # given: 첨부 1건
    attachment = make_attachment(deal_code=DEAL)
    await attachment_case.add(attachment)

    # when: 첨부를 지운다
    await attachment_case.repository.delete(attachment.id)

    # then: 첨부 건수가 0이다
    assert (await attachment_case.deals.deletion_impact(DEAL)).attachment_count == 0
