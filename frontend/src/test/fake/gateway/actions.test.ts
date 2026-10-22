import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { seedActionTypeId } from '../seed/actionTypes'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

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
    await expectApiError(gateway.actions.create(code, input({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
    await expectApiError(gateway.actions.create(code, input({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
    await expectApiError(gateway.actions.create(code, input({ nextAction: '', dueDate: '2026-10-22' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
    await expectApiError(gateway.actions.create('20000101-ZZZZ', input()), 404)
  })

  it('등록 시점의 Status/Forecast를 저장하고 수행일시·담당자는 서버가 채운다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    expect(created).toMatchObject({ dealCode: code, actedAt: TEST_NOW, actor: { id: USER_ID.kim }, statusKey: 'technical_evaluation', forecastKey: 'most_likely', type: '미팅', typeId: seedActionTypeId('미팅') })
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
    expect(row).toMatchObject({ nextAction: { text: '새 Next Action', dueDate: '2026-10-30', status: 'open' }, lastUpdatedAt: TEST_NOW, risk: null })
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', by: { id: USER_ID.kim }, at: TEST_NOW })
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
    expect((await gateway.actions.list(code, { actorId: NO_SUCH_ID })).length).toBe(0)
    expect((await gateway.actions.list(code, { actorId: USER_ID.kim })).length).toBe(all.length)
    expect((await gateway.actions.list(code, { keyword: '최종 가격' })).map((a) => a.progress)).toContain('최종 가격 협의')
    expect((await gateway.actions.list(code, { keyword: 'ROI' })).length).toBeGreaterThan(0)
    const latestDate = all[0]?.actedAt.slice(0, 10) ?? ''
    const onlyLatest = await gateway.actions.list(code, { actedFrom: latestDate, actedTo: latestDate })
    expect(onlyLatest.map((a) => a.id)).toEqual([all[0]?.id])
    const due = await gateway.actions.list(code, { dueFrom: '2026-10-18', dueTo: '2026-10-18' })
    expect(due.every((a) => a.dueDate === '2026-10-18')).toBe(true)
    const asc = await gateway.actions.list(code, { sort: 'actedAt', order: 'asc' })
    expect(asc.map((a) => a.id)).toEqual([...all].reverse().map((a) => a.id))
    const dueAsc = (await gateway.actions.list(code, { sort: 'dueDate', order: 'asc' })).map((a) => a.dueDate)
    expect(dueAsc).toEqual([...dueAsc].sort())
  })
})

describe('actions.list 헤더 정렬 (서버 정렬 표와 같은 순서)', () => {
  /** 한 Deal에 (담당자, 유형, 진행사항, Due)별 Action을 만들고 진행사항 목록으로 본다. 시계는 한 건마다 1분 간다. */
  async function seeded(rows: readonly (readonly [keyof typeof USER_ID, string, string, string | null])[]) {
    const mock = await mockAs('root')
    const code = dealCode(2)
    for (const [login, type, progress, due] of rows) {
      await mock.gateway.auth.quickLogin(USER_ID[login])
      mock.clock.advance(60_000)
      await mock.gateway.actions.create(
        code,
        input({ type: { name: type }, progress, nextAction: due === null ? '' : `${progress} 계획`, dueDate: due ?? '' }),
      )
    }
    await mock.gateway.auth.quickLogin(USER_ID.root)
    const names = async (query: Parameters<typeof mock.gateway.actions.list>[1]) =>
      (await mock.gateway.actions.list(code, query)).filter((a) => rows.some((r) => r[2] === a.progress)).map((a) => a.progress)
    return { names }
  }

  it('수행일시 정렬의 동률은 id 오름차순이다(서버와 같음)', async () => {
    const mock = await mockAs('kim')
    const code = dealCode(2)
    const first = await mock.gateway.actions.create(code, input({ progress: '동시 1' }))
    const second = await mock.gateway.actions.create(code, input({ progress: '동시 2' }))
    expect(second.actedAt).toBe(first.actedAt)

    const desc = (await mock.gateway.actions.list(code, {})).filter((a) => a.actedAt === first.actedAt).map((a) => a.id)
    const asc = (await mock.gateway.actions.list(code, { sort: 'actedAt', order: 'asc' })).filter((a) => a.actedAt === first.actedAt).map((a) => a.id)

    expect(desc).toEqual([first.id, second.id])
    expect(asc).toEqual([first.id, second.id])
  })

  it('dueDate desc는 늦은 날짜부터이고 Due가 없는 Action은 방향과 관계없이 맨 뒤다', async () => {
    const { names } = await seeded([
      ['kim', '미팅', 'Z빠름', '2026-12-01'],
      ['kim', '미팅', 'Z없음', null],
      ['kim', '미팅', 'Z늦음', '2026-12-20'],
    ])

    expect(await names({ sort: 'dueDate', order: 'desc' })).toEqual(['Z늦음', 'Z빠름', 'Z없음'])
    expect(await names({ sort: 'dueDate', order: 'asc' })).toEqual(['Z빠름', 'Z늦음', 'Z없음'])
  })

  it('동률은 방향을 바꿔도 최신 수행 먼저(그 다음 id 오름차순)이다', async () => {
    const { names } = await seeded([
      ['kim', '미팅', 'T오래됨', '2026-12-01'],
      ['kim', '미팅', 'T최신', '2026-12-01'],
    ])

    expect(await names({ sort: 'dueDate', order: 'asc' })).toEqual(['T최신', 'T오래됨'])
    expect(await names({ sort: 'dueDate', order: 'desc' })).toEqual(['T최신', 'T오래됨'])
    expect(await names({ sort: 'actor', order: 'desc' })).toEqual(['T최신', 'T오래됨'])
  })

  it('담당자는 표시 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다(김영업 < 박영업)', async () => {
    const { names } = await seeded([
      ['park', '미팅', 'A박', '2026-12-01'],
      ['kim', '미팅', 'A김', '2026-12-01'],
    ])

    expect(await names({ sort: 'actor', order: 'asc' })).toEqual(['A김', 'A박'])
    expect(await names({ sort: 'actor', order: 'desc' })).toEqual(['A박', 'A김'])
  })

  it('유형은 현재 유형 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다', async () => {
    const { names } = await seeded([
      ['kim', '통화', 'Y통화', '2026-12-01'],
      ['kim', 'Beta', 'Y베타', '2026-12-01'],
      ['kim', '미팅', 'Y미팅', '2026-12-01'],
      ['kim', 'alpha', 'Y알파', '2026-12-01'],
    ])

    expect(await names({ sort: 'type', order: 'asc' })).toEqual(['Y알파', 'Y베타', 'Y미팅', 'Y통화'])
    expect(await names({ sort: 'type', order: 'desc' })).toEqual(['Y통화', 'Y미팅', 'Y베타', 'Y알파'])
  })

  it('상태는 open, done, not_done 순이고 상태 없음은 방향과 관계없이 맨 뒤다', async () => {
    const mock = await mockAs('kim')
    const code = dealCode(2)
    const notDone = await mock.gateway.actions.create(code, input({ progress: 'S미수행' }))
    mock.clock.advance(60_000)
    await mock.gateway.actions.create(code, input({ progress: 'S없음', nextAction: '', dueDate: '' }))
    mock.clock.advance(60_000)
    const done = await mock.gateway.actions.create(code, input({ progress: 'S수행' }))
    mock.clock.advance(60_000)
    await mock.gateway.actions.create(code, input({ progress: 'S열림' }))
    await mock.gateway.actions.changeNextActionStatus(notDone.id, { status: 'notDone', memo: '' })
    await mock.gateway.actions.changeNextActionStatus(done.id, { status: 'done', memo: '' })
    const names = async (order: 'asc' | 'desc') =>
      (await mock.gateway.actions.list(code, { sort: 'nextActionStatus', order })).map((a) => a.progress).filter((p) => ['S열림', 'S수행', 'S미수행', 'S없음'].includes(p ?? ''))

    expect(await names('asc')).toEqual(['S열림', 'S수행', 'S미수행', 'S없음'])
    expect(await names('desc')).toEqual(['S미수행', 'S수행', 'S열림', 'S없음'])
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
    expect(history[0]).toMatchObject({ category: 'action', by: { id: USER_ID.kim } })
    await expectApiError(gateway.actions.update(old.id, { type: { name: '기타' }, progress: '', nextAction: '', dueDate: '', memo: '' }), 422, '진행사항 또는 Next Action을 입력하세요.')
    await expectApiError(gateway.actions.update(NO_SUCH_ID, { type: { name: '기타' }, progress: 'x', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 404)
  })

  it('최신 Action을 삭제하면 이전 Action이 Next Action이 된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const list = await gateway.actions.list(code, {})
    const base = (await gateway.history.list(code, {})).length
    await gateway.actions.remove(list[0]?.id ?? NO_SUCH_ID)
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
