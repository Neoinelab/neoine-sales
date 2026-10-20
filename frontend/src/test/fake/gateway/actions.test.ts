import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { seedActionTypeId } from '../seed/actionTypes'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

describe('actions.create', () => {
  it('T-GW user는 403', async () => {
    const { gateway } = await mockAs('han')
    await expectApiError(gateway.actions.create(dealCode(2), input()), 403)
  })

  it('필수 누락은 위에서부터 첫 오류 문구로 422', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await expectApiError(gateway.actions.create(code, input({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항을 입력하세요.')
    await expectApiError(gateway.actions.create(code, input({ nextAction: '' })), 422, 'Next Action을 입력하세요.')
    await expectApiError(gateway.actions.create(code, input({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
    await expectApiError(gateway.actions.create('20000101-ZZZZ', input()), 404)
  })

  it('등록 시점의 Status/Forecast를 저장하고 수행일시·담당자는 서버가 채운다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    expect(created).toMatchObject({ dealCode: code, actedAt: TEST_NOW, actor: { id: 'u-kim' }, statusKey: 'technical_evaluation', forecastKey: 'most_likely', type: '미팅', typeId: seedActionTypeId('미팅') })
    // 이후 Deal의 Status가 바뀌어도 Action 값은 그대로
    await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'price_negotiation' } })
    const list = await gateway.actions.list(code, {})
    expect(list[0]).toMatchObject({ id: created.id, statusKey: 'technical_evaluation' })
  })

  it('Deal 목록의 Next Action과 최종 업데이트가 바뀌고 History에 Action이 남는다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(4) // 미업데이트
    expect((await gateway.deals.get(code)).risk).toBe('stale')
    const base = (await gateway.history.list(code, {})).length
    await gateway.actions.create(code, input({ nextAction: '새 Next Action', dueDate: '2026-10-30' }))
    const row = (await gateway.deals.list({ keyword: code })).items[0]
    expect(row).toMatchObject({ nextAction: { text: '새 Next Action', dueDate: '2026-10-30' }, lastUpdatedAt: TEST_NOW, risk: null })
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', by: { id: 'u-kim' }, at: TEST_NOW })
  })

  it('Due Date는 과거도 허용하고 기한초과로 표시된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await gateway.actions.create(code, input({ dueDate: '2026-10-01' }))
    expect((await gateway.deals.get(code)).risk).toBe('overdue')
  })

  it('statusChange가 있으면 Deal도 sync 규칙으로 바뀌고 Action에는 적용 후 값이 저장된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const countBefore = (await gateway.actions.list(code, {})).length
    await expectApiError(
      gateway.actions.create(code, input({ statusChanges: [{ change: { field: 'statusKey', value: 'contract_completed' } }] })),
      422,
      'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.',
    )
    expect((await gateway.actions.list(code, {})).length).toBe(countBefore)
    const created = await gateway.actions.create(
      code,
      input({
        statusChanges: [{
          change: { field: 'statusKey', value: 'contract_completed' },
          resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
        }],
      }),
    )
    expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
    const deal = await gateway.deals.get(code)
    expect([deal.statusKey, deal.forecastKey, deal.revenueAmount]).toEqual(['contract_completed', 'won', 1_800_000_000])
    const cats = (await gateway.history.list(code, {})).slice(0, 5).map((h) => h.category)
    expect(cats).toEqual(expect.arrayContaining(['action', 'status', 'forecast']))
  })
})

describe('actions.list', () => {
  it('기본은 수행일시 최신순이고 actor가 풀려 있다', async () => {
    const { gateway } = await mockAs('han')
    const list = await gateway.actions.list(dealCode(1), {})
    expect(list.length).toBeGreaterThanOrEqual(2)
    const times = list.map((a) => Date.parse(a.actedAt))
    expect(times).toEqual([...times].sort((a, b) => b - a))
    expect(list[0]?.actor.name).toBeTruthy()
    expect(list[0]).toMatchObject({ type: '협상', progress: '최종 가격 협의', nextAction: '계약서 초안 검토', dueDate: '2026-10-18' })
  })

  it('T-ACTION 검색: 유형·담당자·키워드·수행일·기한·정렬', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const all = await gateway.actions.list(code, {})
    const byType = await gateway.actions.list(code, { typeId: seedActionTypeId('협상') })
    expect(byType.length).toBeGreaterThan(0)
    expect(byType.every((a) => a.type === '협상')).toBe(true)
    expect((await gateway.actions.list(code, { actorId: 'u-nobody' })).length).toBe(0)
    expect((await gateway.actions.list(code, { actorId: 'u-kim' })).length).toBe(all.length)
    expect((await gateway.actions.list(code, { keyword: '최종 가격' })).map((a) => a.progress)).toContain('최종 가격 협의')
    expect((await gateway.actions.list(code, { keyword: 'ROI' })).length).toBeGreaterThan(0)
    const latestDate = all[0]?.actedAt.slice(0, 10) ?? ''
    const onlyLatest = await gateway.actions.list(code, { actedFrom: latestDate, actedTo: latestDate })
    expect(onlyLatest.map((a) => a.id)).toEqual([all[0]?.id])
    const due = await gateway.actions.list(code, { dueFrom: '2026-10-18', dueTo: '2026-10-18' })
    expect(due.every((a) => a.dueDate === '2026-10-18')).toBe(true)
    const asc = await gateway.actions.list(code, { sort: 'actedAsc' })
    expect(asc.map((a) => a.id)).toEqual([...all].reverse().map((a) => a.id))
    const dueAsc = (await gateway.actions.list(code, { sort: 'dueAsc' })).map((a) => a.dueDate)
    expect(dueAsc).toEqual([...dueAsc].sort())
  })
})

describe('actions.update / remove', () => {
  it('이전 Action도 수정할 수 있고 등록 시점 값·수행일시·담당자는 유지된다', async () => {
    const { gateway } = await mockAs('kim') // 담당자 본인(Q8). 다른 sales는 actions.rules.test.ts
    const code = dealCode(1)
    const old = (await gateway.actions.list(code, {})).at(-1)
    if (!old) throw new Error('no action')
    const base = (await gateway.history.list(code, {})).length
    const updated = await gateway.actions.update(old.id, { type: { name: '기타' }, progress: '수정한 진행사항', nextAction: '수정한 Next', dueDate: '2026-11-01', memo: '메모' })
    expect(updated).toMatchObject({ id: old.id, progress: '수정한 진행사항', actedAt: old.actedAt, actor: old.actor, statusKey: old.statusKey, forecastKey: old.forecastKey })
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', by: { id: 'u-kim' } })
    await expectApiError(gateway.actions.update(old.id, { type: { name: '기타' }, progress: '', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 422, '진행사항을 입력하세요.')
    await expectApiError(gateway.actions.update('act-none', { type: { name: '기타' }, progress: 'x', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 404)
  })

  it('최신 Action을 삭제하면 이전 Action이 Next Action이 된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const list = await gateway.actions.list(code, {})
    const base = (await gateway.history.list(code, {})).length
    await gateway.actions.remove(list[0]?.id ?? '')
    expect((await gateway.actions.list(code, {})).length).toBe(list.length - 1)
    expect((await gateway.deals.get(code)).nextAction?.text).toBe(list[1]?.nextAction)
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', after: '삭제' })
  })

  it('user는 수정·삭제 403', async () => {
    const { gateway } = await mockAs('han')
    const first = (await gateway.actions.list(dealCode(1), {}))[0]
    if (!first) throw new Error('no action')
    await expectApiError(gateway.actions.update(first.id, { type: { name: '기타' }, progress: 'x', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 403)
    await expectApiError(gateway.actions.remove(first.id), 403)
  })
})
