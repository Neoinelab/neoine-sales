import { describe, expect, it } from 'vitest'
import {
  canBeOwner,
  canChangeReportVisibility,
  canDeleteAttachment,
  canDeleteDeal,
  canDeleteReport,
  canEditMeeting,
  canEditAction,
  canEditReport,
  canViewReport,
  canWrite,
  visibleMenu,
} from './permissions'
import type { ReportVisibility } from './reportTypes'
import type { Role } from './types'
import { USER_ID } from '../../test/fake/seed/ids'

const resigned = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' } as const
const active = { id: USER_ID.park, name: '박영업', role: 'sales', status: 'active' } as const

describe('permissions', () => {
  it('쓰기와 메뉴', () => {
    expect(canWrite('user')).toBe(false)
    expect(canWrite('sales')).toBe(true)
    expect(visibleMenu('admin')).toHaveLength(6)
    expect(visibleMenu('sales')).toHaveLength(5)
  })

  it('Deal 삭제: admin 전체, sales 본인, user 불가', () => {
    expect(canDeleteDeal({ id: USER_ID.root, role: 'admin' }, USER_ID.kim)).toBe(true)
    expect(canDeleteDeal({ id: USER_ID.kim, role: 'sales' }, USER_ID.kim)).toBe(true)
    expect(canDeleteDeal({ id: USER_ID.park, role: 'sales' }, USER_ID.kim)).toBe(false)
    expect(canDeleteDeal({ id: USER_ID.han, role: 'user' }, USER_ID.han)).toBe(false)
  })

  it.each([
    ['admin edits the action of another user', { id: USER_ID.root, role: 'admin' }, USER_ID.kim, true],
    ['admin edits the action of themselves', { id: USER_ID.root, role: 'admin' }, USER_ID.root, true],
    ['sales edits their own action', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['sales cannot edit the action of another sales', { id: USER_ID.park, role: 'sales' }, USER_ID.kim, false],
    ['user cannot edit even an action with the same id', { id: USER_ID.han, role: 'user' }, USER_ID.han, false],
    ['user cannot edit the action of another user', { id: USER_ID.han, role: 'user' }, USER_ID.kim, false],
  ] as const)('Action 수정·삭제(Q8): %s', (_name, viewer, actorId, expected) => {
    expect(canEditAction(viewer, actorId)).toBe(expected)
  })

  it('T-FILE-06 파일 삭제 권한 표', () => {
    expect(canDeleteAttachment({ id: USER_ID.root, role: 'admin' }, active)).toBe(true)
    expect(canDeleteAttachment({ id: USER_ID.park, role: 'sales' }, active)).toBe(true)
    expect(canDeleteAttachment({ id: USER_ID.kim, role: 'sales' }, active)).toBe(false)
    expect(canDeleteAttachment({ id: USER_ID.kim, role: 'sales' }, resigned)).toBe(true)
    expect(canDeleteAttachment({ id: USER_ID.han, role: 'user' }, resigned)).toBe(false)
  })

  it('Owner 후보는 재직 sales뿐', () => {
    expect(canBeOwner(active)).toBe(true)
    expect(canBeOwner(resigned)).toBe(false)
    expect(canBeOwner({ role: 'admin', status: 'active' })).toBe(false)
  })
})

/**
 * 저장 리포트 권한 표(Reports 3단계 4.3, AC5·7·9). 서버 `saved_report/policy.py`와 같은 규칙이다.
 * [역할, 누구 리포트, 공개 범위, 보기, 수정, 공개 범위 변경, 삭제]
 */
const REPORT_TABLE: readonly (readonly [Role, 'mine' | 'others', ReportVisibility, boolean, boolean, boolean, boolean])[] = [
  ['admin', 'mine', 'public', true, true, true, true],
  ['admin', 'mine', 'private', true, true, true, true],
  ['admin', 'others', 'public', true, true, true, true],
  ['admin', 'others', 'private', true, true, true, true],
  ['sales', 'mine', 'public', true, true, true, true],
  ['sales', 'mine', 'private', true, true, true, true],
  ['sales', 'others', 'public', true, true, false, false],
  ['sales', 'others', 'private', false, false, false, false],
  ['user', 'mine', 'public', true, true, true, true],
  ['user', 'mine', 'private', true, true, true, true],
  ['user', 'others', 'public', true, true, false, false],
  ['user', 'others', 'private', false, false, false, false],
]

describe('report permissions follow the decision table', () => {
  it.each(REPORT_TABLE)('%s with a report of %s (%s): view %s, edit %s, visibility %s, delete %s', (role, whose, visibility, view, edit, change, remove) => {
    const viewer = { id: USER_ID.han, role }
    const owner = whose === 'mine' ? { id: USER_ID.han } : { id: USER_ID.park }
    const report = { owner, visibility }

    expect(canViewReport(viewer, report)).toBe(view)
    expect(canEditReport(viewer, report)).toBe(edit)
    expect(canChangeReportVisibility(viewer, report)).toBe(change)
    expect(canDeleteReport(viewer, report)).toBe(remove)
  })

  it('judges ownership by user id, not by role or name', () => {
    const viewer = { id: USER_ID.kim, role: 'sales' } as const

    expect(canDeleteReport(viewer, { owner: { id: USER_ID.kim } })).toBe(true)
    expect(canDeleteReport(viewer, { owner: { id: USER_ID.park } })).toBe(false)
    expect(canChangeReportVisibility(viewer, { owner: { id: USER_ID.park } })).toBe(false)
  })

  it('lets a resigned owner be the owner of a report that others can still see when public', () => {
    const viewer = { id: USER_ID.kim, role: 'sales' } as const
    const resignedOwner = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' } as const

    expect(canViewReport(viewer, { owner: resignedOwner, visibility: 'public' })).toBe(true)
    expect(canDeleteReport(viewer, { owner: resignedOwner })).toBe(false)
    expect(canDeleteReport({ id: USER_ID.root, role: 'admin' }, { owner: resignedOwner })).toBe(true)
  })
})

describe('파트너 Activity 권한', () => {
  it('메뉴는 Deals 다음에 /partner-activities가 오고 모든 역할에 보인다', () => {
    expect(visibleMenu('sales')).toEqual(['/dashboard', '/deals', '/partner-activities', '/forecast', '/reports'])
    expect(visibleMenu('user')).toEqual(['/dashboard', '/deals', '/partner-activities', '/forecast', '/reports'])
    expect(visibleMenu('admin')).toEqual(['/dashboard', '/deals', '/partner-activities', '/forecast', '/reports', '/admin'])
  })

  it.each([
    ['admin edits the record of another user', { id: USER_ID.root, role: 'admin' }, USER_ID.kim, true],
    ['admin edits their own record', { id: USER_ID.root, role: 'admin' }, USER_ID.root, true],
    ['sales edits their own record', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['sales cannot edit the record of another sales', { id: USER_ID.park, role: 'sales' }, USER_ID.kim, false],
    ['user cannot edit even a record with the same id', { id: USER_ID.han, role: 'user' }, USER_ID.han, false],
    ['user cannot edit the record of another user', { id: USER_ID.han, role: 'user' }, USER_ID.kim, false],
  ] as const)('수정·삭제: %s', (_name, viewer, authorId, expected) => {
    expect(canEditMeeting(viewer, authorId)).toBe(expected)
  })
})

