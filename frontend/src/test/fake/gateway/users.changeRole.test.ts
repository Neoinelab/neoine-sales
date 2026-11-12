import { describe, expect, it } from 'vitest'
import type { Role } from '../../../shared/model/types'
import { expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

/** 서버 `PUT /users/{id}/role`과 같은 문구·판정 순서(401 → 403 → 422 → 404 → 409). */
const SELF = '자기 자신의 역할은 바꿀 수 없습니다.'
const RESIGNED = '이미 퇴사 처리된 사용자입니다'

const roleOf = async (gw: Awaited<ReturnType<typeof mockAs>>['gateway'], id: number) =>
  (await gw.users.list('all')).find((u) => u.id === id)?.role

describe('users.changeRole', () => {
  // 역할을 바꾸면 바뀐 사용자가 돌아오고 목록에 반영된다
  it('updates the role and returns the changed user', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when: kim의 역할을 user로 바꾼다
    const changed = await gateway.users.changeRole(USER_ID.kim, 'user')

    // then: 응답과 목록의 역할이 user다
    expect(changed).toMatchObject({ id: USER_ID.kim, loginId: 'kim', role: 'user' })
    expect(await roleOf(gateway, USER_ID.kim)).toBe('user')
  })

  // 바뀐 역할은 다시 로그인하지 않아도 다음 요청부터 적용된다
  it('applies the new role to the target on the next request without a new login', async () => {
    // given: admin이 kim을 admin으로 올렸다
    const mock = await mockAs('root')
    const { gateway } = mock
    await gateway.users.changeRole(USER_ID.kim, 'admin')

    // when: kim으로 전환해 본인과 사용자 목록을 읽는다
    await mock.signInAs(USER_ID.kim)

    // then: 본인 역할이 admin이고 목록 조회가 된다
    expect((await gateway.auth.me()).role).toBe('admin')
    await expect(gateway.users.list('all')).resolves.toBeInstanceOf(Array)
  })

  // sales였던 사용자는 sales Owner 후보에서 빠진다
  it('drops a former sales user from the sales owner options', async () => {
    // given: admin이 kim을 user로 바꿨다
    const { gateway } = await mockAs('root')
    await gateway.users.changeRole(USER_ID.kim, 'user')

    const sales = await gateway.users.options({ role: 'sales' })

    // when: sales 옵션을 읽는다
    const actual = sales.map((u) => u.id)

    // then: kim이 없다
    expect(actual).not.toContain(USER_ID.kim)
  })

  // sales였던 사용자의 Deal은 그대로 남는다
  it('keeps the deals owned by a former sales user', async () => {
    // given: kim이 Deal을 가지고 있다
    const { gateway } = await mockAs('root')

    const before = (await gateway.deals.list({ ownerId: USER_ID.kim, limit: 200 })).total
    expect(before).toBeGreaterThan(0)

    // when: kim을 user로 바꾼다
    await gateway.users.changeRole(USER_ID.kim, 'user')

    // then: kim 소유 Deal 수가 그대로다
    expect((await gateway.deals.list({ ownerId: USER_ID.kim, limit: 200 })).total).toBe(before)
  })

  // 같은 역할로 바꾸면 사용자가 그대로 돌아온다
  it('returns the user unchanged for the same role', async () => {
    // given: kim은 sales다
    const { gateway } = await mockAs('root')
    const before = (await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)

    // when: sales로 바꾼다
    const same = await gateway.users.changeRole(USER_ID.kim, 'sales')

    // then: 응답이 바뀌기 전 사용자와 같다
    expect(same).toEqual(before)
  })

  // 자기 자신의 역할은 409로 거절된다
  it('rejects oneself with 409', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 자기 역할을 바꾼다 → 409 문구이고 역할은 admin 그대로다
    await expectApiError(gateway.users.changeRole(USER_ID.root, 'user'), 409, SELF)
    expect(await roleOf(gateway, USER_ID.root)).toBe('admin')
  })

  // 다른 admin이 있는 동안 admin도 강등할 수 있다
  it('allows demoting another admin while the signed-in admin remains', async () => {
    // given: admin이 다른 admin을 만들었다
    const { gateway } = await mockAs('root')
    const boss = await gateway.users.create({ loginId: 'boss', name: '관리자2', role: 'admin' })

    // when: 그 admin을 sales로 바꾼다
    const result = await gateway.users.changeRole(boss.id, 'sales')
    // then: 역할이 sales다
    expect(result).toMatchObject({ role: 'sales' })
  })

  // 퇴사자의 역할 변경은 409다
  it('rejects a resigned user with 409', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 퇴사자의 역할을 바꾼다 → 퇴사 문구의 409다
    await expectApiError(gateway.users.changeRole(USER_ID.old, 'user'), 409, RESIGNED)
  })

  // 예약이 아닌 dev- 사용자는 일반 사용자로 역할이 바뀐다
  it.each(['dev-ops', 'dev-qa'])('changes the role of the ordinary user %s (not a reserved id)', async (loginId) => {
    // given: dev-ops 같은 사용자를 등록했다
    const { gateway } = await mockAs('root')

    // when: user로 바꾼다
    const user = await gateway.users.create({ loginId, name: '일반 사용자', role: 'sales' })

    // then: 역할이 user로 바뀌고 목록에도 같다
    await expect(gateway.users.changeRole(user.id, 'user')).resolves.toMatchObject({ role: 'user' })
    expect(await roleOf(gateway, user.id)).toBe('user')
  })

  // 없는 사용자는 404다
  it('returns 404 for an unknown user', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 없는 id의 역할을 바꾼다 → 사용자를 찾을 수 없다는 404다
    await expectApiError(
      gateway.users.changeRole(NO_SUCH_ID, 'user'),
      404,
      `사용자을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`,
    )
  })

  // admin·sales·user 밖의 역할은 422이고 그대로다
  it('returns 422 for a role outside admin, sales and user', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: owner 같은 알 수 없는 역할로 바꾼다 → 422이고 kim 역할은 sales 그대로다
    await expectApiError(gateway.users.changeRole(USER_ID.kim, 'owner' as Role), 422, '역할을 선택하세요.')
    expect(await roleOf(gateway, USER_ID.kim)).toBe('sales')
  })

  // sales·user는 403, 로그인하지 않으면 401이다
  it('returns 403 for sales and user, and 401 without login', async () => {
    // given: sales, user, 비로그인 세션이 있다
    const sales = await mockAs('kim')

    // when·then: 각자 역할 변경을 요청한다 → sales·user는 403, 비로그인은 401이다
    await expectApiError(sales.gateway.users.changeRole(USER_ID.park, 'user'), 403)
    const viewer = await mockAs('han')
    await expectApiError(viewer.gateway.users.changeRole(USER_ID.park, 'user'), 403)
    const anonymous = await mockAs(null)
    await expectApiError(anonymous.gateway.users.changeRole(USER_ID.park, 'user'), 401)
  })
})
