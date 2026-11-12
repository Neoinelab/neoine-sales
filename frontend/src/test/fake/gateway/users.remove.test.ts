import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

/** 서버 `DELETE /users/{id}`와 같은 문구·판정 순서(404 → 이미 퇴사 409 → 자기 자신 409 → 마지막 관리자 409). */
const RESIGNED = '이미 퇴사 처리된 사용자입니다'
const SELF = '자기 자신은 삭제할 수 없습니다'

describe('users.remove', () => {
  // 퇴사자를 다시 삭제하면 서버와 같은 문구(마침표 없음)의 409다
  it('rejects an already resigned user with the server message (no trailing period)', async () => {
    // given: admin이고 old는 퇴사자다
    const { gateway } = await mockAs('root')

    // when·then: old를 삭제한다 → 마침표 없는 퇴사 문구의 409다
    await expectApiError(gateway.users.remove(USER_ID.old), 409, RESIGNED)
  })

  // 자기 자신은 연결 유무와 무관하게 삭제할 수 없다
  it('rejects deleting oneself with 409 and keeps the user active', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 자기 자신을 삭제한다 → 409이고 목록에 재직으로 남는다
    await expectApiError(gateway.users.remove(USER_ID.root), 409, SELF)
    const root = (await gateway.users.list('all')).find((u) => u.id === USER_ID.root)
    expect(root?.status).toBe('active')
  })

  // 없는 사용자는 404다
  it('returns 404 for an unknown user', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 없는 id를 삭제한다 → 404다
    await expectApiError(gateway.users.remove(NO_SUCH_ID), 404, `사용자을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`)
  })

  // 연결된 데이터가 있으면 퇴사 처리, 없으면 목록에서 사라진다
  it('resigns a linked user and deletes an unlinked one', async () => {
    // given: kim은 Deal을 갖고 있고 새로 등록한 temp는 연결이 없다
    const { gateway } = await mockAs('root')
    const temp = await gateway.users.create({ loginId: 'temp', name: '임시', role: 'user' })

    // when: 둘을 삭제한다
    const linked = await gateway.users.remove(USER_ID.kim)
    const unlinked = await gateway.users.remove(temp.id)

    // then: kim은 퇴사로 남고 temp는 목록에서 사라진다
    expect([linked.outcome, unlinked.outcome]).toEqual(['resigned', 'deleted'])
    const all = await gateway.users.list('all')
    expect(all.find((u) => u.id === USER_ID.kim)?.status).toBe('resigned')
    expect(all.some((u) => u.id === temp.id)).toBe(false)
  })

  // 다른 관리자가 있는 동안 admin도 삭제할 수 있다
  it('allows deleting another admin while the signed-in admin remains', async () => {
    // given: admin이 다른 admin을 만들었다
    const { gateway } = await mockAs('root')
    const boss = await gateway.users.create({ loginId: 'boss', name: '관리자2', role: 'admin' })

    // when: 그 admin을 삭제한다
    const result = await gateway.users.remove(boss.id)

    // then: 연결이 없어 물리 삭제된다
    expect(result.outcome).toBe('deleted')
  })
})
