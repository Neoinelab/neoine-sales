import type { UsersGateway } from '../../../gateway/types'
import { hasWhitespace } from '../../../shared/model/contactRules'
import { compareIso } from '../../../shared/model/dates'
import type { Role, UserRef } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import {
  AD_MANAGED,
  checkLoginIdAllowed,
  checkPassword,
  cleanEmail,
  cleanPhone,
  modeOf,
  profilePatch,
  requireLocal,
  setPasswordOf,
} from './accountRules'
import { read, requireAdmin, requireUser, write, type MockContext } from './context'
import { userRef, userView } from './views'

const ROLES: readonly Role[] = ['admin', 'sales', 'user']

/** 사용자와 연결된 데이터(Deal 담당, Action, History, 첨부, Label)가 있는지. 다른 사용자를 등록한 것은 연결이 아니다. */
function hasLinks(ctx: MockContext, id: number): boolean {
  const d = ctx.store.data
  return (
    d.deals.some((x) => x.ownerId === id) ||
    d.actions.some((x) => x.actorId === id) ||
    d.history.some((x) => x.byId === id) ||
    d.attachments.some((x) => x.uploadedById === id) ||
    d.comments.some((x) => x.authorId === id) ||
    d.labels.some((x) => x.createdById === id)
  )
}

export function createUsersGateway(ctx: MockContext): UsersGateway {
  return {
    list: (filter) =>
      read(ctx, () => {
        requireAdmin(ctx)
        const { data } = ctx.store
        return data.users
          .filter((u) => filter === 'all' || u.status === filter)
          .sort((a, b) => compareIso(b.createdAt, a.createdAt) || b.id - a.id)
          .map((u) => userView(u))
      }),
    // 서버 UserOption: UserRef + 로그인 아이디(US-R20, 모든 항목에 항상 있다)
    options: (query) =>
      read(ctx, (): (UserRef & { loginId: string })[] => {
        requireUser(ctx)
        const { data } = ctx.store
        return data.users
          .filter((u) => (query.includeResigned ? true : u.status === 'active'))
          .filter((u) => (query.role ? u.role === query.role : true))
          // 서버(US-R20)는 등록 시각·id 순으로 돌려주고 이름순 정렬은 화면(DL-R40)이 한다.
          .sort((a, b) => compareIso(a.createdAt, b.createdAt) || a.id - b.id)
          .map((u) => ({ ...userRef(data, u.id), loginId: u.loginId }))
      }),
    create: (input) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const loginId = input.loginId.trim()
        const name = input.name.trim()
        if (loginId === '') throw validation('아이디를 입력하세요.')
        if (hasWhitespace(loginId)) throw validation('아이디에는 공백을 입력할 수 없습니다.')
        if (name === '') throw validation('이름을 입력하세요.')
        if (!ROLES.includes(input.role)) throw validation('역할을 선택하세요.')
        const email = cleanEmail(input.email)
        const phone = cleanPhone(input.phone)
        const local = modeOf(ctx) === 'local'
        const password = input.password ?? ''
        checkLoginIdAllowed(loginId)
        if (local) {
          if (password === '') throw validation('비밀번호를 입력하세요.')
          checkPassword(password, loginId)
        } else if (password !== '') {
          throw validation('비밀번호는 앱에서 계정을 직접 관리할 때만 받습니다.')
        }
        const { data } = ctx.store
        if (data.users.some((u) => u.loginId === loginId && u.status === 'active')) throw conflict(`이미 존재하는 사용자입니다: ${loginId}`)
        const record: UserRecord = {
          id: takeId(data.counters, 'u'),
          loginId,
          name,
          role: input.role,
          status: 'active',
          email,
          phone,
          createdAt: ctx.clock.now(),
          lastLoginAt: null,
          resignedAt: null,
        }
        data.users.push(record)
        if (local) setPasswordOf(data, record.id, password)
        return userView(record)
      }),
    update: (id, change) =>
      write(ctx, () => {
        requireAdmin(ctx)
        // 서버 순서(US-R14): AD 모드의 이름·이메일 409 → 404 → 퇴사 409 → 값 검증 422
        if (modeOf(ctx) === 'ad' && (change.name !== undefined || change.email !== undefined)) throw conflict(AD_MANAGED)
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound(`사용자을(를) 찾을 수 없습니다: ${id}`)
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다')
        Object.assign(target, profilePatch(modeOf(ctx), change))
        return userView(target)
      }),
    resetPassword: (id, password) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        requireLocal(ctx)
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound(`사용자을(를) 찾을 수 없습니다: ${id}`)
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다')
        if (target.id === admin.id) throw conflict('자기 자신의 비밀번호는 내 정보에서 바꾸세요.')
        checkPassword(password, target.loginId)
        setPasswordOf(data, target.id, password)
      }),
    changeRole: (id, role) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        if (!ROLES.includes(role)) throw validation('역할을 선택하세요.')
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound(`사용자을(를) 찾을 수 없습니다: ${id}`)
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다')
        if (target.id === admin.id) throw conflict('자기 자신의 역할은 바꿀 수 없습니다.')
        const activeAdmins = data.users.filter((u) => u.status === 'active' && u.role === 'admin').length
        if (target.role === 'admin' && role !== 'admin' && activeAdmins <= 1) throw conflict('마지막 관리자의 역할은 바꿀 수 없습니다.')
        target.role = role
        return userView(target)
      }),
    remove: (id) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound(`사용자을(를) 찾을 수 없습니다: ${id}`)
        // 서버 ensure_deletable 순서: 이미 퇴사 → 자기 자신 → 마지막 재직 admin
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다')
        if (target.id === admin.id) throw conflict('자기 자신은 삭제할 수 없습니다')
        const activeAdmins = data.users.filter((u) => u.status === 'active' && u.role === 'admin').length
        if (target.role === 'admin' && activeAdmins <= 1) throw conflict('마지막 관리자는 삭제할 수 없습니다')
        if (hasLinks(ctx, id)) {
          target.status = 'resigned'
          target.resignedAt = ctx.clock.now()
          return { outcome: 'resigned' as const }
        }
        data.users.splice(data.users.indexOf(target), 1)
        return { outcome: 'deleted' as const }
      }),
  }
}
