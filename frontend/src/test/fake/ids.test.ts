import { describe, expect, it } from 'vitest'
import { newMock, expectApiError, mockAs } from './testing'
import { USER_ID } from './seed/ids'
import { takeId } from './store'

/** Fake가 서버(BIGINT id)처럼 양의 안전 정수를 쓰고, 종류마다 1씩 커지는지 고정한다. */
describe('Fake 게이트웨이의 정수 id', () => {
  it('takeId counts up from 1 per kind', () => {
    const counters: Record<string, number> = {}

    expect([takeId(counters, 'vd'), takeId(counters, 'vd'), takeId(counters, 'sl')]).toEqual([1, 2, 1])
  })

  it('seed users keep the fixed ids of USER_ID', async () => {
    const { gateway } = await mockAs('root')

    const users = await gateway.users.list('all')

    expect(users.map((u) => [u.loginId, u.id])).toEqual(
      expect.arrayContaining(Object.entries(USER_ID).map(([loginId, id]) => [loginId, id])),
    )
  })

  it('a new vendor gets an integer id larger than every seeded vendor id', async () => {
    const { gateway } = await mockAs('root')
    const before = await gateway.vendors.list()

    const created = await gateway.vendors.create('Brand New Vendor')

    expect(Number.isSafeInteger(created.id)).toBe(true)
    expect(created.id).toBeGreaterThan(Math.max(...before.map((v) => v.id)))
  })

  it('a new user gets the next integer after the seeded users', async () => {
    const { gateway } = await mockAs('root')

    const created = await gateway.users.create({ loginId: 'newbie', name: '신입', role: 'sales' })

    expect(created.id).toBe(Object.keys(USER_ID).length + 1)
  })

  it('a new contact and a new action type get positive integer ids', async () => {
    const { gateway } = await mockAs('root')

    const type = await gateway.actionTypes.create('웨비나')
    const contact = await gateway.contacts.create('customer', { company: '신규상사', name: '김신규', title: '', email: null, phone: null })

    expect(Number.isSafeInteger(type.id) && type.id > 0).toBe(true)
    expect(Number.isSafeInteger(contact.id) && contact.id > 0).toBe(true)
  })

  it('a session that was kept in sessionStorage as text is restored as the numeric user id', async () => {
    window.sessionStorage.setItem('neoine-mock-user-id', String(USER_ID.kim))

    const mock = newMock({ persistSession: true })

    expect((await mock.gateway.auth.me()).id).toBe(USER_ID.kim)
  })

  it('an id that no row has is a 404, not a type error', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.remove(Number.MAX_SAFE_INTEGER), 404)
  })
})
