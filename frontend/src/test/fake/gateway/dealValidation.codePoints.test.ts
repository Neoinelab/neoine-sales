import { describe, expect, it } from 'vitest'
import { dealInput, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

/** P2 이월 Q6(a): 서버는 글자 수를 코드 포인트로 센다. 이모지 하나는 1자다(UTF-16 length로 세면 2자가 된다). */
describe('deals.create: 길이 한도는 코드 포인트로 센다', () => {
  const EMOJI = '😀'

  it.each([
    ['name', 200, 'Deal Name은 200자 이내로 입력하세요.'],
    ['procurement', 500, '구매절차는 500자 이내로 입력하세요.'],
  ] as const)('%s accepts exactly %i emoji and rejects one more', async (field, max, message) => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.deals.create(dealInput(USER_ID.kim, { [field]: EMOJI.repeat(max) }))).resolves.toBeDefined()
    await expect(gateway.deals.create(dealInput(USER_ID.kim, { [field]: EMOJI.repeat(max + 1) }))).rejects.toMatchObject({
      status: 422,
      message,
    })
  })

  it('still counts after trimming surrounding spaces', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.deals.create(dealInput(USER_ID.kim, { procurement: `  ${EMOJI.repeat(500)}  ` }))).resolves.toBeDefined()
  })
})
