import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

describe('history.list', () => {
  it('최신순이고 같은 시각이면 나중에 만든 것이 위다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' } })
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const list = await gateway.history.list(code, {})
    expect(list[0]).toMatchObject({ category: 'forecast', after: 'Best' })
    expect(list[1]).toMatchObject({ category: 'forecast', after: 'Commit' })
    const times = list.map((h) => Date.parse(h.at))
    expect(times).toEqual([...times].sort((a, b) => b - a))
  })

  it('category 필터와 없는 Deal 404, 모든 역할 조회 가능', async () => {
    const { gateway } = await mockAs('han')
    const code = dealCode(1)
    const all = await gateway.history.list(code, {})
    const files = await gateway.history.list(code, { category: 'attachment' })
    expect(files.length).toBe(3)
    expect(files.every((h) => h.category === 'attachment')).toBe(true)
    expect(all.length).toBeGreaterThan(files.length)
    expect((await gateway.history.list(code, { category: 'created' }))).toHaveLength(1)
    await expectApiError(gateway.history.list('20000101-ZZZZ', {}), 404)
  })

  it('시드 History: 등록·파일·종결·Lost·변경자 표기', async () => {
    const { gateway } = await mockAs('han')
    const d1 = await gateway.history.list(dealCode(1), {})
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

  it('R02 한 번의 폼 저장이 여러 필드를 바꾸면 필드마다 기록된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(4)
    const before = (await gateway.history.list(code, {})).length
    await gateway.deals.update(code, { name: '새 이름', revenueAmount: 1_000_000, revenueDate: '2027-02-01' })
    const added = (await gateway.history.list(code, {})).slice(0, -before)
    expect(added.map((h) => h.category).sort()).toEqual(['amount', 'expectedClose', 'other'])
    expect(new Set(added.map((h) => h.by.id))).toEqual(new Set([USER_ID.kim]))
  })
})
