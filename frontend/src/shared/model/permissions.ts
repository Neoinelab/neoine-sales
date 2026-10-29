/**
 * 역할별 권한 판단 순수 함수(A-0 계약, 본문 구현 완료). 계획 6.9 권한 매트릭스.
 * 화면은 이 함수로 버튼 노출을, 게이트웨이는 같은 함수로 403을 판단한다(이중 방어).
 *
 * | 항목                                    | admin  | sales                         | user |
 * | Deal 등록/수정/Inline/Action 등록/업로드/새 Label | O | O                         | X    |
 * | Deal 삭제                                | 모두   | Owner가 본인인 Deal만          | X    |
 * | Action 수정/삭제                          | 모두   | 본인이 남긴 Action만(P2 Q8)    | X    |
 * | 파일 삭제                                | 전체   | 본인 업로드 + 퇴사 sales 업로드 | X    |
 * | 코드·Label 수정/삭제, 사용자, contacts, 설정 | O      | X                             | X    |
 */

import type { ReportVisibility } from './reportTypes'
import type { Role, UserRef } from './types'

export interface Viewer {
  id: number
  role: Role
}

/** 쓰기(등록·수정·Inline·Action 등록·업로드·새 Label) 가능 여부: admin 또는 sales. Action 수정·삭제는 canEditAction. */
export function canWrite(role: Role | null | undefined): boolean {
  return role === 'admin' || role === 'sales'
}

export function isAdmin(role: Role | null | undefined): boolean {
  return role === 'admin'
}

/** Admin 메뉴·`/admin/*` 접근. admin만. */
export function canAccessAdmin(role: Role | null | undefined): boolean {
  return role === 'admin'
}

/** Deal 삭제: admin은 모든 Deal, sales는 Owner가 본인인 Deal만, user는 불가. */
export function canDeleteDeal(viewer: Viewer, ownerId: number): boolean {
  if (viewer.role === 'admin') return true
  return viewer.role === 'sales' && viewer.id === ownerId
}

/**
 * 첨부 파일 삭제: admin은 전체, sales는 본인이 올린 파일 또는 업로더가 퇴사한 sales인 파일,
 * user는 불가. (퇴사한 admin/user의 파일은 sales가 지울 수 없다.)
 */
export function canDeleteAttachment(viewer: Viewer, uploadedBy: UserRef): boolean {
  if (viewer.role === 'admin') return true
  if (viewer.role !== 'sales') return false
  if (uploadedBy.id === viewer.id) return true
  return uploadedBy.role === 'sales' && uploadedBy.status === 'resigned'
}

/** Action 수정·삭제: admin은 모든 Action, sales는 본인이 남긴 Action만, user는 불가. */
export function canEditAction(viewer: Viewer, actorId: number): boolean {
  if (viewer.role === 'admin') return true
  return viewer.role === 'sales' && viewer.id === actorId
}

/** 파트너 미팅 기록 수정·삭제: admin은 모두, sales는 본인이 남긴 기록만, user는 불가. */
export function canEditMeeting(viewer: Viewer, authorId: number): boolean {
  if (viewer.role === 'admin') return true
  return viewer.role === 'sales' && viewer.id === authorId
}

/** 새 BANT Label 생성(Deal 화면): sales/admin. */
export function canCreateLabel(role: Role | null | undefined): boolean {
  return canWrite(role)
}

/** BANT Label 이름 변경·삭제, Status/Forecast 코드 관리, 사용자·contacts·설정 변경: admin만. */
export function canManageMasterData(role: Role | null | undefined): boolean {
  return role === 'admin'
}

/** Owner로 지정 가능한 사용자: 재직 중인 sales만. */
export function canBeOwner(user: Pick<UserRef, 'role' | 'status'>): boolean {
  return user.role === 'sales' && user.status === 'active'
}

/** 상단 메뉴 항목(경로). 사용자 메뉴 5개 고정, admin에게만 Admin 추가. */
export function visibleMenu(role: Role | null | undefined): readonly string[] {
  const base = ['/dashboard', '/deals', '/partner-activities', '/forecast', '/reports']
  return role === 'admin' ? [...base, '/admin'] : base
}

/**
 * 저장 리포트 권한(서버 `saved_report/policy.py`와 같은 규칙, 소유는 id로 판정한다).
 * | 대상                 | 보기·복제 | 수정 | 공개 범위 변경 | 삭제 |
 * | 내가 만든 것          | O        | O    | O            | O    |
 * | 남이 만든 공개        | O        | O    | admin만       | admin만 |
 * | 남이 만든 비공개      | admin만   | admin만 | admin만     | admin만 |
 */
type ReportRef = { owner: Pick<UserRef, 'id'>; visibility: ReportVisibility }

export function canViewReport(viewer: Viewer, report: ReportRef): boolean {
  return viewer.role === 'admin' || viewer.id === report.owner.id || report.visibility === 'public'
}

export function canEditReport(viewer: Viewer, report: ReportRef): boolean {
  return canViewReport(viewer, report)
}

/** 삭제: 만든 사람(공개·비공개 무관) 또는 admin. 남의 공개 리포트는 수정만 되고 삭제는 안 된다. */
export function canDeleteReport(viewer: Viewer, report: Pick<ReportRef, 'owner'>): boolean {
  return viewer.role === 'admin' || viewer.id === report.owner.id
}

export function canChangeReportVisibility(viewer: Viewer, report: Pick<ReportRef, 'owner'>): boolean {
  return canDeleteReport(viewer, report)
}
