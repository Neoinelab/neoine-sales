import { describe, expect, it } from 'vitest'
import { dealInput, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

/** 서버는 글자 수를 코드 포인트로 센다. 이모지 하나는 1자다(UTF-16 length로 세면 2자가 된다). */
describe('deals.create: 길이 한도는 코드 포인트로 센다', () => {
  const EMOJI = '😀'

  it.each([
    ['name', 200, 'Deal Name은 200자 이내로 입력하세요.'],
    ['procurement', 500, '구매절차는 500자 이내로 입력하세요.'],
  ] as const)('%s는 이모지 정확히 %i개까지 받아들이고 하나 더 많으면 거절한다', async (field, max, message) => {
    // given: 영업 사용자 게이트웨이
    const { gateway } = await mockAs('kim')

    // when·then: 한도 개수의 이모지는 등록되고, 하나 더 많으면 한도 문구로 422가 된다
    await expect(gateway.deals.create(dealInput(USER_ID.kim, { [field]: EMOJI.repeat(max) }))).resolves.toBeDefined()
    await expect(gateway.deals.create(dealInput(USER_ID.kim, { [field]: EMOJI.repeat(max + 1) }))).rejects.toMatchObject({
      status: 422,
      message,
    })
  })

  it('앞뒤 공백을 자른 뒤의 글자 수로 센다', async () => {
    // given: 영업 사용자 게이트웨이
    const { gateway } = await mockAs('kim')

    // when: 공백으로 감싼 500자 구매절차로 Deal을 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { procurement: `  ${EMOJI.repeat(500)}  ` }))

    // then: 자른 뒤 한도 안이라 등록된다
    expect(created).toBeDefined()
  })
})
