import { describe, expect, it } from 'vitest'
import type { Role } from '../../../shared/model/types'
import { expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

/** 서버 `PUT /users/{id}/role`과 같은 문구·판정 순서(401 → 403 → 422 → 404 → 409). */
const SELF = '자기 자신의 역할은 바꿀 수 없습니다.'
const RESIGNED = '이미 퇴사 처리된 사용자입니다.'
const DEV_ONLY = '개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다.'

const roleOf = async (gw: Awaited<ReturnType<typeof mockAs>>['gateway'], id: number) =>
  (await gw.users.list('all')).find((u) => u.id === id)?.role

describe('users.changeRole', () => {
  it('updates the role and returns the changed user', async () => {
    const { gateway } = await mockAs('root')

    const changed = await gateway.users.changeRole(USER_ID.kim, 'user')

    expect(changed).toMatchObject({ id: USER_ID.kim, loginId: 'kim', role: 'user' })
    expect(await roleOf(gateway, USER_ID.kim)).toBe('user')
  })

  it('applies the new role to the target on the next request without a new login', async () => {
    const { gateway } = await mockAs('root')
    await gateway.users.changeRole(USER_ID.kim, 'admin')
    await gateway.auth.quickLogin(USER_ID.kim)

    expect((await gateway.auth.me()).role).toBe('admin')
    await expect(gateway.users.list('all')).resolves.toBeInstanceOf(Array)
  })

  it('drops a former sales user from the sales owner options', async () => {
    const { gateway } = await mockAs('root')
    await gateway.users.changeRole(USER_ID.kim, 'user')

    const sales = await gateway.users.options({ role: 'sales' })

    expect(sales.map((u) => u.id)).not.toContain(USER_ID.kim)
  })

  it('keeps the deals owned by a former sales user', async () => {
    const { gateway } = await mockAs('root')
    const before = (await gateway.deals.list({ ownerId: USER_ID.kim, limit: 200 })).total
    expect(before).toBeGreaterThan(0)

    await gateway.users.changeRole(USER_ID.kim, 'user')

    expect((await gateway.deals.list({ ownerId: USER_ID.kim, limit: 200 })).total).toBe(before)
  })

  it('returns the user unchanged for the same role', async () => {
    const { gateway } = await mockAs('root')
    const before = (await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)

    const same = await gateway.users.changeRole(USER_ID.kim, 'sales')

    expect(same).toEqual(before)
  })

  it('rejects oneself with 409', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.changeRole(USER_ID.root, 'user'), 409, SELF)
    expect(await roleOf(gateway, USER_ID.root)).toBe('admin')
  })

  it('allows demoting another admin while the signed-in admin remains', async () => {
    const { gateway } = await mockAs('root')
    const boss = await gateway.users.create({ loginId: 'boss', name: '관리자2', role: 'admin' })

    await expect(gateway.users.changeRole(boss.id, 'sales')).resolves.toMatchObject({ role: 'sales' })
  })

  it('rejects a resigned user with 409', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.changeRole(USER_ID.old, 'user'), 409, RESIGNED)
  })

  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the dev login user %s with 409', async (loginId) => {
    const { gateway } = await mockAs('root')
    const dev = await gateway.users.create({ loginId, name: '개발 사용자', role: 'sales' })

    await expectApiError(gateway.users.changeRole(dev.id, 'user'), 409, DEV_ONLY)
    expect(await roleOf(gateway, dev.id)).toBe('sales')
  })

  it('returns 404 for an unknown user', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.changeRole(NO_SUCH_ID, 'user'), 404, '사용자를 찾을 수 없습니다.')
  })

  it('returns 422 for a role outside admin, sales and user', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.changeRole(USER_ID.kim, 'owner' as Role), 422, '역할을 선택하세요.')
    expect(await roleOf(gateway, USER_ID.kim)).toBe('sales')
  })

  it('returns 403 for sales and user, and 401 without login', async () => {
    const sales = await mockAs('kim')
    await expectApiError(sales.gateway.users.changeRole(USER_ID.park, 'user'), 403)
    const viewer = await mockAs('han')
    await expectApiError(viewer.gateway.users.changeRole(USER_ID.park, 'user'), 403)
    const anonymous = await mockAs(null)
    await expectApiError(anonymous.gateway.users.changeRole(USER_ID.park, 'user'), 401)
  })
})
