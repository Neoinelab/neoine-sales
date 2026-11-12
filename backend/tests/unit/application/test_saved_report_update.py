"""UpdateReport: 권한별 덮어쓰기, 404 숨김, revision 충돌, 공개 범위 변경 권한, 이름 검사 대상."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.update_report import UpdateReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import (
    DuplicateReportNameError,
    ReportEditConflictError,
    ReportNotFoundError,
    ReportVisibilityForbiddenError,
)
from app.domain.saved_report.values import ReportId
from tests.factories import NOW, later
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.ids import MISSING_ID
from tests.support.report_defs import col, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    ROOT,
    content_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def update(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> UpdateReport:
    clock.advance(600)  # 저장 시각(NOW)보다 뒤
    return UpdateReport(uow_factory, clock)


async def test_update_changes_content_and_sql_and_raises_revision_keeping_owner(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """덮어쓰면 내용·SQL이 바뀌고 revision이 오르며 만든 사람·생성 시각은 그대로다.

    테스트 코드: RS-016
    """
    # given: ALICE의 SIMPLE 리포트 "원본"(revision 1)
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    # when: 시간이 지난 뒤 이름·설명·정의를 바꿔 덮어쓴다
    result = await update.execute(
        report.id,
        content_input("수정본", description="새 설명", definition=definition),
        1,
        viewer(ALICE),
    )
    # then: 내용·SQL이 바뀌고 revision 2, 만든 사람·생성 시각은 그대로, 수정 시각은 덮어쓴 시각이다
    assert (result.name, result.description) == ("수정본", "새 설명")
    assert result.definition == definition
    assert result.generated_sql == RENDERED_SQL
    assert result.revision == 2
    assert result.owner_user_id == ALICE
    assert result.created_at == NOW
    assert result.updated_at == later(600)
    # then: 다시 읽어도 같은 값이다
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.definition) == ("수정본", 2, definition)
    assert uow.commits == 1


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_others_public_report_can_be_overwritten_and_editor_is_recorded(
    update: UpdateReport, uow: FakeUnitOfWork, role: Role
) -> None:
    """sales·user도 남의 공개 리포트를 덮어쓰고 최종 수정자가 된다.

    테스트 코드: RS-017
    """
    # given: ALICE의 공개 리포트
    report = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, report)
    # when: BOB이 공개 범위를 그대로 두고 revision 1로 덮어쓴다
    result = await update.execute(
        report.id, content_input("고침", visibility="public"), 1, viewer(BOB, role)
    )
    # then: 만든 사람은 ALICE, 최종 수정자는 BOB, revision 2다
    assert (result.owner_user_id, result.updated_by_user_id, result.revision) == (ALICE, BOB, 2)
    (saved,) = await stored(uow)
    assert saved.updated_by_user_id == BOB


async def test_admin_overwrites_others_private_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """admin은 남의 비공개 리포트도 덮어쓰고 만든 사람은 그대로, 최종 수정자는 admin이다.

    테스트 코드: RS-015
    """
    # given: ALICE의 비공개 리포트
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)
    # when: ROOT가 이름을 "admin이 고침"으로 덮어쓴다(공개 범위 유지)
    result = await update.execute(
        report.id, content_input("admin이 고침", visibility="private"), 1, viewer(ROOT, Role.ADMIN)
    )
    # then: 만든 사람은 ALICE, 최종 수정자는 ROOT다
    assert (result.name, result.owner_user_id, result.updated_by_user_id) == (
        "admin이 고침",
        ALICE,
        ROOT,
    )


async def test_update_of_others_private_is_not_found_for_sales_and_user(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트의 덮어쓰기는 없는 id와 같은 404이고 리포트는 그대로다.

    테스트 코드: RS-014
    """
    # given: ALICE의 비공개 리포트
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)
    # when·then: sales·user가 덮어쓰면(잘못된 revision이어도) 모두 404다
    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            await update.execute(report.id, content_input("침입"), 99, viewer(BOB, role))
    # then: 리포트는 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision) == ("비공개", 1)
    assert uow.commits == 0


async def test_update_of_a_missing_report_is_the_same_not_found(update: UpdateReport) -> None:
    """없는 id의 덮어쓰기는 숨긴 리포트와 같은 404 문구다.

    테스트 코드: RS-014
    """
    # when·then: 없는 id로 덮어쓰면 404 문구가 같다
    with pytest.raises(ReportNotFoundError) as caught:
        await update.execute(ReportId(MISSING_ID), content_input(), 1, viewer(ALICE))
    assert str(caught.value) == "리포트를 찾을 수 없습니다."


async def test_update_with_stale_revision_conflicts(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """저장된 것과 다른 revision(낮든 높든)으로 덮어쓰면 충돌이고 리포트는 그대로다.

    테스트 코드: RS-018
    """
    # given: revision 3인 리포트
    report = make_report("원본", owner=ALICE, revision=3)
    await seed(uow, report)
    # when·then: revision 2와 5로 덮어쓰면 충돌 문구의 오류다
    for revision in (2, 5):
        with pytest.raises(ReportEditConflictError) as caught:
            await update.execute(report.id, content_input("바뀜"), revision, viewer(ALICE))
        assert str(caught.value) == (
            "다른 사용자가 먼저 이 리포트를 저장했습니다."
            " 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."
        )
    # then: 저장 내용이 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.updated_at) == ("원본", 3, NOW)
    assert uow.commits == 0


async def test_two_sequential_updates_with_the_same_revision_conflict_on_the_second(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """같은 revision으로 차례로 두 번 덮어쓰면 첫 번째만 되고 두 번째는 충돌이다.

    테스트 코드: RS-018
    """
    # given: BOB이 revision 1로 덮어써 revision 2가 된 공개 리포트
    report = make_report("원본", owner=ALICE, visibility="public")
    await seed(uow, report)
    await update.execute(report.id, content_input("첫째"), 1, viewer(BOB))
    # when·then: ALICE가 같은 revision 1로 덮어쓰면 충돌이다
    with pytest.raises(ReportEditConflictError):
        await update.execute(report.id, content_input("둘째"), 1, viewer(ALICE))
    # then: BOB이 저장한 값 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.updated_by_user_id) == ("첫째", 2, BOB)


async def test_non_owner_changing_visibility_is_forbidden_and_changes_nothing(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """만든 사람이 아닌 편집자가 공개 범위를 바꾸면 403이고 리포트는 그대로다.

    테스트 코드: RS-019
    """
    # given: ALICE의 공개 리포트
    report = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, report)
    # when·then: BOB이 private으로 덮어쓰면 공개 범위 권한 오류다
    with pytest.raises(ReportVisibilityForbiddenError) as caught:
        await update.execute(report.id, content_input("바뀜", visibility="private"), 1, viewer(BOB))
    assert str(caught.value) == "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."
    # then: 리포트는 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.visibility.value, saved.revision) == ("공개", "public", 1)


async def test_non_owner_overwriting_with_the_same_visibility_is_allowed(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """만든 사람이 아니어도 저장된 값과 같은 공개 범위를 보내는 덮어쓰기는 된다.

    테스트 코드: RS-019
    """
    # given: ALICE의 공개 리포트
    report = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, report)
    # when: BOB이 public 그대로 덮어쓴다
    result = await update.execute(
        report.id, content_input("고침", visibility="public"), 1, viewer(BOB)
    )
    # then: 덮어써지고 공개 범위는 그대로다
    assert (result.name, result.visibility.value, result.revision) == ("고침", "public", 2)


@pytest.mark.parametrize(("editor", "role"), [(ALICE, Role.SALES), (ROOT, Role.ADMIN)])
async def test_owner_and_admin_change_visibility_to_private_and_others_cannot_see_it(
    update: UpdateReport, uow: FakeUnitOfWork, editor: int, role: Role
) -> None:
    """만든 사람과 admin은 공개 범위를 바꾸고, 비공개가 되면 남에게는 404다.

    테스트 코드: RS-020
    """
    # given: ALICE의 공개 리포트
    report = make_report("공개", owner=ALICE, visibility="public")
    await seed(uow, report)
    # when: 만든 사람 또는 admin이 private으로 덮어쓴다
    result = await update.execute(
        report.id,
        content_input("공개", visibility="private"),
        1,
        viewer(editor, role),  # type: ignore[arg-type]
    )
    # then: 공개 범위가 private이 되고 BOB이 다시 덮어쓰려 하면 404다
    assert result.visibility.value == "private"
    with pytest.raises(ReportNotFoundError):
        await update.execute(report.id, content_input("침입"), 2, viewer(BOB))


async def test_update_judges_not_found_then_content_then_visibility_forbidden(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """덮어쓰기는 404, 내용 422, 공개 범위 403 순서로 판정하고 리포트를 바꾸지 않는다.

    테스트 코드: RS-021
    """
    # given: ALICE의 비공개 리포트 P(revision 4)와 공개 리포트 R(revision 4)
    private = make_report("P", owner=ALICE, visibility="private", revision=4)
    public = make_report("R", owner=ALICE, visibility="public", revision=4)
    await seed(uow, private, public)
    # when·then: BOB이 P를 틀린 정의·revision 1로 덮어쓰면 404다
    with pytest.raises(ReportNotFoundError):
        await update.execute(
            private.id, content_input("P", definition=INVALID_DEFINITION), 1, viewer(BOB)
        )
    # when·then: R을 틀린 정의·private·revision 1로 덮어쓰면 422(정의)다
    with pytest.raises(ReportDefinitionError):
        await update.execute(
            public.id,
            content_input("R", visibility="private", definition=INVALID_DEFINITION),
            1,
            viewer(BOB),
        )
    # when·then: R을 맞는 정의·private·낡은 revision 1로 덮어쓰면 409가 아니라 403이다
    with pytest.raises(ReportVisibilityForbiddenError):
        await update.execute(public.id, content_input("R", visibility="private"), 1, viewer(BOB))
    # then: 어느 리포트도 바뀌지 않는다
    saved = {r.name: (r.revision, r.visibility.value) for r in await stored(uow)}
    assert saved == {"P": (4, "private"), "R": (4, "public")}
    assert uow.commits == 0


async def test_renaming_checks_names_of_every_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """다른 리포트의 이름으로 바꾸면 만든 사람·편집자와 무관하게 409이고 리포트는 그대로다.

    테스트 코드: RS-022
    """
    # given: ALICE의 "첫째"·"둘째", BOB의 공개 "bob"
    first = make_report("첫째", owner=ALICE)
    second = make_report("둘째", owner=ALICE)
    bobs = make_report("bob", owner=BOB, visibility="public")
    await seed(uow, first, second, bobs)
    # when·then: ALICE가 "둘째"를 "첫째"로 덮어쓰면 이름 중복이다
    with pytest.raises(DuplicateReportNameError):
        await update.execute(second.id, content_input("첫째"), 1, viewer(ALICE))
    # when·then: BOB이 "bob"을 "첫째"로 덮어써도 이름 중복이다
    with pytest.raises(DuplicateReportNameError):
        await update.execute(bobs.id, content_input("첫째"), 1, viewer(BOB))
    # then: "둘째"·"bob"은 그대로다
    saved = {r.id: (r.name, r.revision) for r in await stored(uow)}
    assert saved[second.id] == ("둘째", 1)
    assert saved[bobs.id] == ("bob", 1)


async def test_keeping_the_own_name_in_another_case_is_not_a_duplicate(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """자기 이름을 대소문자만 바꿔 덮어쓰는 것은 중복이 아니다.

    테스트 코드: RS-009
    """
    # given: ALICE의 "Pipeline"
    report = make_report("Pipeline", owner=ALICE)
    await seed(uow, report)
    # when: "PIPELINE"으로 덮어쓴다
    result = await update.execute(report.id, content_input("PIPELINE"), 1, viewer(ALICE))
    # then: 이름이 "PIPELINE"으로 바뀐다
    assert result.name == "PIPELINE"


async def test_invalid_definition_keeps_the_stored_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """규칙을 어긴 정의로 덮어쓰면 정의 오류이고 저장된 리포트는 그대로다.

    테스트 코드: RS-023
    """
    # given: ALICE의 리포트 "원본"
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    # when·then: 카탈로그에 없는 컬럼의 정의로 덮어쓰면 정의 오류다
    with pytest.raises(ReportDefinitionError):
        await update.execute(
            report.id, content_input(definition=INVALID_DEFINITION), 1, viewer(ALICE)
        )
    # then: 이름·revision·정의가 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.revision, saved.definition) == ("원본", 1, report.definition)
