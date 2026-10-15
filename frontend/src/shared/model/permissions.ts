/**
 * 역할별 권한 판단 순수 함수(A-0 계약, 본문 구현 완료). 계획 6.9 권한 매트릭스.
 * 화면은 이 함수로 버튼 노출을, 게이트웨이는 같은 함수로 403을 판단한다(이중 방어).
 *
 * | 항목                                    | admin  | sales                         | user |
 * | Deal 등록/수정/Inline/Action/업로드/새 Label | O      | O                             | X    |
 * | Deal 삭제                                | 모두   | Owner가 본인인 Deal만          | X    |
 * | 파일 삭제                                | 전체   | 본인 업로드 + 퇴사 sales 업로드 | X    |
 * | 코드·Label 수정/삭제, 사용자, contacts, 설정 | O      | X                             | X    |
 */

import type { Role, UserRef } from './types'

export interface Viewer {
  id: string
  role: Role
}

/** 쓰기(등록·수정·Inline·Action·업로드·새 Label) 가능 여부: admin 또는 sales. */
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
export function canDeleteDeal(viewer: Viewer, ownerId: string): boolean {
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

/** Action 수정·삭제: 담당자와 무관하게 sales/admin 모두 가능(PRD: 이전 Action도 수정 가능). */
export function canEditAction(role: Role | null | undefined): boolean {
  return canWrite(role)
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

/** 상단 메뉴 항목(경로). 사용자 메뉴 4개 고정, admin에게만 Admin 추가. */
export function visibleMenu(role: Role | null | undefined): readonly string[] {
  const base = ['/dashboard', '/deals', '/forecast', '/reports']
  return role === 'admin' ? [...base, '/admin'] : base
}
