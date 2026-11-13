import { afterEach, describe, expect, it, vi } from 'vitest'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { createUsersHttp } from './users'

afterEach(() => vi.unstubAllGlobals())

/** 서버 UserRef 응답 조각. 서버는 모든 UserRef에 role을 담는다. */
function refWithRole(id: number, name: string, role: 'admin' | 'sales' | 'user', resigned = false) {
  return { id, name, label: resigned ? `${name}(퇴사)` : name, resigned, role }
}

const userRefBody = (id: number, name: string, resigned = false) => refWithRole(id, name, 'admin', resigned)

const row = (over: Record<string, unknown> = {}) => ({
  id: 2,
  login_id: 'park',
  display_name: '박영업',
  email: 'park@corp.test',
  phone: null,
  role: 'sales',
  status: 'active',
  created_at: '2026-10-01T09:00:00+09:00',
  last_login_at: null,
  deleted_at: null,
  ...over,
})

describe('users over HTTP', () => {
  // 목록은 GET /users를 최대 페이지 크기로 읽고 화면 값으로 바꾼다
  // 테스트 코드: US-108, US-110
  it('list reads GET /users with the status and the maximum page size', async () => {
    // given: 서버 사용자 응답
    const { calls } = stubFetch(json({ items: [row()], offset: 0, limit: 200 }))

    // when: 퇴사 상태로 목록을 읽는다
    const users = await createUsersHttp().list('resigned')

    // then: 요청 경로와 변환된 사용자 값이 계약과 같다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/users?status=resigned&limit=200' })
    expect(users).toEqual([
      {
        id: 2,
        loginId: 'park',
        name: '박영업',
        role: 'sales',
        status: 'active',
        email: 'park@corp.test',
        phone: null,
        createdAt: '2026-10-01T09:00:00+09:00',
        lastLoginAt: null,
        resignedAt: null,
      },
    ])
    // then: 등록자·퇴사 사유 키는 만들지 않는다
    expect(users[0]).not.toHaveProperty('createdBy')
    expect(users[0]).not.toHaveProperty('resignReason')
  })

  // 표시 이름이 없으면 아이디를 이름으로 보인다
  // 테스트 코드: US-110
  it('shows the login id when the user has no display name yet', async () => {
    // given: 표시 이름이 없는 응답
    stubFetch(json({ items: [row({ display_name: null })], offset: 0, limit: 200 }))

    // when: 목록을 읽는다
    const [user] = await createUsersHttp().list('all')

    // then: 이름이 아이디다
    expect(user?.name).toBe('park')
  })

  // 퇴사 사용자는 퇴사 시각으로 변환되고 퇴사 사유는 만들지 않는다
  // 테스트 코드: US-110
  it('maps a resigned user with the resign time and no reason', async () => {
    // given: 퇴사 사용자 응답
    stubFetch(
      json({
        items: [row({ status: 'resigned', deleted_at: '2026-10-10T18:00:00+09:00' })],
        offset: 0,
        limit: 200,
      }),
    )

    // when: 목록을 읽는다
    const [user] = await createUsersHttp().list('all')

    // then: 퇴사 상태·시각으로 변환되고 퇴사 사유 키는 없다
    expect(user).toMatchObject({ status: 'resigned', resignedAt: '2026-10-10T18:00:00+09:00' })
    expect(user).not.toHaveProperty('resignReason')
  })

  // 선택 목록은 GET /user-options를 한 번 읽고 퇴사자를 요청에 따라 더한다
  // 테스트 코드: US-109
  it('options reads GET /user-options and includes resigned users on request', async () => {
    // given: 재직·퇴사 참조 응답
    const { calls } = stubFetch(json({ items: [userRefBody(1, '최관리'), userRefBody(9, '강퇴사', true)] }))

    // when: include_resigned로 읽는다
    const options = await createUsersHttp().options({ includeResigned: true })

    // then: 경로가 계약과 같고 두 사용자가 변환된다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/user-options?include_resigned=true' })
    expect(options.map((o) => [o.id, o.name, o.status])).toEqual([
      [1, '최관리', 'active'],
      [9, '강퇴사', 'resigned'],
    ])
  })

  // role이 있으면 role 쿼리로 보내고 페이지 값은 보내지 않는다
  // 테스트 코드: US-109
  it('options with a role sends it as the role query', async () => {
    // given: sales 참조 응답
    const { calls } = stubFetch(json({ items: [refWithRole(2, '박영업', 'sales')] }))

    // when: role을 주고 읽는다
    const options = await createUsersHttp().options({ role: 'sales' })

    const url = new URL(calls[0]?.path ?? '', 'http://localhost')
    // then: role·include_resigned 쿼리가 맞게 간다
    expect(calls[0]).toMatchObject({ method: 'GET' })
    expect(url.pathname).toBe('/api/v1/user-options')
    expect(url.searchParams.get('role')).toBe('sales')
    expect(url.searchParams.get('include_resigned')).toBe('false')
    expect(options).toEqual([{ id: 2, name: '박영업', role: 'sales', status: 'active' }])
  })

  // role이 없으면 role 쿼리를 보내지 않는다
  // 테스트 코드: US-109
  it('options without a role does not send the role query', async () => {
    // given: 빈 응답
    const { calls } = stubFetch(json({ items: [] }))

    // when: role 없이 읽는다
    await createUsersHttp().options({})

    const url = new URL(calls[0]?.path ?? '', 'http://localhost')
    // then: role 쿼리가 없다
    expect(url.searchParams.has('role')).toBe(false)
  })

  // 가득 찬 응답이 와도 선택 목록은 요청 한 번이고 offset·limit이 없다
  // 테스트 코드: US-109
  it('options with a role reads one request that carries the role and no offset', async () => {
    // given: 200개 응답
    const full = Array.from({ length: 200 }, (_, i) => refWithRole(i + 1, `이름${i}`, 'sales'))
    const { calls } = stubFetch(json({ items: full }))

    // when: role을 주고 읽는다
    await createUsersHttp().options({ role: 'sales' })

    // then: 요청이 한 번이고 offset·limit이 없다
    expect(calls).toHaveLength(1)
    const sent = new URL(calls[0]?.path ?? '', 'http://localhost').searchParams
    expect(sent.get('role')).toBe('sales')
    expect(sent.has('offset')).toBe(false)
    expect(sent.has('limit')).toBe(false)
  })

  // 선택 목록은 서버 역할을 그대로 쓴다(퇴사자 포함)
  // 테스트 코드: US-110
  it('options maps the server role of each user, resigned ones included', async () => {
    // given: 역할이 다른 참조 응답
    stubFetch(
      json({
        items: [refWithRole(1, '최관리', 'admin'), refWithRole(3, '조회', 'user'), refWithRole(9, '강퇴사', 'sales', true)],
      }),
    )

    // when: 퇴사자 포함으로 읽는다
    const options = await createUsersHttp().options({ includeResigned: true })

    // then: 역할과 상태가 서버 값 그대로다
    expect(options.map((o) => [o.id, o.role, o.status])).toEqual([
      [1, 'admin', 'active'],
      [3, 'user', 'active'],
      [9, 'sales', 'resigned'],
    ])
  })

  // 목록은 가득 찬 페이지가 오는 동안 이어 읽는다
  // 테스트 코드: US-108
  it('list keeps reading the next page while a full page comes back', async () => {
    // given: 200개 페이지와 1개 페이지 응답
    const full = Array.from({ length: 200 }, (_, i) => row({ id: `u${i}`, login_id: `id${i}` }))
    const { calls } = stubFetch(
      json({ items: full, offset: 0, limit: 200 }),
      json({ items: [row({ id: 999, login_id: 'last' })], offset: 200, limit: 200 }),
    )

    // when: 전체 목록을 읽는다
    const users = await createUsersHttp().list('all')

    // then: 201명을 돌려주고 offset을 늘려 두 번 읽는다
    expect(users).toHaveLength(201)
    expect(users.at(-1)?.id).toBe(999)
    expect(calls.map((c) => c.path)).toEqual([
      '/api/v1/users?status=all&limit=200',
      '/api/v1/users?status=all&limit=200&offset=200',
    ])
  })

  // 서버 /user-options는 offset을 모른다(쿼리: include_resigned, keyword, role; limit도 없다). 보내면 422다.
  // 선택 목록은 offset·limit을 보내지 않는다
  // 테스트 코드: US-109
  it('options never sends an offset, because the server does not know it', async () => {
    // given: 200개 응답
    const full = Array.from({ length: 200 }, (_, i) => userRefBody(i + 1, `이름${i}`))
    const { calls } = stubFetch(json({ items: full }))

    // when: 읽는다
    await createUsersHttp().options({})

    // then: 요청에 offset·limit이 없다
    expect(calls).toHaveLength(1)
    expect(calls.every((c) => !new URL(c.path, 'http://localhost').searchParams.has('offset'))).toBe(true)
    expect(calls.every((c) => !new URL(c.path, 'http://localhost').searchParams.has('limit'))).toBe(true)
  })

  // 선택 목록은 한 번 요청해 받은 사용자를 모두 돌려준다
  // 테스트 코드: US-109
  it('options returns every user of a single request without sending a limit', async () => {
    // given: 250개 응답
    const full = Array.from({ length: 250 }, (_, i) => userRefBody(i + 1, `이름${i}`))
    const { calls } = stubFetch(json({ items: full }))

    // when: 읽는다
    const options = await createUsersHttp().options({})

    // then: 250명을 돌려주고 요청은 한 번이다
    expect(options).toHaveLength(250)
    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/user-options?include_resigned=false')
  })

  // 등록 요청은 이름을 display_name으로 보낸다
  // 테스트 코드: US-111
  it('create sends the name as display_name', async () => {
    // given: 201 응답
    const { calls } = stubFetch(json(row(), 201))

    // when: 사용자를 등록한다
    const user = await createUsersHttp().create({ loginId: 'park', name: '박영업', role: 'sales' })

    // then: POST /users 본문이 계약과 같다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/users', body: { login_id: 'park', role: 'sales', display_name: '박영업' } })
    expect(user.name).toBe('박영업')
  })

  // 응답의 전화번호가 화면 값으로 변환된다
  // 테스트 코드: US-110
  it('maps the phone of a user', async () => {
    // given: 전화번호가 있는 응답
    stubFetch(json({ items: [row({ phone: '02-123-4567' })], offset: 0, limit: 200 }))

    // when: 목록을 읽는다
    const [user] = await createUsersHttp().list('all')

    // then: 전화번호가 그대로다
    expect(user?.phone).toBe('02-123-4567')
  })

  // local 등록 요청은 비밀번호·이메일·전화를 보낸다
  // 테스트 코드: US-111
  it('create sends the password, email and phone of a local user', async () => {
    // given: 201 응답
    const { calls } = stubFetch(json(row({ phone: '010-1234-5678' }), 201))

    // when: 모든 값을 넣어 등록한다
    const user = await createUsersHttp().create({
      loginId: 'park',
      name: '박영업',
      role: 'sales',
      password: 'Passw0rd-ok',
      email: 'park@corp.test',
      phone: '010-1234-5678',
    })

    // then: 본문에 비밀번호·이메일·전화가 있다
    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: '/api/v1/users',
      body: {
        login_id: 'park',
        role: 'sales',
        display_name: '박영업',
        password: 'Passw0rd-ok',
        email: 'park@corp.test',
        phone: '010-1234-5678',
      },
    })
    expect(user.phone).toBe('010-1234-5678')
  })

  // 비밀번호·빈 이메일·빈 전화는 요청 본문에서 뺀다
  // 테스트 코드: US-111
  it('create leaves out the password, an empty email and an empty phone', async () => {
    // given: 201 응답
    const { calls } = stubFetch(json(row(), 201))

    // when: 이메일·전화 null로 등록한다
    await createUsersHttp().create({ loginId: 'park', name: '박영업', role: 'sales', email: null, phone: null })

    // then: 본문이 아이디·역할·이름뿐이다
    expect(calls[0]?.body).toEqual({ login_id: 'park', role: 'sales', display_name: '박영업' })
  })

  // 약한 비밀번호 거절은 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it('create shows the server message for a weak password', async () => {
    // given: 422 응답
    stubFetch(problem(422, 'invalid-value', '비밀번호는 8자 이상이어야 합니다'))

    // when·then: 약한 비밀번호로 등록한다 → validation 오류와 서버 문구다
    await expect(createUsersHttp().create({ loginId: 'park', name: '박', role: 'sales', password: 'short' })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '비밀번호는 8자 이상이어야 합니다',
    })
  })

  // 중복 아이디 거절은 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it('create shows the server message for a duplicate login id', async () => {
    // given: 409 응답
    stubFetch(problem(409, 'already-exists', '이미 존재하는 사용자입니다: park'))

    // when·then: 중복 아이디로 등록한다 → conflict 오류와 서버 문구다
    await expect(createUsersHttp().create({ loginId: 'park', name: '박', role: 'sales' })).rejects.toMatchObject({
      kind: 'conflict',
      message: '이미 존재하는 사용자입니다: park',
    })
  })

  // 삭제는 서버가 알려 준 결과(deleted·resigned)를 돌려준다
  // 테스트 코드: US-111
  it.each(['deleted', 'resigned'] as const)('remove returns the outcome %s', async (outcome) => {
    // given: 삭제 결과 응답
    const { calls } = stubFetch(json({ outcome }))

    // when: 사용자를 삭제한다
    const result = await createUsersHttp().remove(2)
    // then: 결과가 그대로다
    expect(result).toEqual({ outcome })

    // then: 요청이 쿼리 없는 DELETE /users/{id}이다
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/users/2' })
  })

  // 자기 삭제 거절은 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it('remove shows the server message for deleting yourself', async () => {
    // given: 409 응답
    stubFetch(problem(409, 'invalid-state', '자기 자신은 삭제할 수 없습니다'))

    // when·then: 자기 자신을 삭제한다 → 상태 409와 서버 문구다
    await expect(createUsersHttp().remove(1)).rejects.toMatchObject({ status: 409, message: '자기 자신은 삭제할 수 없습니다' })
  })

  // 역할 변경은 PUT /users/{id}/role로 보내고 사용자를 변환한다
  // 테스트 코드: US-111
  it('changeRole sends PUT /users/{id}/role with the role body and maps the user', async () => {
    // given: 200 응답
    const { calls } = stubFetch(json(row({ role: 'user' })))

    // when: 역할을 바꾼다
    const changed = await createUsersHttp().changeRole(2, 'user')

    // then: 요청이 계약과 같고 변환된 사용자가 돌아온다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/users/2/role', body: { role: 'user' } })
    expect(changed).toMatchObject({ id: 2, loginId: 'park', role: 'user', status: 'active' })
  })

  // 거절 응답은 상태와 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it.each([
    [409, 'invalid-state', '자기 자신의 역할은 바꿀 수 없습니다.', 'conflict'],
    [409, 'invalid-state', '마지막 관리자의 역할은 바꿀 수 없습니다.', 'conflict'],
    [409, 'invalid-state', '이미 퇴사 처리된 사용자입니다', 'conflict'],
    [403, 'forbidden', '이 작업을 할 권한이 없습니다.', 'forbidden'],
    [404, 'not-found', '사용자를 찾을 수 없습니다.', 'not-found'],
  ])('changeRole shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 거절 응답
    stubFetch(problem(status, serverKind, detail))

    // when·then: 요청을 보낸다 → 상태·종류·서버 문구가 그대로다
    await expect(createUsersHttp().changeRole(2, 'user')).rejects.toMatchObject({ status, kind, message: detail })
  })

  // 정보 수정은 준 키만 PATCH로 보낸다
  // 테스트 코드: US-111
  it('update sends PATCH /users/{id} with only the given fields and maps the user', async () => {
    // given: 200 응답
    const { calls } = stubFetch(json(row({ display_name: '박새이름', phone: '02-123-4567' })))

    // when: 이름·전화를 수정한다
    const changed = await createUsersHttp().update(2, { name: '박새이름', phone: '02-123-4567' })

    // then: 본문 키가 두 개뿐이고 변환된 사용자가 돌아온다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({
      method: 'PATCH',
      path: '/api/v1/users/2',
      body: { display_name: '박새이름', phone: '02-123-4567' },
    })
    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(['display_name', 'phone'])
    expect(changed).toMatchObject({ id: 2, name: '박새이름', phone: '02-123-4567' })
  })

  // null은 비움으로 보내고 생략한 키는 보내지 않는다
  // 테스트 코드: US-111
  it('update sends null to clear a field and nothing for an omitted one', async () => {
    // given: 200 응답
    const { calls } = stubFetch(json(row({ email: null })))

    // when: 이메일을 null로 수정한다
    await createUsersHttp().update(2, { email: null })

    // then: 본문이 email null뿐이다
    expect(calls[0]?.body).toEqual({ email: null })
  })

  // 정보 수정 거절 응답은 상태와 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it.each([
    [409, 'invalid-state', 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다', 'conflict'],
    [409, 'invalid-state', '이미 퇴사 처리된 사용자입니다', 'conflict'],
    [422, 'invalid-value', '이메일 형식이 올바르지 않습니다.', 'validation'],
    [403, 'forbidden', '이 작업을 할 권한이 없습니다.', 'forbidden'],
    [404, 'not-found', '사용자를 찾을 수 없습니다.', 'not-found'],
  ])('update shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 거절 응답
    stubFetch(problem(status, serverKind, detail))

    // when·then: 정보 수정을 보낸다 → 상태·종류·서버 문구가 그대로다
    await expect(createUsersHttp().update(2, { name: 'x' })).rejects.toMatchObject({ status, kind, message: detail })
  })

  // 재설정은 PUT …/password로 보내고 204로 끝난다
  // 테스트 코드: US-111
  it('resetPassword sends PUT /users/{id}/password and resolves on 204', async () => {
    // given: 204 응답
    const { calls } = stubFetch(noContent())

    // when: 비밀번호를 재설정한다
    const result = await createUsersHttp().resetPassword(2, 'Fresh-passw0rd')
    // then: 값 없이 끝난다
    expect(result).toBeUndefined()

    // then: 요청이 계약과 같다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/users/2/password', body: { password: 'Fresh-passw0rd' } })
  })

  // 재설정 거절 응답은 상태와 서버 문구를 그대로 전달한다
  // 테스트 코드: US-111
  it.each([
    [409, 'invalid-state', '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.', 'conflict'],
    [422, 'invalid-value', '비밀번호는 8자 이상이어야 합니다', 'validation'],
    [404, 'not-found', '사용자를 찾을 수 없습니다.', 'not-found'],
    [403, 'forbidden', '이 작업을 할 권한이 없습니다.', 'forbidden'],
  ])('resetPassword shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 거절 응답
    stubFetch(problem(status, serverKind, detail))

    // when·then: 재설정을 보낸다 → 상태·종류·서버 문구가 그대로다
    await expect(createUsersHttp().resetPassword(2, 'x')).rejects.toMatchObject({ status, kind, message: detail })
  })
})
