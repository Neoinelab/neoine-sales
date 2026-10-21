import { afterEach, describe, expect, it, vi } from 'vitest'
import { json, problem, stubFetch } from './testHelpers'
import { createUsersHttp } from './users'

afterEach(() => vi.unstubAllGlobals())

/** 서버 UserRef 응답 조각. 서버는 모든 UserRef에 role을 담는다(P1 AC-02). */
function refWithRole(id: number, name: string, role: 'admin' | 'sales' | 'user', resigned = false) {
  return { id, name, label: resigned ? `${name}(퇴사)` : name, resigned, role }
}

const userRefBody = (id: number, name: string, resigned = false) => refWithRole(id, name, 'admin', resigned)

const row = (over: Record<string, unknown> = {}) => ({
  id: 2,
  login_id: 'park',
  display_name: '박영업',
  email: 'park@corp.test',
  role: 'sales',
  status: 'active',
  created_at: '2026-10-01T09:00:00+09:00',
  created_by: userRefBody(1, '최관리'),
  last_login_at: null,
  deleted_at: null,
  delete_reason: null,
  ...over,
})

describe('users over HTTP', () => {
  it('list reads GET /users with the status and the maximum page size', async () => {
    const { calls } = stubFetch(json({ items: [row()], offset: 0, limit: 200 }))

    const users = await createUsersHttp().list('resigned')

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/users?status=resigned&limit=200' })
    expect(users).toEqual([
      {
        id: 2,
        loginId: 'park',
        name: '박영업',
        role: 'sales',
        status: 'active',
        email: 'park@corp.test',
        createdAt: '2026-10-01T09:00:00+09:00',
        createdBy: { id: 1, name: '최관리', role: 'admin', status: 'active' },
        lastLoginAt: null,
        resignedAt: null,
        resignReason: null,
      },
    ])
  })

  it('shows the login id when the user has no display name yet', async () => {
    stubFetch(json({ items: [row({ display_name: null })], offset: 0, limit: 200 }))

    const [user] = await createUsersHttp().list('all')

    expect(user?.name).toBe('park')
  })

  it('maps a resigned user with the resign time and the reason', async () => {
    stubFetch(
      json({
        items: [row({ status: 'resigned', deleted_at: '2026-10-10T18:00:00+09:00', delete_reason: 'resigned', created_by: userRefBody(1, '최관리', true) })],
        offset: 0,
        limit: 200,
      }),
    )

    const [user] = await createUsersHttp().list('all')

    expect(user).toMatchObject({ status: 'resigned', resignedAt: '2026-10-10T18:00:00+09:00', resignReason: '퇴사' })
    expect(user?.createdBy).toMatchObject({ status: 'resigned' })
  })

  it('options reads GET /user-options and includes resigned users on request', async () => {
    const { calls } = stubFetch(json({ items: [userRefBody(1, '최관리'), userRefBody(9, '강퇴사', true)] }))

    const options = await createUsersHttp().options({ includeResigned: true })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/user-options?include_resigned=true' })
    expect(options.map((o) => [o.id, o.name, o.status])).toEqual([
      [1, '최관리', 'active'],
      [9, '강퇴사', 'resigned'],
    ])
  })

  it('options with a role sends it as the role query', async () => {
    const { calls } = stubFetch(json({ items: [refWithRole(2, '박영업', 'sales')] }))

    const options = await createUsersHttp().options({ role: 'sales' })

    const url = new URL(calls[0]?.path ?? '', 'http://localhost')
    expect(calls[0]).toMatchObject({ method: 'GET' })
    expect(url.pathname).toBe('/api/v1/user-options')
    expect(url.searchParams.get('role')).toBe('sales')
    expect(url.searchParams.get('include_resigned')).toBe('false')
    expect(options).toEqual([{ id: 2, name: '박영업', role: 'sales', status: 'active' }])
  })

  it('options without a role does not send the role query', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createUsersHttp().options({})

    const url = new URL(calls[0]?.path ?? '', 'http://localhost')
    expect(url.searchParams.has('role')).toBe(false)
  })

  it('options with a role reads one request that carries the role and no offset', async () => {
    const full = Array.from({ length: 200 }, (_, i) => refWithRole(i + 1, `이름${i}`, 'sales'))
    const { calls } = stubFetch(json({ items: full }))

    await createUsersHttp().options({ role: 'sales' })

    expect(calls).toHaveLength(1)
    const sent = new URL(calls[0]?.path ?? '', 'http://localhost').searchParams
    expect(sent.get('role')).toBe('sales')
    expect(sent.has('offset')).toBe(false)
    expect(sent.has('limit')).toBe(false)
  })

  it('options maps the server role of each user, resigned ones included', async () => {
    stubFetch(
      json({
        items: [refWithRole(1, '최관리', 'admin'), refWithRole(3, '조회', 'user'), refWithRole(9, '강퇴사', 'sales', true)],
      }),
    )

    const options = await createUsersHttp().options({ includeResigned: true })

    expect(options.map((o) => [o.id, o.role, o.status])).toEqual([
      [1, 'admin', 'active'],
      [3, 'user', 'active'],
      [9, 'sales', 'resigned'],
    ])
  })

  it('list keeps reading the next page while a full page comes back', async () => {
    const full = Array.from({ length: 200 }, (_, i) => row({ id: `u${i}`, login_id: `id${i}` }))
    const { calls } = stubFetch(
      json({ items: full, offset: 0, limit: 200 }),
      json({ items: [row({ id: 999, login_id: 'last' })], offset: 200, limit: 200 }),
    )

    const users = await createUsersHttp().list('all')

    expect(users).toHaveLength(201)
    expect(users.at(-1)?.id).toBe(999)
    expect(calls.map((c) => c.path)).toEqual([
      '/api/v1/users?status=all&limit=200',
      '/api/v1/users?status=all&limit=200&offset=200',
    ])
  })

  // 서버 /user-options는 offset을 모른다(쿼리: include_resigned, keyword, role; limit도 없다). 보내면 422다.
  it('options never sends an offset, because the server does not know it', async () => {
    const full = Array.from({ length: 200 }, (_, i) => userRefBody(i + 1, `이름${i}`))
    const { calls } = stubFetch(json({ items: full }))

    await createUsersHttp().options({})

    expect(calls).toHaveLength(1)
    expect(calls.every((c) => !new URL(c.path, 'http://localhost').searchParams.has('offset'))).toBe(true)
    expect(calls.every((c) => !new URL(c.path, 'http://localhost').searchParams.has('limit'))).toBe(true)
  })

  it('options returns every user of a single request without sending a limit', async () => {
    const full = Array.from({ length: 250 }, (_, i) => userRefBody(i + 1, `이름${i}`))
    const { calls } = stubFetch(json({ items: full }))

    const options = await createUsersHttp().options({})

    expect(options).toHaveLength(250)
    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/user-options?include_resigned=false')
  })

  it('create sends the name as display_name', async () => {
    const { calls } = stubFetch(json(row(), 201))

    const user = await createUsersHttp().create({ loginId: 'park', name: '박영업', role: 'sales' })

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/users', body: { login_id: 'park', role: 'sales', display_name: '박영업' } })
    expect(user.name).toBe('박영업')
  })

  it('create shows the server message for a duplicate login id', async () => {
    stubFetch(problem(409, 'already-exists', '이미 사용 중인 아이디입니다.'))

    await expect(createUsersHttp().create({ loginId: 'park', name: '박', role: 'sales' })).rejects.toMatchObject({
      kind: 'conflict',
      message: '이미 사용 중인 아이디입니다.',
    })
  })

  it.each(['deleted', 'resigned'] as const)('remove returns the outcome %s', async (outcome) => {
    const { calls } = stubFetch(json({ outcome }))

    await expect(createUsersHttp().remove(2)).resolves.toEqual({ outcome })

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/users/2' })
  })

  it('remove shows the server message for deleting yourself', async () => {
    stubFetch(problem(403, 'forbidden', '본인 계정은 삭제할 수 없습니다.'))

    await expect(createUsersHttp().remove(1)).rejects.toMatchObject({ status: 403, message: '본인 계정은 삭제할 수 없습니다.' })
  })
})
