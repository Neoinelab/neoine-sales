"""권한 표(경로별로 어떤 역할이 쓸 수 있는가) 테스트 데이터 (PL-R3, 2026-11-09).

각 feature 문서 2.5의 합본이다. 행마다 소유 feature 코드를 주석으로 단다. 새 /api/v1 엔드포인트는
소유 feature 2.5와 이 표에 한 줄을 함께 더한다(안 하면 "모든 경로가 표에 있다" 케이스 PL-002가
실패한다). 값은 그 엔드포인트를 쓸 수 있는 역할 집합이고, None은 로그인 없이 쓰는 공개
엔드포인트다. 경로 형식은 OpenAPI의 경로 템플릿과 같다.
"""

from typing import Final

from app.domain.auth.principal import Role
from tests.support.ids import MISSING_ID

Route = tuple[str, str]  # (HTTP 메서드 대문자, 경로 템플릿)

EVERYONE: Final = frozenset({Role.ADMIN, Role.SALES, Role.USER})  # 로그인한 모든 역할
WRITERS: Final = frozenset({Role.ADMIN, Role.SALES})
ADMINS: Final = frozenset({Role.ADMIN})

BUSINESS_READS: Final = (
    ("GET", "/api/v1/contacts/companies"),  # CT Deal 화면의 연락처 선택: 로그인한 모든 역할
    ("GET", "/api/v1/contacts/by-company"),  # CT
    ("GET", "/api/v1/deals"),  # DL
    ("GET", "/api/v1/deals/export"),  # DL 검색 조건에 맞는 전체 결과 CSV: 모든 역할
    ("GET", "/api/v1/deals/years"),  # DL 연도 선택지 기준(가장 이른 Expected Close 연도): 모든 역할
    ("GET", "/api/v1/deals/{code}"),  # DD
    ("GET", "/api/v1/deals/{code}/deletion-impact"),  # DD
    ("GET", "/api/v1/deals/{code}/history"),  # DD
    ("GET", "/api/v1/deals/{code}/actions"),  # AC
    ("GET", "/api/v1/deal-actions/{action_id}"),  # AC 전역 검색 GET /deal-actions는 폐지(P2)
    ("GET", "/api/v1/deals/{code}/attachments"),  # AT P2b: 첨부 목록·단건·다운로드는 모든 역할(Q5)
    ("GET", "/api/v1/attachments/{attachment_id}"),  # AT
    ("GET", "/api/v1/attachments/{attachment_id}/download"),  # AT
    (
        "GET",
        "/api/v1/user-options",
    ),  # US 사용자 선택 UI용: 로그인한 모든 역할(이메일·역할은 노출 안 함)
    ("GET", "/api/v1/codes"),  # CD
    ("GET", "/api/v1/bant-labels"),  # CL
    ("GET", "/api/v1/action-types"),  # CL Action 폼·검색의 유형 선택지: 모든 역할
    ("GET", "/api/v1/vendors"),  # CL Deal 폼·필터의 Vendor 선택지: 모든 역할
    ("GET", "/api/v1/dashboard/summary"),  # DSH 조회 전용: 모든 역할
    ("GET", "/api/v1/deals/updated-periods"),  # DL
    ("GET", "/api/v1/forecast/summary"),  # FC
    ("GET", "/api/v1/forecast/snapshots"),  # FC
    ("GET", "/api/v1/forecast/snapshots/{period}/summary"),  # FC
    ("GET", "/api/v1/time"),  # TM 서버 시각: 로그인한 모든 역할
    ("GET", "/api/v1/alert-settings"),  # RK P3: 경고 기준 조회는 모든 역할(목록 범례에 숫자가 필요)
    ("GET", "/api/v1/reports/fields"),  # 필드 카탈로그는 모든 역할
    ("POST", "/api/v1/reports/query"),  # RQ POST지만 조회 전용(저장 없음)이라 user도 쓸 수 있다
    ("GET", "/api/v1/partner-meetings"),  # PA 파트너 Activity 목록: 모든 역할
    ("GET", "/api/v1/license-contracts"),  # LC 계약관리 목록·단건·첨부 목록·다운로드: 모든 역할
    ("GET", "/api/v1/license-contracts/{contract_id}"),  # LC
    ("GET", "/api/v1/license-contracts/{contract_id}/attachments"),  # LC
    ("GET", "/api/v1/license-contract-attachments/{attachment_id}/download"),  # LC
    ("GET", "/api/v1/deals/{code}/comments"),  # CM Deal 소속 Comment 목록: 모든 역할
    ("GET", "/api/v1/deal-comments/{comment_id}"),  # CM Comment 한 건: 모든 역할
    ("GET", "/api/v1/deals/{code}/comment-counts"),  # CM 읽지 않은 수 집계: 모든 역할
)
BUSINESS_WRITES: Final = (
    ("POST", "/api/v1/bant-labels"),  # CL 자기 Label을 만든다(user는 조회 전용)
    ("POST", "/api/v1/action-types"),  # CL 자기 Action 유형을 만든다(user는 조회 전용)
    ("POST", "/api/v1/deals"),  # DE
    ("PATCH", "/api/v1/deals/{code}"),  # DE
    ("POST", "/api/v1/deals/{code}/changes"),  # DD Status·Forecast·금액·Expected Close 단일 변경
    ("DELETE", "/api/v1/deals/{code}"),  # DD
    ("POST", "/api/v1/deals/{code}/actions"),  # AC
    ("PUT", "/api/v1/deal-actions/{action_id}"),  # AC
    ("DELETE", "/api/v1/deal-actions/{action_id}"),  # AC
    (
        "PUT",
        "/api/v1/deal-actions/{action_id}/next-action-status",
    ),  # NA 상태 변경은 sales·admin(본인 판정은 그 다음)
    ("POST", "/api/v1/deals/{code}/attachments"),  # AT P2b: 업로드·삭제는 sales·admin
    ("DELETE", "/api/v1/attachments/{attachment_id}"),  # AT
    ("POST", "/api/v1/partner-meetings"),  # PA 파트너 Activity 입력·수정·삭제는 sales·admin
    ("PUT", "/api/v1/partner-meetings/{meeting_id}"),  # PA 본인 판정은 그 다음
    ("DELETE", "/api/v1/partner-meetings/{meeting_id}"),  # PA
    (
        "PUT",
        "/api/v1/license-contracts/{contract_id}",
    ),  # LC 계약 칸 수정·발급·갱신·종료는 sales·admin
    ("POST", "/api/v1/license-contracts/{contract_id}/issue"),  # LC
    ("POST", "/api/v1/license-contracts/{contract_id}/renewal"),  # LC
    ("POST", "/api/v1/license-contracts/{contract_id}/end"),  # LC
    ("POST", "/api/v1/license-contracts/{contract_id}/attachments"),  # LC 첨부 업로드·삭제
    ("DELETE", "/api/v1/license-contract-attachments/{attachment_id}"),  # LC
    ("POST", "/api/v1/deals/{code}/comments"),  # CM 작성은 sales·admin(어느 Deal·Action에든)
    (
        "DELETE",
        "/api/v1/deal-comments/{comment_id}",
    ),  # CM 삭제도 sales·admin(본인 판정은 뒤, 수정 폐지)
    ("POST", "/api/v1/deals/{code}/comment-reads"),  # CM 읽음 처리: sales·admin(Owner 판정은 뒤)
)
# 저장 리포트. 만들기·수정·삭제를 로그인한 모든 역할이 한다(user 포함).
# 수정·삭제 가능 여부는 리포트마다 다르며(만든 사람·공개 범위·admin) 도메인 정책이 판정한다.
REPORT_ROUTES: Final = (
    ("GET", "/api/v1/reports"),  # RS
    ("POST", "/api/v1/reports"),  # RS
    ("GET", "/api/v1/reports/{report_id}"),  # RS
    ("PUT", "/api/v1/reports/{report_id}"),  # RS
    ("DELETE", "/api/v1/reports/{report_id}"),  # RS
    ("PUT", "/api/v1/reports/{report_id}/layout"),  # RS 배치만 저장: 보기 화면 자동 저장이 쓴다
    ("POST", "/api/v1/reports/{report_id}/copy"),  # RS
    ("POST", "/api/v1/reports/{report_id}/run"),  # RS
)
ADMIN_ONLY: Final = (
    ("GET", "/api/v1/users"),  # US
    ("GET", "/api/v1/contacts"),  # CT 연락처 관리(목록·등록·수정·삭제)는 admin 전용
    ("POST", "/api/v1/contacts"),  # CT
    ("PUT", "/api/v1/contacts/{contact_id}"),  # CT
    ("DELETE", "/api/v1/contacts/{contact_id}"),  # CT
    ("GET", "/api/v1/codes/usage"),  # CD
    ("POST", "/api/v1/codes"),  # CD
    ("PATCH", "/api/v1/codes/{code_id}"),  # CD
    ("PUT", "/api/v1/codes/order"),  # CD
    ("DELETE", "/api/v1/codes/{code_id}"),  # CD
    ("PATCH", "/api/v1/bant-labels/{label_id}"),  # CL
    ("DELETE", "/api/v1/bant-labels/{label_id}"),  # CL 자기가 만든 Label이라도 sales는 403
    ("PATCH", "/api/v1/action-types/{type_id}"),  # CL Action 유형 이름 변경·삭제는 admin만
    ("DELETE", "/api/v1/action-types/{type_id}"),  # CL
    ("POST", "/api/v1/users"),  # US
    ("DELETE", "/api/v1/users/{user_id}"),  # US
    ("PUT", "/api/v1/users/{user_id}/role"),  # US 역할 변경은 admin만
    ("PATCH", "/api/v1/users/{user_id}"),  # US 다른 사용자의 이름·이메일·전화 수정은 admin만
    ("PUT", "/api/v1/users/{user_id}/password"),  # US local 모드 비밀번호 재설정은 admin만
    ("GET", "/api/v1/settings/directory"),  # IN
    ("PUT", "/api/v1/settings/directory"),  # IN
    ("POST", "/api/v1/settings/directory/test"),  # IN
    ("GET", "/api/v1/settings/storage"),  # IN P2b: 파일 저장 위치 조회·변경·쓰기 확인
    ("PUT", "/api/v1/settings/storage"),  # IN
    ("POST", "/api/v1/settings/storage/test"),  # IN
    ("PUT", "/api/v1/alert-settings"),  # RK P3: 경고 기준 변경은 admin만
    ("POST", "/api/v1/vendors"),  # CL Vendor 관리는 생성도 admin만(D11)
    ("PATCH", "/api/v1/vendors/{vendor_id}"),  # CL
    ("DELETE", "/api/v1/vendors/{vendor_id}"),  # CL
    # 계약 삭제는 admin만. 없는 id여도 admin이 아니면 403이 먼저다(2026-11-09, LC-083)
    ("DELETE", "/api/v1/license-contracts/{contract_id}"),  # LC
)
PUBLIC: Final = (
    ("GET", "/healthz"),  # PL
    ("GET", "/readyz"),  # PL
    ("GET", "/api/v1/auth/config"),  # AU
    ("POST", "/api/v1/auth/login"),  # AU
    ("POST", "/api/v1/auth/logout"),  # AU
    ("PUT", "/api/v1/auth/setup/auth-mode"),  # SU 최초 설정 1단계: 인증 방식 선택(admin 전까지)
    ("PUT", "/api/v1/auth/setup/directory"),  # SU
    ("POST", "/api/v1/auth/setup/directory/test"),  # SU AD 연결 테스트(저장 없음, admin 전까지)
    ("PUT", "/api/v1/auth/setup/storage"),  # SU P2b 최초 설정 2단계
    ("POST", "/api/v1/auth/setup/storage/test"),  # SU
    ("POST", "/api/v1/auth/setup"),  # SU
)
LOGGED_IN_ANY: Final = (
    ("GET", "/api/v1/auth/me"),  # AU
    ("GET", "/api/v1/me/profile"),  # ME 내 정보: 로그인한 모든 역할(user 포함)이 자기 정보를 본다
    ("PATCH", "/api/v1/me/profile"),  # ME 아이디를 뺀 자기 정보 수정: 모든 역할
    ("PUT", "/api/v1/me/password"),  # ME local 모드 비밀번호 변경: 모든 역할(ad는 409)
)

EXPECTED: Final[dict[Route, frozenset[Role] | None]] = {
    **dict.fromkeys(PUBLIC),
    **dict.fromkeys(LOGGED_IN_ANY, EVERYONE),
    **dict.fromkeys(BUSINESS_READS, EVERYONE),
    **dict.fromkeys(REPORT_ROUTES, EVERYONE),
    **dict.fromkeys(BUSINESS_WRITES, WRITERS),
    **dict.fromkeys(ADMIN_ONLY, ADMINS),
}

PLACEHOLDER = str(MISSING_ID)
ABSENT_DEAL_CODE = (
    "20260101-ZZZZ"  # 형식은 맞지만 없는 Deal code(권한 검사는 조회보다 먼저여야 한다)
)
ROLES: Final = (Role.ADMIN, Role.SALES, Role.USER)


def concrete_path(template: str) -> str:
    """경로 템플릿의 `{...}`를 존재하지 않는 값으로 채운다(권한 검사는 조회보다 먼저여야 한다)."""
    out = template
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = (
            out[:start]
            + (ABSENT_DEAL_CODE if out[start + 1 : end] == "code" else PLACEHOLDER)
            + out[end + 1 :]
        )
    return out


def protected_routes() -> list[Route]:
    """로그인이 필요한 경로(공개 경로 제외)."""
    return [route for route, roles in EXPECTED.items() if roles is not None]


def route_id(route: Route) -> str:
    """pytest id로 쓰는 `METHOD 경로`."""
    return f"{route[0]} {route[1]}"


def request_body(method: str) -> dict[str, object] | None:
    """POST·PUT·PATCH는 빈 객체, 그 밖은 본문 없음."""
    return {} if method in {"POST", "PUT", "PATCH"} else None


def garbage_body(method: str) -> dict[str, object] | None:
    """본문 검증에 걸릴 잘못된 본문(DELETE는 본문 없음)."""
    return {"unexpected": ["garbage"]} if method != "DELETE" else None
