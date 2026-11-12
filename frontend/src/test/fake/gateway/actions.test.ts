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
  // user는 Action을 등록할 수 없다(403).
  // 테스트 코드: AC-090
  it('user는 403', async () => {
    // given: user 역할(han)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // when·then: 등록하면 403이다
    await expectApiError(gateway.actions.create(dealCode(2), input()), 403)
  })

  // 필수 누락은 위에서부터 첫 오류 문구로 422이고 없는 Deal은 404다.
  // 테스트 코드: AC-090
  it('필수 누락은 위에서부터 첫 오류 문구로 422', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 진행사항·Next Action이 모두 비면 해당 문구의 422다
    await expectApiError(gateway.actions.create(code, input({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
    // when·then: Next Action만 있고 Due가 없으면 Due Date 필수 422다
    await expectApiError(gateway.actions.create(code, input({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
    // when·then: Next Action 없이 Due만 있으면 Due 금지 422다
    await expectApiError(gateway.actions.create(code, input({ nextAction: '', dueDate: '2026-10-22' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
    // when·then: 없는 Deal에 등록하면 404다
    await expectApiError(gateway.actions.create('20000101-ZZZZ', input()), 404)
  })

  // 등록하면 수행일시·담당자·등록 시점 Status/Forecast를 서버가 채우고 이후 Deal 변경에 영향받지 않는다.
  // 테스트 코드: AC-090
  it('등록 시점의 Status/Forecast를 저장하고 수행일시·담당자는 서버가 채운다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 등록한다
    const created = await gateway.actions.create(code, input())
    // then: 수행일시·담당자·스냅숏·유형이 서버 값이다
    expect(created).toMatchObject({ dealCode: code, actedAt: TEST_NOW, actor: { id: USER_ID.kim }, statusKey: 'technical_evaluation', forecastKey: 'most_likely', type: '미팅', typeId: seedActionTypeId('미팅') })
    // 이후 Deal의 Status가 바뀌어도 Action 값은 그대로
    // when: 이후 Deal의 Status를 바꾼다
    await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'price_negotiation' } })
    // when: 목록을 읽는다
    const list = await gateway.actions.list(code, {})
    // then: Action의 스냅숏은 등록 당시 값 그대로다
    expect(list[0]).toMatchObject({ id: created.id, statusKey: 'technical_evaluation' })
  })

  // 등록하면 Deal의 Next Action·최종 업데이트가 바뀌고 History에 Action이 남는다.
  // 테스트 코드: AC-090
  it('Deal 목록의 Next Action과 최종 업데이트가 바뀌고 History에 Action이 남는다', async () => {
    // given: 미업데이트 경고인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(4) // 미업데이트
    expect((await gateway.deals.get(code)).risk).toBe('stale')
    // given: 등록 전 History 건수
    const base = (await gateway.history.list(code, {})).length
    // when: Next Action이 있는 Action을 등록한다
    await gateway.actions.create(code, input({ nextAction: '새 Next Action', dueDate: '2026-10-30' }))
    // when: Deal 목록의 그 행을 읽는다
    const row = (await gateway.deals.list({ keyword: code })).items[0]
    // then: Next Action과 최종 업데이트가 새 Action을 가리키고 경고가 사라진다
    expect(row).toMatchObject({ nextAction: { text: '새 Next Action', dueDate: '2026-10-30', status: 'open' }, lastUpdatedAt: TEST_NOW, risk: null })
    // when: History를 읽는다
    const history = await gateway.history.list(code, {})
    // then: History가 1건 늘고 맨 위가 요청자·수행 시각의 Action 줄이다
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', by: { id: USER_ID.kim }, at: TEST_NOW })
  })

  // 지난 Due Date도 받고 기한초과로 표시된다.
  // 테스트 코드: AC-090
  it('Due Date는 과거도 허용하고 기한초과로 표시된다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 지난 Due Date로 등록한다
    await gateway.actions.create(code, input({ dueDate: '2026-10-01' }))
    // then: Deal은 기한초과 경고다
    expect((await gateway.deals.get(code)).risk).toBe('overdue')
  })

  // 동반 변경이 있으면 Deal도 sync 규칙으로 바뀌고 Action에는 변경 뒤 값이 저장된다.
  // 테스트 코드: AC-090
  it('statusChange가 있으면 Deal도 sync 규칙으로 바뀌고 Action에는 적용 후 값이 저장된다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // given: 등록 전 Action 건수
    const countBefore = (await gateway.actions.list(code, {})).length
    // when·then: 매출 답 없이 계약완료로 바꾸며 등록하면 매출 필수 422다
    await expectApiError(
      gateway.actions.create(code, input({ statusChanges: [{ change: { field: 'statusKey', value: 'contract_completed' } }] })),
      422,
      'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.',
    )
    // then: Action이 늘지 않는다
    expect((await gateway.actions.list(code, {})).length).toBe(countBefore)
    // when: 매출 답과 함께 계약완료로 바꾸며 등록한다
    const created = await gateway.actions.create(
      code,
      input({
        statusChanges: [{
          change: { field: 'statusKey', value: 'contract_completed' },
          resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
        }],
      }),
    )
    // then: Action 스냅숏이 계약완료·Won이다
    expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
    // when: Deal을 읽는다
    const deal = await gateway.deals.get(code)
    // then: Deal은 계약완료·Won·매출금액으로 바뀐다
    expect([deal.statusKey, deal.forecastKey, deal.revenueAmount]).toEqual(['contract_completed', 'won', 1_800_000_000])
    // then: History에 Status·Forecast·Action 줄이 있다
    const cats = (await gateway.history.list(code, {})).slice(0, 5).map((h) => h.category)
    expect(cats).toEqual(expect.arrayContaining(['action', 'status', 'forecast']))
  })
})

describe('actions.list', () => {
  // 조건 없는 목록은 수행일시 최신순이고 작성자 이름이 풀려 있다(Fake도 서버 규칙을 따른다).
  // 테스트 코드: AC-090, NA-068, NA-019
  it('기본은 수행일시 최신순이고 actor가 풀려 있다', async () => {
    // given: user 역할(han)로 로그인했다.
    const { gateway } = await mockAs('han')
    // when: 조건 없이 목록을 부른다.
    const list = await gateway.actions.list(dealCode(1), {})
    // then: 수행일시 내림차순이고 작성자 이름과 내용이 채워져 있다.
    expect(list.length).toBeGreaterThanOrEqual(2)
    const times = list.map((a) => Date.parse(a.actedAt))
    expect(times).toEqual([...times].sort((a, b) => b - a))
    expect(list[0]?.actor.name).toBeTruthy()
    expect(list[0]).toMatchObject({ type: '협상', progress: '최종 가격 협의', nextAction: '계약서 초안 검토', dueDate: '2026-10-18' })
  })

  // 유형·담당자·키워드·수행일·기한·정렬 조건을 Fake도 서버 규칙대로 적용한다.
  // 테스트 코드: NA-068
  it('검색: 유형·담당자·키워드·수행일·기한·정렬', async () => {
    // given: 김영업으로 로그인했고 한 Deal의 전체 목록이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const all = await gateway.actions.list(code, {})
    // when: 유형·담당자·키워드·수행일·기한·정렬 조건으로 각각 목록을 부른다.
    const byType = await gateway.actions.list(code, { typeId: seedActionTypeId('협상') })
    // then: 각 조건에 맞는 행만 나오고 정렬은 서버 순서대로다.
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
      await mock.signInAs(USER_ID[login])
      mock.clock.advance(60_000)
      await mock.gateway.actions.create(
        code,
        input({ type: { name: type }, progress, nextAction: due === null ? '' : `${progress} 계획`, dueDate: due ?? '' }),
      )
    }
    await mock.signInAs(USER_ID.root)
    const names = async (query: Parameters<typeof mock.gateway.actions.list>[1]) =>
      (await mock.gateway.actions.list(code, query)).filter((a) => rows.some((r) => r[2] === a.progress)).map((a) => a.progress)
    return { names }
  }

  // 수행일시 정렬의 동률은 양방향 모두 먼저 등록한 Action이 앞이다.
  // 테스트 코드: NA-068, NA-038
  it('수행일시 정렬의 동률은 id 오름차순이다(서버와 같음)', async () => {
    // given: 같은 수행 일시에 Action 둘을 연달아 등록했다.
    const mock = await mockAs('kim')
    const code = dealCode(2)
    const first = await mock.gateway.actions.create(code, input({ progress: '동시 1' }))
    const second = await mock.gateway.actions.create(code, input({ progress: '동시 2' }))
    expect(second.actedAt).toBe(first.actedAt)

    // when: 내림차순·오름차순으로 목록을 부른다.
    const desc = (await mock.gateway.actions.list(code, {})).filter((a) => a.actedAt === first.actedAt).map((a) => a.id)
    const asc = (await mock.gateway.actions.list(code, { sort: 'actedAt', order: 'asc' })).filter((a) => a.actedAt === first.actedAt).map((a) => a.id)

    // then: 두 방향 모두 먼저 등록한 Action이 앞이다.
    expect(desc).toEqual([first.id, second.id])
    expect(asc).toEqual([first.id, second.id])
  })

  // Due Date 정렬은 Due가 없는 Action을 방향과 관계없이 맨 뒤에 둔다.
  // 테스트 코드: NA-068, NA-039
  it('dueDate desc는 늦은 날짜부터이고 Due가 없는 Action은 방향과 관계없이 맨 뒤다', async () => {
    // given: Due가 다른 Action 둘과 Due가 없는 Action이 있다.
    const { names } = await seeded([
      ['kim', '미팅', 'Z빠름', '2026-12-01'],
      ['kim', '미팅', 'Z없음', null],
      ['kim', '미팅', 'Z늦음', '2026-12-20'],
    ])

    // when·then: 내림차순은 늦은 날짜부터이고 Due 없음이 맨 뒤다.
    expect(await names({ sort: 'dueDate', order: 'desc' })).toEqual(['Z늦음', 'Z빠름', 'Z없음'])
    // when·then: 오름차순은 빠른 날짜부터이고 Due 없음이 맨 뒤다.
    expect(await names({ sort: 'dueDate', order: 'asc' })).toEqual(['Z빠름', 'Z늦음', 'Z없음'])
  })

  // 주 키가 같으면 방향을 바꿔도 최신 수행이 먼저다.
  // 테스트 코드: NA-068, NA-039
  it('동률은 방향을 바꿔도 최신 수행 먼저(그 다음 id 오름차순)이다', async () => {
    // given: Due 날짜가 같은 오래된 Action과 최신 Action이 있다.
    const { names } = await seeded([
      ['kim', '미팅', 'T오래됨', '2026-12-01'],
      ['kim', '미팅', 'T최신', '2026-12-01'],
    ])

    // when·then: Due 오름차순이어도 최신이 먼저다.
    expect(await names({ sort: 'dueDate', order: 'asc' })).toEqual(['T최신', 'T오래됨'])
    // when·then: Due 내림차순이어도 최신이 먼저다.
    expect(await names({ sort: 'dueDate', order: 'desc' })).toEqual(['T최신', 'T오래됨'])
    // when·then: 작성자 내림차순이어도 최신이 먼저다.
    expect(await names({ sort: 'actor', order: 'desc' })).toEqual(['T최신', 'T오래됨'])
  })

  // 담당자 정렬은 표시 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다.
  // 테스트 코드: NA-068, NA-040
  it('담당자는 표시 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다(김영업 < 박영업)', async () => {
    // given: 박영업과 김영업이 각각 남긴 Action이 있다.
    const { names } = await seeded([
      ['park', '미팅', 'A박', '2026-12-01'],
      ['kim', '미팅', 'A김', '2026-12-01'],
    ])

    // when·then: 오름차순은 김영업 < 박영업이다.
    expect(await names({ sort: 'actor', order: 'asc' })).toEqual(['A김', 'A박'])
    // when·then: 내림차순은 그 반대다.
    expect(await names({ sort: 'actor', order: 'desc' })).toEqual(['A박', 'A김'])
  })

  // 유형 정렬은 현재 유형 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다.
  // 테스트 코드: NA-068, NA-041
  it('유형은 현재 유형 이름을 대소문자 구분 없이 코드 포인트 순으로 비교한다', async () => {
    // given: 유형 이름이 통화·Beta·미팅·alpha인 Action이 있다.
    const { names } = await seeded([
      ['kim', '통화', 'Y통화', '2026-12-01'],
      ['kim', 'Beta', 'Y베타', '2026-12-01'],
      ['kim', '미팅', 'Y미팅', '2026-12-01'],
      ['kim', 'alpha', 'Y알파', '2026-12-01'],
    ])

    // when·then: 오름차순은 alpha < Beta < 미팅 < 통화다.
    expect(await names({ sort: 'type', order: 'asc' })).toEqual(['Y알파', 'Y베타', 'Y미팅', 'Y통화'])
    // when·then: 내림차순은 그 반대다.
    expect(await names({ sort: 'type', order: 'desc' })).toEqual(['Y통화', 'Y미팅', 'Y베타', 'Y알파'])
  })

  // 상태 정렬은 Open, 종료(수행), 종료(미수행) 순이고 상태 없음은 방향과 관계없이 맨 뒤다.
  // 테스트 코드: NA-068, NA-042
  it('상태는 open, done, not_done 순이고 상태 없음은 방향과 관계없이 맨 뒤다', async () => {
    // given: Open·종료(수행)·종료(미수행)·Next Action 없음 Action이 있다.
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
    // when: 상태 정렬을 오름차순·내림차순으로 부른다.
    const names = async (order: 'asc' | 'desc') =>
      (await mock.gateway.actions.list(code, { sort: 'nextActionStatus', order })).map((a) => a.progress).filter((p) => ['S열림', 'S수행', 'S미수행', 'S없음'].includes(p ?? ''))

    // then: 오름차순은 열림, 수행, 미수행, 없음이다.
    expect(await names('asc')).toEqual(['S열림', 'S수행', 'S미수행', 'S없음'])
    // then: 내림차순은 미수행, 수행, 열림, 없음이고 상태 없음은 맨 뒤다.
    expect(await names('desc')).toEqual(['S미수행', 'S수행', 'S열림', 'S없음'])
  })
})

describe('actions.update / remove', () => {
  // 이전 Action도 수정할 수 있고 등록 시점 값·수행일시·담당자는 유지된다.
  // 테스트 코드: AC-090
  it('이전 Action도 수정할 수 있고 등록 시점 값·수행일시·담당자는 유지된다', async () => {
    // given: 담당자 본인(kim)과 가장 오래된 Action
    const { gateway } = await mockAs('kim') // 담당자 본인다른 sales는 actions.rules.test.ts
    const code = dealCode(1)
    const old = (await gateway.actions.list(code, {})).at(-1)
    if (!old) throw new Error('no action')
    // given: 수정 전 History 건수
    const base = (await gateway.history.list(code, {})).length
    // when: 유형·내용을 모두 고쳐 수정한다
    const updated = await gateway.actions.update(old.id, { type: { name: '기타' }, progress: '수정한 진행사항', nextAction: '수정한 Next', dueDate: '2026-11-01', memo: '메모' })
    // then: 내용만 바뀌고 수행일시·담당자·스냅숏은 그대로다
    expect(updated).toMatchObject({ id: old.id, progress: '수정한 진행사항', actedAt: old.actedAt, actor: old.actor, statusKey: old.statusKey, forecastKey: old.forecastKey })
    // when: History를 읽는다
    const history = await gateway.history.list(code, {})
    // then: History가 1건 늘고 맨 위가 요청자의 Action 줄이다
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', by: { id: USER_ID.kim } })
    // when·then: 진행사항·Next Action을 모두 비우면 422다
    await expectApiError(gateway.actions.update(old.id, { type: { name: '기타' }, progress: '', nextAction: '', dueDate: '', memo: '' }), 422, '진행사항 또는 Next Action을 입력하세요.')
    // when·then: 없는 Action을 수정하면 404다
    await expectApiError(gateway.actions.update(NO_SUCH_ID, { type: { name: '기타' }, progress: 'x', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 404)
  })

  // 최신 Action을 삭제하면 이전 Action이 Deal의 Next Action이 된다.
  // 테스트 코드: AC-090
  it('최신 Action을 삭제하면 이전 Action이 Next Action이 된다', async () => {
    // given: sales(kim)와 Action 목록·History 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const list = await gateway.actions.list(code, {})
    const base = (await gateway.history.list(code, {})).length
    // when: 최신 Action을 삭제한다
    await gateway.actions.remove(list[0]?.id ?? NO_SUCH_ID)
    // then: 목록이 1건 줄고 Deal Next Action이 이전 Action의 것이다
    expect((await gateway.actions.list(code, {})).length).toBe(list.length - 1)
    expect((await gateway.deals.get(code)).nextAction?.text).toBe(list[1]?.nextAction)
    // when: History를 읽는다
    const history = await gateway.history.list(code, {})
    // then: History가 1건 늘고 맨 위가 "삭제"다
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'action', after: '삭제' })
  })

  // user는 수정·삭제할 수 없다(403).
  // 테스트 코드: AC-090
  it('user는 수정·삭제 403', async () => {
    // given: user(han)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // given: 첫 Action
    const first = (await gateway.actions.list(dealCode(1), {}))[0]
    if (!first) throw new Error('no action')
    // when·then: 수정하면 403이다
    await expectApiError(gateway.actions.update(first.id, { type: { name: '기타' }, progress: 'x', nextAction: 'x', dueDate: '2026-11-01', memo: '' }), 403)
    // when·then: 삭제하면 403이다
    await expectApiError(gateway.actions.remove(first.id), 403)
  })
})
