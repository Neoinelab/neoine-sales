import type { UsersGateway } from '../../../gateway/types'
import { hasWhitespace } from '../../../shared/model/contactRules'
import { compareIso } from '../../../shared/model/dates'
import type { Role, UserRef } from '../../../shared/model/types'
import { conflict, forbidden, notFound, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import {
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
/** 서버 `DEV_LOGIN_IDS`: 개발 로그인 전용 사용자의 로그인 아이디. */
const DEV_LOGIN_IDS: readonly string[] = ['dev-admin', 'dev-sales', 'dev-user']

/** 사용자와 연결된 데이터(Deal 담당, Action, History, 첨부, Label, 다른 사용자 등록자)가 있는지. */
function hasLinks(ctx: MockContext, id: number): boolean {
  const d = ctx.store.data
  return (
    d.deals.some((x) => x.ownerId === id) ||
    d.actions.some((x) => x.actorId === id) ||
    d.history.some((x) => x.byId === id) ||
    d.attachments.some((x) => x.uploadedById === id) ||
    d.labels.some((x) => x.createdById === id) ||
    d.users.some((x) => x.createdById === id && x.id !== id)
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
          .map((u) => userView(data, u))
      }),
    options: (query) =>
      read(ctx, (): UserRef[] => {
        requireUser(ctx)
        const { data } = ctx.store
        return data.users
          .filter((u) => (query.includeResigned ? true : u.status === 'active'))
          .filter((u) => (query.role ? u.role === query.role : true))
          .sort((a, b) => a.name.localeCompare(b.name, 'ko') || a.id - b.id)
          .map((u) => userRef(data, u.id))
      }),
    create: (input) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
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
        if (local) {
          checkLoginIdAllowed(loginId)
          if (password === '') throw validation('비밀번호를 입력하세요.')
          checkPassword(password, loginId)
        } else if (password !== '') {
          throw validation('비밀번호는 앱에서 계정을 직접 관리할 때만 받습니다.')
        }
        const { data } = ctx.store
        if (data.users.some((u) => u.loginId === loginId && u.status === 'active')) throw conflict('이미 사용 중인 아이디입니다.')
        const record: UserRecord = {
          id: takeId(data.counters, 'u'),
          loginId,
          name,
          role: input.role,
          status: 'active',
          email,
          phone,
          createdAt: ctx.clock.now(),
          createdById: admin.id,
          lastLoginAt: null,
          resignedAt: null,
          resignReason: null,
        }
        data.users.push(record)
        if (local) setPasswordOf(data, record.id, password)
        return userView(data, record)
      }),
    update: (id, change) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound('사용자를 찾을 수 없습니다.')
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다.')
        Object.assign(target, profilePatch(modeOf(ctx), change))
        return userView(data, target)
      }),
    resetPassword: (id, password) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        requireLocal(ctx)
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound('사용자를 찾을 수 없습니다.')
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다.')
        if (target.id === admin.id) throw conflict('자기 자신의 비밀번호는 내 정보에서 바꾸세요.')
        if (DEV_LOGIN_IDS.includes(target.loginId)) throw conflict('개발 로그인 전용 사용자의 비밀번호는 바꿀 수 없습니다.')
        checkPassword(password, target.loginId)
        setPasswordOf(data, target.id, password)
      }),
    changeRole: (id, role) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        if (!ROLES.includes(role)) throw validation('역할을 선택하세요.')
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound('사용자를 찾을 수 없습니다.')
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다.')
        if (target.id === admin.id) throw conflict('자기 자신의 역할은 바꿀 수 없습니다.')
        const activeAdmins = data.users.filter((u) => u.status === 'active' && u.role === 'admin').length
        if (target.role === 'admin' && role !== 'admin' && activeAdmins <= 1) throw conflict('마지막 관리자의 역할은 바꿀 수 없습니다.')
        if (DEV_LOGIN_IDS.includes(target.loginId)) throw conflict('개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다.')
        target.role = role
        return userView(data, target)
      }),
    remove: (id) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        if (id === admin.id) throw forbidden('본인 계정은 삭제할 수 없습니다.')
        const { data } = ctx.store
        const target = data.users.find((u) => u.id === id)
        if (!target) throw notFound('사용자를 찾을 수 없습니다.')
        if (target.status === 'resigned') throw conflict('이미 퇴사 처리된 사용자입니다.')
        if (hasLinks(ctx, id)) {
          target.status = 'resigned'
          target.resignedAt = ctx.clock.now()
          target.resignReason = '관리자 삭제 요청으로 퇴사 처리'
          return { outcome: 'resigned' as const }
        }
        data.users.splice(data.users.indexOf(target), 1)
        return { outcome: 'deleted' as const }
      }),
  }
}
