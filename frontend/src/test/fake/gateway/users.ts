import type { UsersGateway } from '../../../gateway/types'
import { hasWhitespace } from '../../../shared/model/contactRules'
import { compareIso } from '../../../shared/model/dates'
import type { Role, UserRef } from '../../../shared/model/types'
import { conflict, forbidden, notFound, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import { read, requireAdmin, requireUser, write, type MockContext } from './context'
import { userRef, userView } from './views'

const ROLES: readonly Role[] = ['admin', 'sales', 'user']

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
        const { data } = ctx.store
        if (data.users.some((u) => u.loginId === loginId && u.status === 'active')) throw conflict('이미 사용 중인 아이디입니다.')
        const record: UserRecord = {
          id: takeId(data.counters, 'u'),
          loginId,
          name,
          role: input.role,
          status: 'active',
          email: null,
          createdAt: ctx.clock.now(),
          createdById: admin.id,
          lastLoginAt: null,
          resignedAt: null,
          resignReason: null,
        }
        data.users.push(record)
        return userView(data, record)
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
