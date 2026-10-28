"""ReportRepository(저장 리포트) 계약(AC1·3·4·5·7·9·11): Fake와 SQL 구현에 같은 테스트.

SQL 구현은 실제 PostgreSQL이다.

이름은 모든 리포트 사이에서 고유하다(테스트마다 롤백되는 세션이라 이름이 겹치지 않는다).
목록은 `mine`으로 자기 행만 비교한다.
정렬 계약: `updated_at` 내림차순, 동률은 id 내림차순.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.saved_report.errors import DuplicateReportNameError, ReportNotFoundError
from app.domain.saved_report.values import ReportId, ReportListScope, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_content, make_report
from tests.support.ids import new_id
from tests.support.report_defs import col, cond, raw
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.saved_report_case import SavedReportCase

ALICE = uid("contract-alice")
BOB = uid("contract-bob")
CAROL = uid("contract-carol")


def _scope(viewer: int, *, see_all: bool = False) -> ReportListScope:
    return ReportListScope(viewer_id=viewer, see_all=see_all)  # type: ignore[arg-type]


async def test_add_and_get_round_trip_keeps_definition_json(
    saved_report_case: SavedReportCase,
) -> None:
    definition = raw(
        [
            col("deal.vendor", group=True, label="벤더 이름"),
            col("deal.amount", aggregate="sum", format="krw_million", sort="desc"),
        ],
        [
            cond("deal.status", "in", ["prospecting", "introduction"]),
            cond("deal.amount", "between", [1000, 50000]),
            cond("deal.expected_close", "relative", {"period": "last_n_days", "days": 7}),
            cond("deal.name", "is_empty", None),
            cond("deal.vendor", "in", [1, 2]),
        ],
        combine="or",
        row_limit=10000,
    )
    report = make_report(
        "한글 이름 리포트",
        owner=ALICE,
        description="설명 줄1\n줄2",
        visibility="private",
        definition=definition,
        generated_sql="SELECT 1 -- 한글",
        revision=1,
    )
    await saved_report_case.add(report)

    stored = await saved_report_case.reports.get(report.id)

    assert stored == report
    assert stored.name == "한글 이름 리포트"
    assert stored.description == "설명 줄1\n줄2"
    assert stored.visibility is ReportVisibility.PRIVATE
    assert stored.definition == definition
    assert stored.generated_sql == "SELECT 1 -- 한글"
    assert (stored.owner_user_id, stored.updated_by_user_id) == (ALICE, ALICE)
    assert stored.revision == 1
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_empty_description_and_public_visibility_round_trip(
    saved_report_case: SavedReportCase,
) -> None:
    report = make_report("빈 설명", owner=ALICE, description="", visibility="public")
    await saved_report_case.add(report)

    stored = await saved_report_case.reports.get(report.id)

    assert (stored.description, stored.visibility) == ("", ReportVisibility.PUBLIC)


async def test_get_missing_report_raises_not_found(saved_report_case: SavedReportCase) -> None:
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(ReportId(new_id()))


async def test_get_for_update_returns_the_same_report(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("잠금", owner=ALICE))

    locked = await saved_report_case.reports.get(report.id, for_update=True)

    assert locked.name == "잠금"


async def test_name_is_unique_ignoring_case_for_the_same_owner(
    saved_report_case: SavedReportCase,
) -> None:
    await saved_report_case.add(make_report("Sales Report", owner=ALICE))

    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.add(make_report("sales report", owner=ALICE))


async def test_name_is_unique_ignoring_case_across_owners_and_visibility(
    saved_report_case: SavedReportCase,
) -> None:
    await saved_report_case.add(make_report("Team Report", owner=ALICE, visibility="private"))

    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.add(make_report("TEAM REPORT", owner=BOB, visibility="public"))


async def test_update_to_another_reports_name_of_the_same_owner_raises_duplicate(
    saved_report_case: SavedReportCase,
) -> None:
    await saved_report_case.add(make_report("첫째", owner=ALICE))
    second = await saved_report_case.add(make_report("둘째", owner=ALICE))
    second.overwrite(
        make_content("첫째"), editor=ALICE, role=Role.SALES, expected_revision=1, now=later(1)
    )

    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.reports.update(second)


async def test_update_to_the_name_of_another_owners_report_raises_duplicate(
    saved_report_case: SavedReportCase,
) -> None:
    await saved_report_case.add(make_report("공통 이름", owner=ALICE))
    mine = await saved_report_case.add(make_report("다른 이름", owner=BOB))
    mine.overwrite(
        make_content("공통 이름"), editor=BOB, role=Role.SALES, expected_revision=1, now=later(1)
    )

    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.reports.update(mine)


async def test_renaming_a_report_to_its_own_name_in_another_case_is_stored(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("sales", owner=ALICE))
    report.overwrite(
        make_content("SALES"), editor=ALICE, role=Role.SALES, expected_revision=1, now=later(1)
    )

    await saved_report_case.reports.update(report)

    assert (await saved_report_case.reports.get(report.id)).name == "SALES"


async def test_list_filters_by_scope_and_orders_by_updated_at_then_id(
    saved_report_case: SavedReportCase,
) -> None:
    mine_private = make_report("내 비공개", owner=ALICE, visibility="private", updated_at=later(10))
    mine_public = make_report("내 공개", owner=ALICE, visibility="public", updated_at=later(30))
    bobs_public = make_report("밥 공개", owner=BOB, visibility="public", updated_at=later(20))
    bobs_private = make_report("밥 비공개", owner=BOB, visibility="private", updated_at=later(40))
    tie_low = make_report("동률 먼저", owner=CAROL, visibility="public", updated_at=later(20))
    tie_high = make_report("동률 나중", owner=CAROL, visibility="public", updated_at=later(20))
    assert tie_high.id > tie_low.id
    everything = [mine_private, mine_public, bobs_public, bobs_private, tie_low, tie_high]
    for report in everything:
        await saved_report_case.add(report)
    ids = {r.id for r in everything}

    for_alice = await saved_report_case.mine(_scope(ALICE), ids)
    for_admin = await saved_report_case.mine(_scope(ALICE, see_all=True), ids)

    # 수정 시각 내림차순, 같은 시각(20)은 id 내림차순(동률 나중 > 동률 먼저 > 밥 공개)
    assert [r.name for r in for_alice] == [
        "내 공개",
        "동률 나중",
        "동률 먼저",
        "밥 공개",
        "내 비공개",
    ]
    assert [r.name for r in for_admin] == [
        "밥 비공개",
        "내 공개",
        "동률 나중",
        "동률 먼저",
        "밥 공개",
        "내 비공개",
    ]


async def test_list_hides_others_private_reports_from_a_non_admin_scope(
    saved_report_case: SavedReportCase,
) -> None:
    hidden = await saved_report_case.add(make_report("숨김", owner=BOB, visibility="private"))

    assert await saved_report_case.mine(_scope(ALICE), {hidden.id}) == []
    assert [r.id for r in await saved_report_case.mine(_scope(BOB), {hidden.id})] == [hidden.id]


async def test_update_changes_all_editable_fields_and_keeps_owner_and_created_at(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(
        make_report("원본", owner=ALICE, visibility="public", description="옛")
    )
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    await saved_report_case.prepare(BOB)
    report.overwrite(
        make_content(
            "수정본",
            description="새 설명",
            visibility="public",
            definition=definition,
            generated_sql="SELECT edited",
        ),
        editor=BOB,
        role=Role.ADMIN,
        expected_revision=1,
        now=later(100),
    )

    await saved_report_case.reports.update(report)

    stored = await saved_report_case.reports.get(report.id)
    assert (stored.name, stored.description) == ("수정본", "새 설명")
    assert stored.definition == definition
    assert stored.generated_sql == "SELECT edited"
    assert stored.updated_by_user_id == BOB
    assert stored.revision == 2
    assert stored.updated_at == later(100)
    assert stored.owner_user_id == ALICE
    assert stored.created_at == NOW


async def test_update_stores_a_visibility_change(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("공개였음", owner=ALICE, visibility="public"))
    report.overwrite(
        make_content("공개였음", visibility="private"),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(report)

    assert (await saved_report_case.reports.get(report.id)).visibility is ReportVisibility.PRIVATE


async def test_delete_removes_only_that_report(saved_report_case: SavedReportCase) -> None:
    gone = await saved_report_case.add(make_report("삭제", owner=ALICE))
    kept = await saved_report_case.add(make_report("유지", owner=ALICE))

    await saved_report_case.reports.delete(gone.id)

    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(gone.id)
    assert (await saved_report_case.reports.get(kept.id)).name == "유지"


async def test_a_deleted_reports_name_can_be_used_again(
    saved_report_case: SavedReportCase,
) -> None:
    gone = await saved_report_case.add(make_report("재사용", owner=ALICE))
    await saved_report_case.reports.delete(gone.id)

    await saved_report_case.add(make_report("재사용", owner=ALICE))


async def test_missing_id_raises_not_found_for_get_update_and_delete(
    saved_report_case: SavedReportCase,
) -> None:
    ghost = make_report("유령", owner=ALICE)
    await saved_report_case.prepare(ALICE)

    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(ghost.id)
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.update(ghost)
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.delete(ghost.id)


async def test_resigned_owner_keeps_the_report(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("퇴사자 것", owner=CAROL, visibility="public"))

    await saved_report_case.resign(CAROL, later(60))

    stored = await saved_report_case.reports.get(report.id)
    assert (stored.name, stored.owner_user_id) == ("퇴사자 것", CAROL)
    assert [r.id for r in await saved_report_case.mine(_scope(ALICE), {report.id})] == [report.id]


# ---- 깨진 저장 정의 (계획 11.2): 읽기 실패를 삼키지 않고 깨짐 상태 엔티티로 돌려준다 ----

BROKEN_JSON = ["{}", '{"columns": "oops"}', '{"columns": [{"field": 5}]}']


@pytest.mark.parametrize("raw_json", BROKEN_JSON)
async def test_get_returns_a_broken_report_when_the_stored_definition_is_unreadable(
    saved_report_case: SavedReportCase, raw_json: str
) -> None:
    report = await saved_report_case.add(make_report("깨짐", owner=ALICE, description="설명"))
    await saved_report_case.corrupt_definition(report, raw_json)

    stored = await saved_report_case.reports.get(report.id)

    assert stored.definition is None
    assert (stored.name, stored.description, stored.revision) == ("깨짐", "설명", 1)
    assert stored.entities() == ()


async def test_list_does_not_fail_on_a_broken_report_and_keeps_the_healthy_ones(
    saved_report_case: SavedReportCase,
) -> None:
    healthy = await saved_report_case.add(make_report("정상", owner=ALICE, updated_at=later(10)))
    broken = await saved_report_case.add(make_report("깨짐", owner=ALICE, updated_at=later(20)))
    await saved_report_case.corrupt_definition(broken, '{"columns": "oops"}')

    listed = await saved_report_case.mine(_scope(ALICE), {healthy.id, broken.id})

    assert [(r.name, r.definition is None) for r in listed] == [("깨짐", True), ("정상", False)]


async def test_update_with_a_new_definition_repairs_a_broken_report(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("복구 대상", owner=ALICE))
    await saved_report_case.corrupt_definition(report, "{}")
    broken = await saved_report_case.reports.get(report.id)
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    broken.overwrite(
        make_content("복구 대상", definition=definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(broken)

    stored = await saved_report_case.reports.get(report.id)
    assert stored.definition == definition
    assert stored.revision == 2


async def test_delete_removes_a_broken_report(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("깨짐 삭제", owner=ALICE))
    await saved_report_case.corrupt_definition(report, "{}")

    await saved_report_case.reports.delete(report.id)

    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(report.id)
