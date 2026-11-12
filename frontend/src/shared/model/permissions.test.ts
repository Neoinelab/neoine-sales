import { describe, expect, it } from 'vitest'
import {
  canAccessAdmin,
  canBeOwner,
  canChangeReportVisibility,
  canDeleteAttachment,
  canDeleteDeal,
  canDeleteReport,
  canEditMeeting,
  canEditAction,
  canEditReport,
  canManageMasterData,
  canViewReport,
  canWrite,
  isAdmin,
  visibleMenu,
} from './permissions'
import type { ReportVisibility } from './reportTypes'
import type { Role } from './types'
import { USER_ID } from '../../test/fake/seed/ids'

const resigned = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' } as const
const active = { id: USER_ID.park, name: '박영업', role: 'sales', status: 'active' } as const

describe('permissions', () => {
  // 역할 판단 함수는 쓰기·관리자·메뉴를 역할대로 판단한다.
  // 테스트 코드: PL-065
  it('쓰기와 관리자와 메뉴', () => {
    // given: admin·sales·user·없음(null) 네 가지 역할 입력
    const roles = ['admin', 'sales', 'user', null] as const
    // when: 각 역할로 판단 함수를 부른다
    const answers = roles.map((role) => ({
      role,
      write: canWrite(role),
      admin: [isAdmin(role), canAccessAdmin(role), canManageMasterData(role)],
      menu: visibleMenu(role),
    }))
    // then: canWrite는 admin·sales만, 관리자 함수는 admin만 true이고 메뉴는 6개(admin은 Admin 포함 7개)다
    expect(answers.map((a) => a.write)).toEqual([true, true, false, false])
    expect(answers.map((a) => a.admin)).toEqual([
      [true, true, true],
      [false, false, false],
      [false, false, false],
      [false, false, false],
    ])
    expect(answers.map((a) => a.menu.length)).toEqual([7, 6, 6, 6])
    expect(answers[0]?.menu.at(-1)).toBe('/admin')
    expect(answers[2]?.menu).not.toContain('/admin')
  })

  // Deal 삭제 권한은 admin 전체, sales 본인, user 불가다.
  // 테스트 코드: DD-074
  it('Deal 삭제: admin 전체, sales 본인, user 불가', () => {
    // when: 역할·Owner 조합마다 삭제 가능 여부를 판정한다
    const actual1 = canDeleteDeal({ id: USER_ID.root, role: 'admin' }, USER_ID.kim)
    const actual2 = canDeleteDeal({ id: USER_ID.kim, role: 'sales' }, USER_ID.kim)
    const actual3 = canDeleteDeal({ id: USER_ID.park, role: 'sales' }, USER_ID.kim)
    const actual4 = canDeleteDeal({ id: USER_ID.han, role: 'user' }, USER_ID.han)

    // then: admin은 모두, sales는 본인 Deal만 가능하고 user는 본인 Deal도 불가다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
    expect(actual4).toBe(false)
  })

  // Action 수정·삭제는 담당자 본인과 admin만 할 수 있다.
  it.each([
    ['admin edits the action of another user', { id: USER_ID.root, role: 'admin' }, USER_ID.kim, true],
    ['admin edits the action of themselves', { id: USER_ID.root, role: 'admin' }, USER_ID.root, true],
    ['sales edits their own action', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['sales cannot edit the action of another sales', { id: USER_ID.park, role: 'sales' }, USER_ID.kim, false],
    ['user cannot edit even an action with the same id', { id: USER_ID.han, role: 'user' }, USER_ID.han, false],
    ['user cannot edit the action of another user', { id: USER_ID.han, role: 'user' }, USER_ID.kim, false],
  ] as const)('Action 수정·삭제(Q8): %s', (_name, viewer, actorId, expected) => {
    // when: 조회자가 해당 담당자의 Action을 수정할 수 있는지 판단한다
    const allowed = canEditAction(viewer, actorId)

    // then: 담당자 본인과 admin만 true다
    expect(allowed).toBe(expected)
  })

  // admin과 재직 Owner는 파일을 지울 수 있고, 퇴사 Owner의 파일은 다른 sales도 지울 수 있으며 user는 못 지운다.
  // 테스트 코드: AT-050
  it('T-FILE-06 파일 삭제 권한 표', () => {
    // when: 역할·본인 여부가 다른 조회자별로 삭제 가능 여부를 판단한다 (전제: 재직 Owner 박영업과 퇴사 Owner 강퇴사의 Deal)
    const adminOnActive = canDeleteAttachment({ id: USER_ID.root, role: 'admin' }, active)
    const ownerOnActive = canDeleteAttachment({ id: USER_ID.park, role: 'sales' }, active)
    const otherSalesOnActive = canDeleteAttachment({ id: USER_ID.kim, role: 'sales' }, active)
    const salesOnResigned = canDeleteAttachment({ id: USER_ID.kim, role: 'sales' }, resigned)
    const userOnResigned = canDeleteAttachment({ id: USER_ID.han, role: 'user' }, resigned)

    // then: admin·재직 Owner·퇴사 Owner 파일의 sales만 true이고 다른 sales(재직 Owner)와 user는 false다
    expect(adminOnActive).toBe(true)
    expect(ownerOnActive).toBe(true)
    expect(otherSalesOnActive).toBe(false)
    expect(salesOnResigned).toBe(true)
    expect(userOnResigned).toBe(false)
  })

  // Owner 후보는 재직 중인 sales뿐이다.
  it('Owner 후보는 재직 sales뿐', () => {
    // when: 재직 sales·퇴사 sales·재직 admin을 Owner 후보로 판단한다
    const activeSales = canBeOwner(active)
    const resignedSales = canBeOwner(resigned)
    const activeAdmin = canBeOwner({ role: 'admin', status: 'active' })

    // then: 재직 sales만 true다
    expect(activeSales).toBe(true)
    expect(resignedSales).toBe(false)
    expect(activeAdmin).toBe(false)
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
  // 리포트 보기·수정·공개 범위 변경·삭제 권한이 역할·소유·공개 범위별 표와 같다.
  it.each(REPORT_TABLE)('%s with a report of %s (%s): view %s, edit %s, visibility %s, delete %s', (role, whose, visibility, view, edit, change, remove) => {
    const viewer = { id: USER_ID.han, role }
    const owner = whose === 'mine' ? { id: USER_ID.han } : { id: USER_ID.park }
    const report = { owner, visibility }

    // when: 조회자가 리포트의 보기·수정·공개 범위 변경·삭제 권한을 판단한다
    const viewAllowed = canViewReport(viewer, report)
    const editAllowed = canEditReport(viewer, report)
    const changeAllowed = canChangeReportVisibility(viewer, report)
    const removeAllowed = canDeleteReport(viewer, report)

    // then: 표의 값과 같다
    expect(viewAllowed).toBe(view)
    expect(editAllowed).toBe(edit)
    expect(changeAllowed).toBe(change)
    expect(removeAllowed).toBe(remove)
  })

  // 소유 판단은 역할·이름이 아니라 사용자 id로 한다.
  it('judges ownership by user id, not by role or name', () => {
    // given: sales 김영업
    const viewer = { id: USER_ID.kim, role: 'sales' } as const

    // when: 자기 리포트와 남의 리포트의 삭제·공개 범위 변경 권한을 판단한다
    const deleteOwn = canDeleteReport(viewer, { owner: { id: USER_ID.kim } })
    const deleteOther = canDeleteReport(viewer, { owner: { id: USER_ID.park } })
    const changeOther = canChangeReportVisibility(viewer, { owner: { id: USER_ID.park } })

    // then: 자기 것만 삭제할 수 있고 남의 공개 범위는 바꿀 수 없다
    expect(deleteOwn).toBe(true)
    expect(deleteOther).toBe(false)
    expect(changeOther).toBe(false)
  })

  // 퇴사자가 만든 공개 리포트는 다른 사용자도 보고, 삭제는 admin만 한다.
  it('lets a resigned owner be the owner of a report that others can still see when public', () => {
    // given: 퇴사한 Owner의 공개 리포트와 조회자 sales
    const viewer = { id: USER_ID.kim, role: 'sales' } as const
    const resignedOwner = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' } as const

    // when: sales의 보기·삭제와 admin의 삭제 권한을 판단한다
    const view = canViewReport(viewer, { owner: resignedOwner, visibility: 'public' })
    const salesDelete = canDeleteReport(viewer, { owner: resignedOwner })
    const adminDelete = canDeleteReport({ id: USER_ID.root, role: 'admin' }, { owner: resignedOwner })

    // then: sales는 보기만 되고 삭제는 admin만 된다
    expect(view).toBe(true)
    expect(salesDelete).toBe(false)
    expect(adminDelete).toBe(true)
  })
})

describe('파트너 Activity 권한', () => {
  // 메뉴는 Deals 다음에 계약관리, 그다음 파트너 Activity가 오며 모든 역할에 보인다.
  it('메뉴는 Deals 다음에 /contracts, 그다음 /partner-activities가 오며 모든 역할에 보인다', () => {
    // when: 역할별 메뉴를 만든다
    const sales = visibleMenu('sales')
    const user = visibleMenu('user')
    const admin = visibleMenu('admin')

    // then: sales·user는 6개, admin은 /admin이 더해진 7개이며 순서가 같다
    expect(sales).toEqual(['/deals', '/contracts', '/partner-activities', '/dashboard', '/forecast', '/reports'])
    expect(user).toEqual(['/deals', '/contracts', '/partner-activities', '/dashboard', '/forecast', '/reports'])
    expect(admin).toEqual(['/deals', '/contracts', '/partner-activities', '/dashboard', '/forecast', '/reports', '/admin'])
  })

  // 파트너 미팅 기록은 작성자 본인과 admin만 수정·삭제한다.
  // 테스트 코드: PA-092
  it.each([
    ['admin edits the record of another user', { id: USER_ID.root, role: 'admin' }, USER_ID.kim, true],
    ['admin edits their own record', { id: USER_ID.root, role: 'admin' }, USER_ID.root, true],
    ['sales edits their own record', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['sales cannot edit the record of another sales', { id: USER_ID.park, role: 'sales' }, USER_ID.kim, false],
    ['user cannot edit even a record with the same id', { id: USER_ID.han, role: 'user' }, USER_ID.han, false],
    ['user cannot edit the record of another user', { id: USER_ID.han, role: 'user' }, USER_ID.kim, false],
  ] as const)('수정·삭제: %s', (_name, viewer, authorId, expected) => {
    // when: 조회자가 해당 작성자의 미팅 기록을 수정할 수 있는지 판단한다
    const allowed = canEditMeeting(viewer, authorId)

    // then: 작성자 본인과 admin만 true다
    expect(allowed).toBe(expected)
  })
})

