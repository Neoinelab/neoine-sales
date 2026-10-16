import { afterEach, describe, expect, it, vi } from 'vitest'
import { createContactsHttp } from './contacts'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const contact = (over: Record<string, unknown> = {}) => ({
  id: 'ct1',
  kind: 'customer',
  company: '네오인',
  name: '홍길동',
  title: null,
  email: null,
  phone: null,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-02T09:00:00+09:00',
  ...over,
})

describe('contacts over HTTP', () => {
  it('companies reads GET /contacts/companies for the kind', async () => {
    const { calls } = stubFetch(json(['네오인', '에이콘']))

    await expect(createContactsHttp().companies('customer')).resolves.toEqual(['네오인', '에이콘'])

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/contacts/companies?kind=customer' })
  })

  it('byCompany reads the people of one company with their Deal counts', async () => {
    const { calls } = stubFetch(json([{ ...contact({ title: '팀장', email: 'hong@neoine.test' }), deal_count: 2 }]))

    const rows = await createContactsHttp().byCompany('partner', '네오인')

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/contacts/by-company?kind=partner&company=${encodeURIComponent('네오인')}` })
    expect(rows[0]).toEqual({
      id: 'ct1',
      kind: 'customer',
      company: '네오인',
      name: '홍길동',
      title: '팀장',
      email: 'hong@neoine.test',
      phone: null,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
      dealCount: 2,
    })
  })

  it('maps a missing title to an empty string', async () => {
    stubFetch(json([{ ...contact(), deal_count: 0 }]))

    const [row] = await createContactsHttp().byCompany('customer', '네오인')

    expect(row?.title).toBe('')
  })

  it('list sends the filters and reads total from the page', async () => {
    const { calls } = stubFetch(json({ items: [{ ...contact(), deal_count: 1 }], total: 41, offset: 20, limit: 20 }))

    const page = await createContactsHttp().list({ kind: 'customer', keyword: '홍', offset: 20, limit: 20 })

    expect(calls[0]).toMatchObject({
      method: 'GET',
      path: `/api/v1/contacts?kind=customer&keyword=${encodeURIComponent('홍')}&offset=20&limit=20`,
    })
    expect(page).toMatchObject({ total: 41, offset: 20, limit: 20 })
    expect(page.items[0]).toMatchObject({ id: 'ct1', dealCount: 1 })
  })

  it('list omits the filters that are not set', async () => {
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 0, limit: 50 }))

    await createContactsHttp().list({})

    expect(calls[0]?.path).toBe('/api/v1/contacts')
  })

  it('list shows the 403 of a non-admin', async () => {
    stubFetch(problem(403, 'forbidden', '이 작업을 수행할 권한이 없습니다.'))

    await expect(createContactsHttp().list({})).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })

  it('create posts the kind with company, name, title, email and phone', async () => {
    const { calls } = stubFetch(json(contact({ title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' }), 201))

    const created = await createContactsHttp().create('customer', {
      company: '네오인',
      name: '홍길동',
      title: '팀장',
      email: 'hong@neoine.test',
      phone: '010-1234-5678',
    })

    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: '/api/v1/contacts',
      body: { kind: 'customer', company: '네오인', name: '홍길동', title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' },
    })
    expect(created).toMatchObject({ id: 'ct1', title: '팀장', phone: '010-1234-5678' })
  })

  it('create sends an empty title as null', async () => {
    const { calls } = stubFetch(json(contact(), 201))

    await createContactsHttp().create('partner', { company: 'A', name: 'B', title: '', email: null, phone: null })

    expect(calls[0]?.body).toEqual({ kind: 'partner', company: 'A', name: 'B', title: null, email: null, phone: null })
  })

  it.each([
    [409, 'already-exists', '이미 등록된 연락처입니다.', 'conflict'],
    [422, 'invalid-value', '공백은 입력할 수 없습니다.', 'validation'],
    [422, 'invalid-value', '이메일 형식이 올바르지 않습니다.', 'validation'],
    [422, 'invalid-value', '전화번호 형식이 올바르지 않습니다.', 'validation'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createContactsHttp().create('customer', { company: 'A', name: 'B', title: '', email: null, phone: null })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })

  it('update puts the fields without the kind', async () => {
    const { calls } = stubFetch(json(contact({ name: '김철수' })))

    const updated = await createContactsHttp().update('ct1', { company: '네오인', name: '김철수', title: '', email: null, phone: null })

    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/contacts/ct1', body: { company: '네오인', name: '김철수', title: null, email: null, phone: null } })
    expect(calls[0]?.body).not.toHaveProperty('kind')
    expect(updated.name).toBe('김철수')
  })

  it('remove deletes and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createContactsHttp().remove('ct1')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/contacts/ct1' })
  })

  it('remove shows the server message when Deals still use the contact', async () => {
    stubFetch(problem(409, 'invalid-state', '연결된 Deal이 2건 있어 삭제할 수 없습니다.'))

    await expect(createContactsHttp().remove('ct1')).rejects.toMatchObject({
      kind: 'conflict',
      message: '연결된 Deal이 2건 있어 삭제할 수 없습니다.',
    })
  })
})
