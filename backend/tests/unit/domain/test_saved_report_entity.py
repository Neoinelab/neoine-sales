"""Report 엔티티: 만들기, 덮어쓰기, 판정 순서(404 -> 403 -> 409), 복제.

판정 순서의 첫째는 항상 "볼 수 있는가"다. 볼 수 없는 리포트는 존재 자체를 숨긴다.
"""

import pytest

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.entities import Report
from app.domain.saved_report.errors import (
    DuplicateReportNameError,
    ReportDeleteForbiddenError,
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
    ReportVisibilityForbiddenError,
)
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_broken_report, make_content, make_report
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.report_defs import col, cond, raw
from tests.support.user_ids import uid

OWNER = uid("rpt-owner")
OTHER = uid("rpt-other")
ADMIN = uid("rpt-admin")


def test_create_sets_owner_editor_revision_one_and_times() -> None:
    """만들면 만든 사람 = 최종 수정자, revision 1, 생성·수정 시각이 같다."""
    # given: 비공개 설정의 저장 내용
    content = make_content("분기 현황", description="설명", visibility="private")
    # when: 리포트를 만든다
    report = Report.create(entity_id=ReportId(new_id()), content=content, owner=OWNER, now=NOW)
    # then: 내용·소유·revision·시각이 정해진다
    assert (report.name, report.description, report.visibility) == (
        "분기 현황",
        "설명",
        ReportVisibility.PRIVATE,
    )
    assert report.owner_user_id == OWNER
    assert report.updated_by_user_id == OWNER
    assert report.revision == 1
    assert (report.created_at, report.updated_at) == (NOW, NOW)
    assert report.definition == content.definition
    assert report.generated_sql == content.generated_sql


def test_overwrite_replaces_content_and_bumps_revision() -> None:
    """덮어쓰면 내용이 바뀌고 최종 수정자·수정 시각이 갱신되며 revision이 오른다.

    테스트 코드: RS-016
    """
    # given: 공개 리포트와 새 내용
    report = make_report("이전", owner=OWNER, visibility="public", description="옛 설명")
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    content = make_content(
        "이후",
        description="새 설명",
        visibility="public",
        definition=definition,
        generated_sql="SELECT new",
    )
    # when: 다른 사용자가 revision 1로 덮어쓴다
    report.overwrite(content, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(5))
    # then: 내용·최종 수정자·revision·수정 시각이 바뀐다
    assert (report.name, report.description) == ("이후", "새 설명")
    assert report.definition == definition
    assert report.generated_sql == "SELECT new"
    assert report.updated_by_user_id == OTHER
    assert report.revision == 2
    assert report.updated_at == later(5)


def test_overwrite_keeps_the_owner_and_created_at() -> None:
    """덮어써도 만든 사람과 생성 시각은 그대로다.

    테스트 코드: RS-016
    """
    # given: 공개 리포트
    report = make_report(owner=OWNER, visibility="public")
    # when: 다른 사용자가 덮어쓴다
    report.overwrite(
        make_content(), editor=OTHER, role=Role.USER, expected_revision=1, now=later(5)
    )
    # then: 만든 사람과 생성 시각이 그대로다
    assert report.owner_user_id == OWNER
    assert report.created_at == NOW


def test_overwrite_with_old_revision_raises_conflict_and_changes_nothing() -> None:
    """낡은 revision으로 덮어쓰면 충돌이고 리포트는 바뀌지 않는다.

    테스트 코드: RS-018
    """
    # given: revision 3인 리포트
    report = make_report("원본", owner=OWNER, revision=3)
    # when·then: revision 2로 덮어쓰면 충돌이다
    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content("바뀜"), editor=OWNER, role=Role.SALES, expected_revision=2, now=later(5)
        )
    # then: 이름·revision·최종 수정자·수정 시각이 그대로다
    assert (report.name, report.revision, report.updated_by_user_id) == ("원본", 3, OWNER)
    assert report.updated_at == NOW


def test_overwrite_with_a_future_revision_is_also_a_conflict() -> None:
    """저장된 것보다 높은 revision도 충돌이다.

    테스트 코드: RS-018
    """
    # given: revision 1인 리포트
    report = make_report(owner=OWNER, revision=1)
    # when·then: revision 2로 덮어쓰면 충돌이다
    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(), editor=OWNER, role=Role.SALES, expected_revision=2, now=later(5)
        )


def test_non_owner_cannot_change_visibility_but_can_keep_it() -> None:
    """만든 사람이 아닌 편집자는 공개 범위를 바꿀 수 없지만 같은 값은 보낼 수 있다.

    테스트 코드: RS-019
    """
    # given: 공개 리포트
    report = make_report(owner=OWNER, visibility="public")
    # when·then: 다른 사용자가 private으로 덮어쓰면 공개 범위 권한 오류다
    with pytest.raises(ReportVisibilityForbiddenError):
        report.overwrite(
            make_content(visibility="private"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,
            now=later(5),
        )
    # then: 리포트는 그대로다
    assert report.visibility is ReportVisibility.PUBLIC
    assert report.revision == 1
    # when: 같은 공개 범위로 덮어쓴다
    report.overwrite(
        make_content(visibility="public"),
        editor=OTHER,
        role=Role.SALES,
        expected_revision=1,
        now=later(5),
    )
    # then: 덮어써져 revision이 오른다
    assert report.revision == 2


@pytest.mark.parametrize(
    ("editor", "role"), [(OWNER, Role.USER), (ADMIN, Role.ADMIN)], ids=["owner", "admin"]
)
def test_owner_and_admin_can_change_visibility(editor: object, role: Role) -> None:
    """만든 사람과 admin은 공개 범위를 바꿀 수 있다.

    테스트 코드: RS-020
    """
    # given: 공개 리포트
    report = make_report(owner=OWNER, visibility="public")
    # when: 만든 사람 또는 admin이 private으로 덮어쓴다
    report.overwrite(
        make_content(visibility="private"),
        editor=editor,  # type: ignore[arg-type]
        role=role,
        expected_revision=1,
        now=later(5),
    )
    # then: 공개 범위가 private이다
    assert report.visibility is ReportVisibility.PRIVATE


def test_hidden_report_check_comes_before_conflict_and_visibility() -> None:
    """볼 수 없는 리포트는 revision·공개 범위가 틀려도 404가 먼저다.

    테스트 코드: RS-021
    """
    # given: revision 4인 남의 비공개 리포트
    report = make_report(owner=OWNER, visibility="private", revision=4)
    # when·then: 다른 사용자가 틀린 revision과 다른 공개 범위로 덮어쓰면 404다
    with pytest.raises(ReportNotFoundError):
        report.overwrite(
            make_content(visibility="public"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,
            now=later(5),
        )
    # then: revision이 그대로다
    assert report.revision == 4


def test_visibility_check_comes_before_the_conflict_check() -> None:
    """공개 범위 권한(403)이 revision 충돌(409)보다 먼저 판정된다.

    테스트 코드: RS-021
    """
    # given: revision 4인 남의 공개 리포트
    report = make_report(owner=OWNER, visibility="public", revision=4)
    # when·then: 다른 사용자가 private으로 낡은 revision 1로 덮어쓰면 공개 범위 권한 오류다
    with pytest.raises(ReportVisibilityForbiddenError):
        report.overwrite(
            make_content(visibility="private"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,
            now=later(5),
        )


def test_admin_can_overwrite_others_private_report() -> None:
    """admin은 남의 비공개 리포트를 덮어쓰고 만든 사람은 그대로다.

    테스트 코드: RS-015
    """
    # given: 남의 비공개 리포트
    report = make_report(owner=OWNER, visibility="private")
    # when: admin이 덮어쓴다
    report.overwrite(
        make_content(visibility="private"),
        editor=ADMIN,
        role=Role.ADMIN,
        expected_revision=1,
        now=later(5),
    )
    # then: 최종 수정자는 admin, 만든 사람은 그대로다
    assert report.updated_by_user_id == ADMIN
    assert report.owner_user_id == OWNER


def test_ensure_visible_to_follows_the_view_rule() -> None:
    """볼 수 있는지 확인은 보기 규칙을 따르고 숨겨야 하면 찾을 수 없음 오류다.

    테스트 코드: RS-014
    """
    # given: 비공개·공개 리포트
    private = make_report(owner=OWNER, visibility="private")
    public = make_report(owner=OWNER, visibility="public")
    # when: 만든 사람·admin·공개 리포트를 확인한다 (오류 없이 끝나야 한다)
    private.ensure_visible_to(OWNER, Role.USER)
    private.ensure_visible_to(ADMIN, Role.ADMIN)
    public.ensure_visible_to(OTHER, Role.USER)
    # when·then: 남의 비공개를 확인하면 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        private.ensure_visible_to(OTHER, Role.SALES)


def test_owner_deletes_own_private_and_public_but_not_others_public() -> None:
    """만든 사람은 공개·비공개를 지우고 admin은 모두 지우지만 남의 공개는 지울 수 없다.

    테스트 코드: RS-025
    """
    # given: 공개·비공개 리포트
    private = make_report(owner=OWNER, visibility="private")
    public = make_report(owner=OWNER, visibility="public")
    # when: 만든 사람과 admin이 삭제를 확인한다 (오류 없이 끝나야 한다)
    private.ensure_deletable_by(OWNER, Role.USER)
    public.ensure_deletable_by(OWNER, Role.USER)
    public.ensure_deletable_by(ADMIN, Role.ADMIN)
    private.ensure_deletable_by(ADMIN, Role.ADMIN)
    # when·then: 남의 공개 리포트 삭제는 삭제 권한 오류다
    with pytest.raises(ReportDeleteForbiddenError):
        public.ensure_deletable_by(OTHER, Role.SALES)


def test_delete_of_others_private_report_is_not_found_not_forbidden() -> None:
    """남의 비공개 리포트의 삭제 확인은 403이 아니라 404다.

    테스트 코드: RS-014
    """
    # given: 남의 비공개 리포트
    private = make_report(owner=OWNER, visibility="private")
    # when·then: 삭제 확인은 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        private.ensure_deletable_by(OTHER, Role.SALES)


def test_copy_as_makes_a_new_owner_with_revision_one_and_same_definition() -> None:
    """복제본은 원본 정의에 요청자 소유, revision 1이고 원본은 그대로다.

    테스트 코드: RS-028
    """
    # given: revision 7인 비공개 원본
    definition = raw([col("deal.vendor", group=True)], [cond("deal.name", "contains", "a")])
    source = make_report(
        "원본", owner=OWNER, visibility="private", revision=7, definition=definition
    )
    new_id_value = ReportId(new_id())
    # when: 다른 사용자가 복제한다
    copy = source.copy_as(
        entity_id=new_id_value,
        meta_name="원본 복사본",
        meta_description="복사 설명",
        visibility=ReportVisibility.PUBLIC,
        generated_sql="SELECT copy",
        owner=OTHER,
        now=later(9),
    )
    # then: 새 id·메타·요청자 소유·revision 1·원본 정의·새 SQL·시각이 정해진다
    assert copy.id == new_id_value
    assert (copy.name, copy.description, copy.visibility) == (
        "원본 복사본",
        "복사 설명",
        ReportVisibility.PUBLIC,
    )
    assert copy.owner_user_id == OTHER
    assert copy.updated_by_user_id == OTHER
    assert copy.revision == 1
    assert copy.definition == definition
    assert copy.generated_sql == "SELECT copy"
    assert (copy.created_at, copy.updated_at) == (later(9), later(9))
    # then: 원본은 그대로다
    assert (source.name, source.owner_user_id, source.revision) == ("원본", OWNER, 7)


def test_entities_follow_the_definition() -> None:
    """목록의 데이터(entities)는 정의가 쓰는 deal·action이다.

    테스트 코드: RS-012
    """
    # given: deal.code와 action.type을 쓰는 정의의 리포트
    report = make_report(definition=raw([col("deal.code"), col("action.type")]))
    # when: 리포트의 데이터(entities)를 구한다
    entities = [e.value for e in report.entities()]
    # then: deal, action 순서다
    assert entities == ["deal", "action"]


def test_report_errors_have_the_expected_kinds_and_messages() -> None:
    """저장 리포트 오류의 종류와 사용자 문구가 명세와 같다."""
    # when: 찾을 수 없음·이름 중복·충돌 오류를 만든다
    missing = ReportNotFoundError(ReportId(5))
    duplicate = DuplicateReportNameError("x")
    conflict = ReportEditConflictError()
    # then: 찾을 수 없음 / 이름 중복 / 충돌이 해당 종류와 문구다
    assert isinstance(missing, NotFoundError)
    assert str(missing) == "리포트를 찾을 수 없습니다."

    assert isinstance(duplicate, AlreadyExistsError)
    assert str(duplicate) == "같은 이름의 리포트가 이미 있습니다."

    assert isinstance(conflict, InvalidStateError)
    assert str(conflict) == (
        "다른 사용자가 먼저 이 리포트를 저장했습니다."
        " 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."
    )
    # when·then: 권한 오류 세 가지가 문구를 갖고 접근 거부 종류다
    with raises_with(
        ReportDeleteForbiddenError, "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    ):
        raise ReportDeleteForbiddenError
    with raises_with(
        ReportVisibilityForbiddenError, "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."
    ):
        raise ReportVisibilityForbiddenError
    with raises_with(ReportEditForbiddenError, "이 리포트를 수정할 권한이 없습니다."):
        raise ReportEditForbiddenError
    for forbidden in (
        ReportDeleteForbiddenError(),
        ReportVisibilityForbiddenError(),
        ReportEditForbiddenError(),
    ):
        assert isinstance(forbidden, AccessDeniedError)


# ---- 깨진 저장 정의 ----


def test_broken_report_has_no_entities() -> None:
    """깨진 저장 정의 리포트의 데이터(entities)는 비어 있다.

    테스트 코드: RS-035
    """
    # when: 깨진 리포트의 entities를 구한다
    entities = make_broken_report().entities()
    # then: 빈 튜플이다
    assert entities == ()


def test_broken_report_refuses_to_give_its_definition_as_stored_invalid() -> None:
    """깨진 리포트에서 정의를 읽으려 하면 stored-invalid(위치 definition) 오류다.

    테스트 코드: RS-036
    """
    # when·then: 읽을 수 있는 정의를 요청하면 정의 오류다
    with pytest.raises(ReportDefinitionError) as caught:
        make_broken_report().readable_definition()
    assert [(i.location, i.code) for i in caught.value.issues] == [
        (("definition",), "stored-invalid")
    ]


def test_readable_definition_returns_the_definition_of_a_healthy_report() -> None:
    """정상 리포트는 저장된 정의를 그대로 준다."""
    # given: 정의가 있는 리포트
    definition = raw([col("deal.code")])
    # when: 읽을 수 있는 정의를 구한다
    readable = make_report(definition=definition).readable_definition()
    # then: 저장된 정의다
    assert readable == definition


def test_broken_report_is_still_hidden_from_users_who_cannot_see_it() -> None:
    """깨진 리포트도 볼 수 없는 사용자에게는 숨는다.

    테스트 코드: RS-036
    """
    # given: 남의 비공개 깨진 리포트
    report = make_broken_report(owner=OWNER, visibility="private")
    # when·then: 다른 사용자가 볼 수 있는지 확인하면 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        report.ensure_visible_to(OTHER, Role.SALES)


def test_overwrite_repairs_a_broken_report() -> None:
    """깨진 리포트는 새 정의로 덮어써 복구된다.

    테스트 코드: RS-037
    """
    # given: revision 3인 깨진 리포트와 새 정의
    report = make_broken_report(owner=OWNER, revision=3)
    definition = raw([col("deal.vendor", group=True)])
    # when: 새 정의로 revision 3을 보내 덮어쓴다
    report.overwrite(
        make_content("복구", definition=definition),
        editor=OWNER,
        role=Role.SALES,
        expected_revision=3,
        now=later(5),
    )
    # then: 정의를 읽을 수 있고 revision 4다
    assert report.readable_definition() == definition
    assert report.revision == 4


def test_copy_of_a_broken_report_is_refused_as_stored_invalid() -> None:
    """깨진 리포트의 복제는 stored-invalid 정의 오류다.

    테스트 코드: RS-036
    """
    # given: 깨진 원본
    source = make_broken_report(owner=OWNER)
    # when·then: 복제하면 정의 오류다
    with pytest.raises(ReportDefinitionError):
        source.copy_as(
            entity_id=ReportId(new_id()),
            meta_name="복사",
            meta_description="",
            visibility=ReportVisibility.PUBLIC,
            generated_sql="SELECT 1",
            owner=OTHER,
            now=later(1),
        )
