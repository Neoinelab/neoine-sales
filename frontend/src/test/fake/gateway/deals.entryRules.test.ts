import { describe, expect, it } from 'vitest'
import { dealInput, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'
import { DEAL_CODE_ISSUE_FAILED_MESSAGE } from './dealsWrite'

/** 난수열을 미리 정해 둔 `random`(다 쓰면 마지막 값을 반복한다). */
function sequence(values: number[]): () => number {
  let index = 0
  return () => values[Math.min(index++, values.length - 1)] ?? 0
}

const SAME = [0, 0, 0, 0] // 끝 4자리가 늘 AAAA
const OTHER = [0.5, 0.5, 0.5, 0.5]

describe('Fake deals.create: 서버의 Deal code 발급 규칙(DE-R2)을 따른다', () => {
  // Fake가 서버처럼 10번째 시도까지 성공할 수 있어야 한다(BDD 밖 Fake 검사).
  it('succeeds on the tenth attempt after nine collisions', async () => {
    // given: 첫 Deal이 AAAA를 쓰고, 둘째 등록은 9번 겹친 뒤 10번째에 다른 값이 나온다
    const random = sequence([...SAME, ...Array<number>(9 * 4).fill(0), ...OTHER])
    const { gateway } = await mockAs('kim', { random })
    const first = await gateway.deals.create(dealInput(USER_ID.kim))

    // when: 둘째 Deal을 등록한다
    const second = await gateway.deals.create(dealInput(USER_ID.kim))

    // then: 10번째 시도의 code로 등록된다
    expect(first.code.endsWith('-AAAA')).toBe(true)
    expect(second.code.endsWith('-AAAA')).toBe(false)
  })

  // 10번 모두 겹치면 서버처럼 409와 같은 문구로 거절하고 저장하지 않는다.
  it('rejects with the issue-failed message after ten collisions and stores nothing', async () => {
    // given: 난수가 늘 같은 끝 4자리를 준다
    const { gateway } = await mockAs('kim', { random: sequence(SAME) })
    await gateway.deals.create(dealInput(USER_ID.kim))
    const before = (await gateway.deals.list({})).total

    // when: 한 번 더 등록한다
    const failure = gateway.deals.create(dealInput(USER_ID.kim))

    // then: 409 + 서버 문구이고 Deal 수가 그대로다
    await expectApiError(failure, 409, DEAL_CODE_ISSUE_FAILED_MESSAGE)
    expect((await gateway.deals.list({})).total).toBe(before)
  })
})

describe('Fake deals.create: 서버의 NUL 문자 거절 문구(PL-R16)를 따른다', () => {
  // Deal Name·Product·구매절차의 NUL은 공백으로 감싸도 칸 이름이 든 문구로 거절한다.
  it.each([
    ['name', 'Deal Name'],
    ['product', 'Product'],
    ['procurement', '구매절차'],
  ] as const)('rejects a NUL character in %s with the column name', async (field, column) => {
    // given: kim으로 로그인한 Fake
    const { gateway } = await mockAs('kim')

    // when: 그 칸에 NUL이 든 값으로 등록한다
    const failure = gateway.deals.create(dealInput(USER_ID.kim, { [field]: ' a\u0000b ' }))

    // then: 422와 '<칸>에는 NUL 문자를 쓸 수 없습니다'다
    await expectApiError(failure, 422, `${column}에는 NUL 문자를 쓸 수 없습니다`)
  })
})
