import { describe, expect, it } from 'vitest'
import { USER_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'

/** Fake 게이트웨이 Deal 목록의 담당자 이름 조건(DL-R39)과 담당자 id와의 동시 지정 오류(DL-R5). */
const BOTH_MESSAGE = '담당자는 사용자 id와 이름 중 하나로만 지정하세요.'
const ALL = { limit: 200 }

describe('deals.list: ownerName', () => {
  // 담당자 이름은 재직 담당자 화면 이름의 부분 일치이고 앞뒤 공백은 지우며 퇴사자는 걸리지 않는다.
  // 테스트 코드: DL-144
  it('matches active owners by a partial name and never matches the resigned owner by a part', async () => {
    // given: 재직 영업(김·박·이·정영업)과 퇴사한 강퇴사가 Deal을 가진 Fake
    const { gateway } = await mockAs('kim')

    // when: "영업"으로, 앞뒤 공백이 있는 " 영업 "으로, 퇴사자 이름 일부 "강퇴"로 찾는다
    const plain = await gateway.deals.list({ ...ALL, ownerName: '영업' })
    const spaced = await gateway.deals.list({ ...ALL, ownerName: ' 영업 ' })
    const part = await gateway.deals.list({ ...ALL, ownerName: '강퇴' })

    // then: 재직 영업 네 명의 Deal만 모이고 공백은 무시되며 퇴사자는 일부로 걸리지 않는다
    const owners = new Set(plain.items.map((row) => row.ownerId))
    expect(owners).toEqual(new Set([USER_ID.kim, USER_ID.park, USER_ID.lee, USER_ID.jung]))
    expect(plain.total).toBe(plain.items.length)
    expect(spaced.total).toBe(plain.total)
    expect(part.total).toBe(0)
  })

  // 한 사람의 이름 글자로 찾으면 그 사람의 Deal만 온다.
  // 테스트 코드: DL-144
  it('narrows to the owner whose name contains the typed letters', async () => {
    // given: 김영업·박영업이 Deal을 가진 Fake
    const { gateway } = await mockAs('kim')

    // when: "박영"으로 찾는다
    const result = await gateway.deals.list({ ...ALL, ownerName: '박영' })

    // then: 박영업의 Deal만 온다
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.items.every((row) => row.ownerId === USER_ID.park)).toBe(true)
  })

  // 퇴사자는 "이름(퇴사)"가 정확히 같을 때만 걸리고 덜 친·띄어 쓴·(퇴사) 없는 값은 걸리지 않는다.
  // 테스트 코드: DL-144
  it('matches the resigned owner only by the exact name followed by (퇴사)', async () => {
    // given: 퇴사한 강퇴사가 Deal 1건을 가진 Fake
    const { gateway } = await mockAs('kim')

    // when: 정확한 값, 덜 친 값, 띄어 쓴 값, (퇴사) 없는 값으로 찾는다
    const exact = await gateway.deals.list({ ...ALL, ownerName: '강퇴사(퇴사)' })
    const lower = await gateway.deals.list({ ...ALL, ownerName: '강퇴사(퇴' })
    const spaced = await gateway.deals.list({ ...ALL, ownerName: '강퇴사 (퇴사)' })
    const bare = await gateway.deals.list({ ...ALL, ownerName: '강퇴사' })

    // then: 정확한 값만 퇴사자의 Deal을 돌려준다
    expect(exact.items.map((row) => row.ownerId)).toEqual([USER_ID.old])
    expect([lower.total, spaced.total, bare.total]).toEqual([0, 0, 0])
  })

  // 맞는 사람이 없으면 오류 없이 0건이다.
  // 테스트 코드: DL-144
  it('returns an empty page without an error when nobody matches', async () => {
    // given: Fake 게이트웨이
    const { gateway } = await mockAs('kim')

    // when: 없는 이름으로 찾는다
    const result = await gateway.deals.list({ ...ALL, ownerName: '없는사람' })

    // then: 0건이다
    expect(result).toMatchObject({ items: [], total: 0 })
  })

  // 공백뿐인 이름은 조건이 없다(담당자 id를 함께 보내도 오류가 아니다).
  // 테스트 코드: DL-144
  it('treats a blank name as no condition even together with an owner id', async () => {
    // given: Fake 게이트웨이와 전체 Deal 수
    const { gateway } = await mockAs('kim')
    const all = await gateway.deals.list(ALL)

    // when: 공백뿐인 이름, 그리고 공백뿐인 이름 + 담당자 id로 찾는다
    const blank = await gateway.deals.list({ ...ALL, ownerName: '  ' })
    const withId = await gateway.deals.list({ ...ALL, ownerName: '  ', ownerId: USER_ID.park })

    // then: 앞의 것은 전체이고 뒤의 것은 박영업만이다
    expect(blank.total).toBe(all.total)
    expect(withId.items.every((row) => row.ownerId === USER_ID.park)).toBe(true)
    expect(withId.total).toBeGreaterThan(0)
  })

  // 이름과 담당자 id를 함께 보내면 422이다.
  // 테스트 코드: DL-144
  it('rejects an owner name together with an owner id', async () => {
    // given: Fake 게이트웨이
    const { gateway } = await mockAs('kim')

    // when·then: 둘 다 주면 서버와 같은 문구의 422 validation이다
    const error = await expectApiError(gateway.deals.list({ ownerName: '영업', ownerId: USER_ID.park }), 422, BOTH_MESSAGE)
    expect(error.kind).toBe('validation')
  })

  // 내 딜만이 켜져 있으면 이름·담당자 id를 모두 무시하고 둘을 함께 줘도 오류가 아니다.
  // 테스트 코드: DL-144
  it('ignores the owner name and id when mine is on', async () => {
    // given: 김영업으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    const mine = await gateway.deals.list({ ...ALL, mine: true })

    // when: mine과 함께 이름과 담당자 id를 보낸다
    const result = await gateway.deals.list({ ...ALL, mine: true, ownerName: '박영', ownerId: USER_ID.park })

    // then: 오류 없이 김영업의 Deal 그대로다
    expect(result.total).toBe(mine.total)
    expect(result.items.every((row) => row.ownerId === USER_ID.kim)).toBe(true)
  })

  // 이름은 100자까지 허용하고 101자는 요청 형식 오류이며 NUL은 별도 문구의 422이다.
  // 테스트 코드: DL-144
  it('accepts 100 characters and rejects 101 characters or a NUL', async () => {
    // given: Fake 게이트웨이
    const { gateway } = await mockAs('kim')

    // when·then: 100자는 0건, 101자와 NUL은 422
    await expect(gateway.deals.list({ ownerName: 'a'.repeat(100) })).resolves.toMatchObject({ total: 0 })
    await expectApiError(gateway.deals.list({ ownerName: 'a'.repeat(101) }), 422, '요청 형식이 올바르지 않습니다')
    await expectApiError(gateway.deals.list({ ownerName: 'a\u0000b' }), 422, '담당자에는 NUL 문자를 쓸 수 없습니다')
  })
})
