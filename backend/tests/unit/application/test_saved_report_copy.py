"""CopyReport: 정의·배치는 원본 그대로, 만든 사람은 요청자, 이름 중복은 모든 리포트 기준."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.copy_report import CopyReport
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import DuplicateReportNameError, ReportNotFoundError
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.ids import MISSING_ID
from tests.support.layout_defs import make_layout
from tests.support.report_defs import col, cond, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    ROOT,
    meta_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def copy(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CopyReport:
    return CopyReport(uow_factory, clock)


async def test_copy_takes_definition_and_layout_from_source_and_owner_from_requester(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    """복제하면 정의·배치는 원본이고 만든 사람은 요청자, revision 1이다.

    테스트 코드: RS-028
    """
    # given: ALICE의 공개 원본(정의, 배치 BOTH_SIDE, revision 5)
    definition = raw([col("deal.vendor", group=True)], [cond("deal.name", "contains", "a")])
    both_side = make_layout("both", ("table", "chart"), "side_by_side")
    source = make_report(
        "원본",
        owner=ALICE,
        visibility="public",
        revision=5,
        definition=definition,
        layout=both_side,
    )
    await seed(uow, source)
    # when: BOB이 메타를 정해 복제한다
    result = await copy.execute(
        source.id, meta_input("원본 복사본", description="복제", visibility="private"), viewer(BOB)
    )
    # then: 새 리포트는 원본의 정의·배치에 요청자 소유, revision 1, 보낸 이름·설명·공개 범위다
    assert result.id != source.id
    assert result.definition == definition
    assert result.layout == both_side
    assert result.generated_sql == RENDERED_SQL
    assert (result.owner_user_id, result.updated_by_user_id, result.revision) == (BOB, BOB, 1)
    assert (result.name, result.description) == ("원본 복사본", "복제")
    assert result.visibility is ReportVisibility.PRIVATE
    assert (result.created_at, result.updated_at) == (NOW, NOW)
    assert uow.commits == 1


async def test_copy_leaves_the_source_unchanged(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    """복제해도 원본의 이름·revision·만든 사람은 그대로다.

    테스트 코드: RS-028
    """
    # given: revision 5인 원본
    source = make_report("원본", owner=ALICE, revision=5)
    await seed(uow, source)
    # when: 복제한다
    await copy.execute(source.id, meta_input("복사"), viewer(ALICE))
    # then: 원본은 이전과 같고 리포트가 둘이 된다
    saved = {r.id: r for r in await stored(uow)}
    assert len(saved) == 2
    assert (saved[source.id].name, saved[source.id].revision) == ("원본", 5)
    assert saved[source.id].owner_user_id == ALICE


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_can_copy_a_public_report(
    copy: CopyReport, uow: FakeUnitOfWork, role: Role
) -> None:
    """모든 역할이 남의 공개 리포트를 복제하고 설명을 생략하면 빈 문자열이다.

    테스트 코드: RS-029
    """
    # given: ALICE의 공개 리포트
    source = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, source)
    # when: 역할별 요청자가 설명 없이 복제한다
    result = await copy.execute(source.id, meta_input("복사"), viewer(BOB, role))
    # then: 요청자의 새 리포트이고 설명은 빈 문자열이다
    assert result.owner_user_id == BOB
    assert result.description == ""


async def test_admin_can_copy_others_private_report(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    """admin은 남의 비공개 리포트도 복제한다.

    테스트 코드: RS-029, RS-015
    """
    # given: ALICE의 비공개 리포트
    source = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, source)
    # when: ROOT가 복제한다
    result = await copy.execute(source.id, meta_input("복사"), viewer(ROOT, Role.ADMIN))
    # then: ROOT의 새 리포트가 생긴다
    assert result.owner_user_id == ROOT
    assert len(await stored(uow)) == 2


async def test_copy_name_must_differ_from_every_report(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    """복제 이름이 남의 비공개 리포트를 포함한 어떤 리포트와 겹쳐도 409이고 새 리포트가 없다.

    테스트 코드: RS-030
    """
    # given: ALICE의 공개 "원본", BOB의 "내 리포트", ALICE의 비공개 "숨은 이름"
    source = make_report("원본", owner=ALICE, visibility="public")
    await seed(
        uow,
        source,
        make_report("내 리포트", owner=BOB),
        make_report("숨은 이름", owner=ALICE, visibility="private"),
    )
    # when·then: BOB이 "내 리포트"와 "숨은 이름"으로 복제하면 모두 이름 중복이다
    for name in ("내 리포트", "숨은 이름"):
        with pytest.raises(DuplicateReportNameError):
            await copy.execute(source.id, meta_input(name), viewer(BOB, Role.USER))
    # then: 새 리포트가 없다
    assert len(await stored(uow)) == 3


async def test_copy_of_hidden_or_missing_report_is_not_found(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트와 없는 id의 복제는 같은 404이고 리포트가 늘지 않는다.

    테스트 코드: RS-014
    """
    # given: ALICE의 비공개 리포트
    hidden = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, hidden)
    # when·then: BOB이 비공개 리포트와 없는 id를 복제하면 둘 다 404다
    with pytest.raises(ReportNotFoundError):
        await copy.execute(hidden.id, meta_input(), viewer(BOB))
    with pytest.raises(ReportNotFoundError):
        await copy.execute(ReportId(MISSING_ID), meta_input(), viewer(BOB))
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


async def test_copy_of_a_source_that_no_longer_fits_the_catalog_is_invalid_report(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    """원본 정의가 지금 규칙과 맞지 않으면 복제는 정의 오류이고 아무것도 생기지 않는다.

    테스트 코드: RS-031
    """
    # given: 지금 카탈로그에 없는 필드를 쓰는 원본
    source = make_report("낡은 정의", owner=ALICE, definition=INVALID_DEFINITION)
    await seed(uow, source)
    # when·then: 복제하면 정의 오류다
    with pytest.raises(ReportDefinitionError):
        await copy.execute(source.id, meta_input("복사"), viewer(ALICE))
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


async def test_copy_with_blank_name_is_rejected_and_nothing_is_saved(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    """복제 메타가 틀리면(빈 이름) 값 오류이고 아무것도 생기지 않는다.

    테스트 코드: RS-031
    """
    # given: 정상 원본
    source = make_report("원본", owner=ALICE)
    await seed(uow, source)
    # when·then: 빈 이름으로 복제하면 이름 문구의 값 오류다
    with pytest.raises(InvalidValueError) as caught:
        await copy.execute(source.id, meta_input(""), viewer(ALICE))
    assert str(caught.value) == "리포트 이름을 입력하세요."
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


@pytest.mark.parametrize(("name", "visibility"), [("a" * 101, "public"), ("ok", "shared")])
async def test_invalid_copy_meta_is_rejected_and_nothing_is_saved(
    copy: CopyReport, uow: FakeUnitOfWork, name: str, visibility: str
) -> None:
    """긴 이름·알 수 없는 공개 범위로 복제하면 값 오류이고 아무것도 생기지 않는다."""
    # given: 정상 원본
    source = make_report("원본", owner=ALICE)
    await seed(uow, source)
    # when·then: 잘못된 메타로 복제하면 값 오류다
    with pytest.raises(InvalidValueError):
        await copy.execute(source.id, meta_input(name, visibility=visibility), viewer(ALICE))
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1
