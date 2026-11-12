import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

describe('history.list', () => {
  // 이력은 최신순이고 같은 시각이면 나중 것이 위다.
  // 테스트 코드: DD-117
  it('최신순이고 같은 시각이면 나중에 만든 것이 위다', async () => {
    // given: Forecast를 두 번 바꾼 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' } })
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })

    // when: 이력을 읽는다
    const list = await gateway.history.list(code, {})

    // then: Best, Commit 순서이고 시각이 내림차순이다
    expect(list[0]).toMatchObject({ category: 'forecast', after: 'Best' })
    expect(list[1]).toMatchObject({ category: 'forecast', after: 'Commit' })
    const times = list.map((h) => Date.parse(h.at))
    expect(times).toEqual([...times].sort((a, b) => b - a))
  })

  // 구분 필터가 되고 없는 Deal은 404이며 user도 읽는다.
  // 테스트 코드: DD-117
  it('category 필터와 없는 Deal 404, 모든 역할 조회 가능', async () => {
    // given: user 역할 사용자
    const { gateway } = await mockAs('han')
    const code = dealCode(1)
    const all = await gateway.history.list(code, {})

    // when: 전체·첨부·등록 구분과 없는 Deal의 이력을 읽는다
    const files = await gateway.history.list(code, { category: 'attachment' })

    // then: 필터가 맞게 걸리고 없는 Deal은 404다
    expect(files.length).toBe(3)
    expect(files.every((h) => h.category === 'attachment')).toBe(true)
    expect(all.length).toBeGreaterThan(files.length)
    expect((await gateway.history.list(code, { category: 'created' }))).toHaveLength(1)
    await expectApiError(gateway.history.list('20000101-ZZZZ', {}), 404)
  })

  // 시드 이력에 등록·파일·종결·Lost와 퇴사 변경자 표기가 있다.
  // 테스트 코드: DD-117
  it('시드 History: 등록·파일·종결·Lost·변경자 표기', async () => {
    // given: 시드 Deal들
    const { gateway } = await mockAs('han')

    // when: 이력을 읽는다
    const d1 = await gateway.history.list(dealCode(1), {})

    // then: 각 구분의 항목과 변경자 이름이 맞다
    expect(d1.find((h) => h.category === 'attachment' && h.after === '업로드 견적서_한빛은행_v2.pdf')).toBeTruthy()
    expect(d1.find((h) => h.category === 'created')).toMatchObject({ before: '', after: 'Deal 등록', by: { name: '김영업' } })
    const d11 = await gateway.history.list(dealCode(11), {})
    for (const category of ['status', 'forecast', 'amount', 'expectedClose'] as const) {
      expect(d11.some((h) => h.category === category)).toBe(true)
    }
    const d16 = await gateway.history.list(dealCode(16), { category: 'forecast' })
    expect(d16[0]).toMatchObject({ before: 'Best', after: 'Lost' })
    const d1attach = d1.filter((h) => h.category === 'attachment').map((h) => h.by.name)
    expect(d1attach).toContain('강퇴사')
    expect((await gateway.history.list(dealCode(24), { category: 'status' })).some((h) => h.after.includes('계약완료'))).toBe(true)
  })

  // 한 번의 폼 저장이 여러 필드를 바꾸면 필드마다 한 건씩 기록된다.
  // 테스트 코드: DD-117
  it('R02 한 번의 폼 저장이 여러 필드를 바꾸면 필드마다 기록된다', async () => {
    // given: Deal 하나
    const { gateway } = await mockAs('kim')
    const code = dealCode(4)
    const before = (await gateway.history.list(code, {})).length
    await gateway.deals.update(code, { name: '새 이름', revenueAmount: 1_000_000, revenueDate: '2027-02-01' })
    const added = (await gateway.history.list(code, {})).slice(0, -before)

    // when: 이름·금액·Expected Close를 한 번에 수정한다
    const actual1 = added.map((h) => h.category).sort()
    const actual2 = new Set(added.map((h) => h.by.id))

    // then: other·amount·expectedClose 세 건이 같은 변경자로 남는다
    expect(actual1).toEqual(['amount', 'expectedClose', 'other'])
    expect(actual2).toEqual(new Set([USER_ID.kim]))
  })
})
