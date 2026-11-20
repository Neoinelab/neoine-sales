import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { pickNextActionBasis, type BasisCandidate } from './nextActionBasis'
import { dealInput, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

const CHANGED = '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.'
const REGISTERED_ON = '2026-10-01T09:00:00+09:00'
const TODAY_AT = '2026-10-10T09:00:00+09:00'

const row = (id: number, actedOn: string, nextAction: string | null, dueDate: string | null, status: 'open' | 'done' | 'notDone' | null): BasisCandidate => ({
  id,
  actedOn,
  nextAction,
  dueDate,
  nextActionStatus: status,
})

describe('pickNextActionBasis (RK-R1)', () => {
  // 지난 Open Next Action이 있으면 Due가 가장 이른 행이고 수행일은 보지 않는다.
  // 테스트 코드: RK-086
  it('picks the past open row with the earliest due and ignores acted day', () => {
    // given: 지난 Open 둘(Due 이른 쪽이 수행일은 더 앞)과 더 최근의 미래 Open
    const rows = [row(1, '2026-10-02', '가', '2026-10-05', 'open'), row(2, '2026-10-04', '나', '2026-10-08', 'open'), row(3, '2026-10-09', '다', '2026-10-20', 'open')]

    // when·then: 오늘 10-10이면 Due가 가장 이른 1번이고 목록 순서와 무관하다
    expect(pickNextActionBasis(rows, '2026-10-10')?.id).toBe(1)
    expect(pickNextActionBasis([...rows].reverse(), '2026-10-10')?.id).toBe(1)
  })

  // 지난 Open 행의 Due가 같으면 id가 큰 행이다.
  // 테스트 코드: RK-086
  it('breaks a tie of the same past open due by the larger id', () => {
    // given: Due가 같은 지난 Open 둘(작은 id가 더 최근 수행)
    const rows = [row(7, '2026-10-09', '가', '2026-10-05', 'open'), row(9, '2026-10-02', '나', '2026-10-05', 'open')]

    // when·then: id가 큰 행이다
    expect(pickNextActionBasis(rows, '2026-10-10')?.id).toBe(9)
  })

  // 지난 Open이 없으면 수행일 내림차순·id 내림차순 첫 행이고 종료된 행도 기준 행이 된다.
  // 테스트 코드: RK-086
  it('falls back to the latest acted row with a next action, closed rows included, and breaks ties by id', () => {
    // given: 지난 Open이 없는 행들(종료 행이 가장 최근, 같은 수행일 둘, 진행사항만 행 하나)
    const rows = [
      row(1, '2026-10-02', '가', '2026-10-05', 'done'),
      row(5, '2026-10-04', '나', '2026-10-20', 'open'),
      row(6, '2026-10-04', '다', '2026-10-25', 'notDone'),
      row(8, '2026-10-09', null, null, null),
    ]

    // when·then: 진행사항만 행은 건너뛰고 같은 수행일은 id가 큰 6번이다
    expect(pickNextActionBasis(rows, '2026-10-10')?.id).toBe(6)
  })

  // Due가 오늘인 Open 행은 지난 행이 아니고, 다음 날부터 지난 행이 된다.
  // 테스트 코드: RK-086
  it('does not treat an open row due today as past until the next day', () => {
    // given: Due가 오늘인 Open 오래된 행과 더 최근 행
    const rows = [row(1, '2026-10-02', '가', '2026-10-10', 'open'), row(2, '2026-10-09', '나', '2026-10-30', 'open')]

    // when·then: 오늘은 가장 최근 행(2), 다음 날은 지난 Open인 1이다
    expect(pickNextActionBasis(rows, '2026-10-10')?.id).toBe(2)
    expect(pickNextActionBasis(rows, '2026-10-11')?.id).toBe(1)
  })

  // Next Action 행이 없으면 null이고 입력을 바꾸지 않는다.
  // 테스트 코드: RK-086
  it('returns null without next action rows and leaves the input untouched', () => {
    // given: 진행사항만 행뿐인 목록
    const rows = [row(1, '2026-10-02', null, null, null)]
    const copy = structuredClone(rows)

    // when·then: null이고 입력은 그대로다
    expect(pickNextActionBasis(rows, '2026-10-10')).toBeNull()
    expect(pickNextActionBasis([], '2026-10-10')).toBeNull()
    expect(rows).toEqual(copy)
  })
})

async function setup() {
  const mock = await mockAs('kim', { now: REGISTERED_ON })
  const { gateway } = mock
  // Deal은 10-01에 등록하고 시계는 곧바로 오늘(10-10)로 돌려 둔다(수행일은 등록일 이후여야 한다).
  const make = async (name: string, over: Parameters<typeof dealInput>[1] = {}) => {
    mock.clock.setNow(REGISTERED_ON)
    const { code } = await gateway.deals.create(dealInput(USER_ID.kim, { name, ...over }))
    mock.clock.setNow(TODAY_AT)
    return code
  }
  const act = (code: string, actedOn: string, nextAction: string | null, dueDate: string | null, over: Partial<ActionInput> = {}) =>
    gateway.actions.create(code, { type: { name: '미팅' }, progress: nextAction === null ? '진행만' : '진행', nextAction: nextAction ?? '', dueDate: dueDate ?? '', comment: '', actedOn, ...over })
  return { mock, gateway, make, act }
}

/** AC-146과 같은 Deal: A(10-02, Due 10-05) · B(10-04, Due 10-08) · C(10-09, Due 10-20), 모두 Open. 오늘 10-10. */
async function dealWithThree(name = '기준 행 Deal') {
  const ctx = await setup()
  const code = await ctx.make(name)
  const a = await ctx.act(code, '2026-10-02', '견적 발송', '2026-10-05')
  const b = await ctx.act(code, '2026-10-04', '제안서', '2026-10-08')
  const c = await ctx.act(code, '2026-10-09', '데모', '2026-10-20')
  return { ...ctx, code, a, b, c }
}

describe('Fake deals.get·list의 nextAction (RK-R1, RK-R21)', () => {
  // 목록 행과 상세의 nextAction은 지난 Open 중 Due가 가장 이른 행이고 actionId를 담는다.
  // 테스트 코드: RK-088
  it('gives the same past open basis row, with its action id, in the list and the detail', async () => {
    // given: 지난 Open 둘(A·B)과 미래 Open(C)이 있는 Deal
    const { gateway, code, a } = await dealWithThree()

    // when: 목록과 상세를 읽는다
    const detail = await gateway.deals.get(code)
    const listed = (await gateway.deals.list({ keyword: '기준 행 Deal' })).items.find((d) => d.code === code)

    // then: 둘 다 A(Due 가장 이른 지난 Open)이고 actionId가 A의 id이며 기한초과다
    expect(detail.nextAction).toEqual({ text: '견적 발송', dueDate: '2026-10-05', status: 'open', actionId: a.id })
    expect(listed?.nextAction).toEqual(detail.nextAction)
    expect(detail.risk).toMatch(/overdue/)
  })

  // 지난 Open을 모두 종료하면 가장 최근 Next Action 행이 되고, 하나를 Open으로 되돌리면 그 행이 된다.
  // 테스트 코드: RK-088
  it('moves to the latest next action row when past open rows are closed and back when one is reopened', async () => {
    // given: A·B가 지난 Open인 Deal
    const { gateway, code, a, b, c } = await dealWithThree()

    // when: A·B를 종료한다
    await gateway.actions.changeNextActionStatus(a.id, { status: 'done', comment: '' })
    await gateway.actions.changeNextActionStatus(b.id, { status: 'notDone', comment: '' })
    const closed = await gateway.deals.get(code)
    // then: 기준 행은 가장 최근 C이고 기한초과가 아니다
    expect(closed.nextAction).toEqual({ text: '데모', dueDate: '2026-10-20', status: 'open', actionId: c.id })
    expect(closed.risk === null || !closed.risk.includes('overdue')).toBe(true)

    // when: B를 Open으로 되돌린다
    await gateway.actions.changeNextActionStatus(b.id, { status: 'open', comment: '' })
    // then: 기준 행은 B다
    expect((await gateway.deals.get(code)).nextAction).toMatchObject({ text: '제안서', status: 'open', actionId: b.id })
  })

  // Due가 오늘인 Open 행은 기준 행이 아니고 시계가 다음 날로 가면 기준 행이 된다.
  // 테스트 코드: RK-088
  it('selects an open row due today only after the Fake clock moves to the next day', async () => {
    // given: Due가 오늘(10-10)인 Open 행 A와 더 최근 행 C
    const { gateway, mock, make, act } = await setup()
    const code = await make('오늘 Due Deal')
    const a = await act(code, '2026-10-02', '오늘 마감', '2026-10-10')
    const c = await act(code, '2026-10-09', '다음', '2026-10-30')

    // when·then: 오늘은 C, 다음 날은 A다
    expect((await gateway.deals.get(code)).nextAction?.actionId).toBe(c.id)
    mock.clock.setNow('2026-10-11T09:00:00+09:00')
    expect((await gateway.deals.get(code)).nextAction?.actionId).toBe(a.id)
  })

  // 종결(Won) Deal도 지난 Open 행을 보이고 risk는 null이다.
  // 테스트 코드: RK-088
  it('shows the past open row of a won deal and keeps risk null', async () => {
    // given: Won Deal에 지난 Open Next Action이 있다
    const { gateway, make, act } = await setup()
    const code = await make('Won Deal', { statusKey: 'contract_completed', forecastKey: 'won' })
    const past = await act(code, '2026-10-02', '후속 연락', '2026-10-05')
    await act(code, '2026-10-09', '다음', '2026-10-30')

    // when: Deal을 읽는다
    const detail = await gateway.deals.get(code)

    // then: 지난 Open 행을 보이고 risk는 null이다
    expect(detail.nextAction).toMatchObject({ text: '후속 연락', actionId: past.id })
    expect(detail.risk).toBeNull()
  })
})

describe('Fake actions.create의 이전 Next Action 종료 대상 (RK-R1, AC-R7)', () => {
  // 가장 최근 Next Action 행 id(C)로 종료를 요청하면 409이고 아무것도 바뀌지 않는다. 지난 Open 기준 행(A)은 성공한다.
  // 테스트 코드: AC-151
  it('rejects the latest row id with 409 and closes the past open basis row', async () => {
    // given: AC-146과 같은 Deal(기준 행은 A)
    const { gateway, code, a, b, c, act } = await dealWithThree()

    // when·then: C.id와 B.id 종료는 409이고 Action 수·상태는 그대로다
    await expectApiError(act(code, '2026-10-10', null, null, { closePreviousNextActionId: c.id }), 409, CHANGED)
    await expectApiError(act(code, '2026-10-10', null, null, { closePreviousNextActionId: b.id }), 409, CHANGED)
    const unchanged = await gateway.actions.list(code, {})
    expect(unchanged).toHaveLength(3)
    expect(unchanged.map((x) => x.nextActionStatus)).toEqual(['open', 'open', 'open'])

    // when: A.id 종료와 함께 등록한다
    await act(code, '2026-10-10', null, null, { closePreviousNextActionId: a.id })

    // then: A가 종료(수행)이고 B·C는 Open 그대로다
    const after = await gateway.actions.list(code, {})
    expect(after.find((x) => x.id === a.id)?.nextActionStatus).toBe('done')
    expect(after.find((x) => x.id === b.id)?.nextActionStatus).toBe('open')
    expect(after.find((x) => x.id === c.id)?.nextActionStatus).toBe('open')
  })

  // 종료 대상 수행일 판정은 새 기준 행(A)의 수행일로 한다.
  // 테스트 코드: AC-151
  it('judges the acted day against the new basis row, not the latest row', async () => {
    // given: AC-148과 같은 Deal(A 수행 10-02, C 수행 10-09)
    const { gateway, code, a, act } = await dealWithThree()

    // when·then: A 수행일(10-02)보다 앞이면 422, C 수행일보다 앞이어도 A 이후면 성공이다
    await expectApiError(act(code, '2026-10-01', null, null, { closePreviousNextActionId: a.id }), 422, '이전 Next Action의 수행일(2026-10-02)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다.')
    await act(code, '2026-10-03', null, null, { closePreviousNextActionId: a.id })
    expect((await gateway.actions.list(code, {})).find((x) => x.id === a.id)?.nextActionStatus).toBe('done')
  })
})

describe('Fake deals.list의 nextActionStatus 필터 (RK-R1, DL-R11)', () => {
  // open·done·closed 필터가 기준 행 상태로 거른다. 지난 Open 기준 행이 있는 Deal은 더 최근 종료 행이 있어도 open이다.
  // 테스트 코드: DL-128
  it('filters by the basis row status so that a deal with a past open row is open', async () => {
    // given: P(A 지난 Open + 더 최근 종료 B), Q(종료 하나), R(미래 Open 하나)
    const { gateway, make, act } = await setup()
    const p = await make('필터 P')
    const q = await make('필터 Q')
    const r = await make('필터 R')
    await act(p, '2026-10-02', 'A', '2026-10-05')
    const pb = await act(p, '2026-10-09', 'B', '2026-10-20')
    await gateway.actions.changeNextActionStatus(pb.id, { status: 'done', comment: '' })
    const qa = await act(q, '2026-10-09', 'Q 할 일', '2026-10-20')
    await gateway.actions.changeNextActionStatus(qa.id, { status: 'done', comment: '' })
    await act(r, '2026-10-09', 'R 할 일', '2026-10-30')

    // when: open·done·closed로 각각 읽는다
    const codesOf = async (nextActionStatus: 'open' | 'done' | 'closed') => {
      const page = await gateway.deals.list({ keyword: '필터', nextActionStatus })
      return { codes: page.items.map((d) => d.code).sort(), total: page.total }
    }

    // then: open은 P·R(total 2)이고 done·closed는 Q뿐(total 1)이다
    expect(await codesOf('open')).toEqual({ codes: [p, r].sort(), total: 2 })
    expect(await codesOf('done')).toEqual({ codes: [q], total: 1 })
    expect(await codesOf('closed')).toEqual({ codes: [q], total: 1 })
  })
})
