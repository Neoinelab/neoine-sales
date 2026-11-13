import { describe, expect, it } from 'vitest'
import { newDeal } from '../../../gateway/contract/actions.contract'
import type { ActionInput } from '../../../shared/model/types'
import { mockAs } from '../testing'

// 공통 예: 서버 시계 T = 2026-11-13T14:30+09:00(오늘 2026-11-13), Deal 등록 2026-11-01 09:00.
const REGISTERED = '2026-11-01T09:00:00+09:00'
const T = '2026-11-13T14:30:00+09:00'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  memo: '',
  ...over,
})

async function setup() {
  const mock = await mockAs('kim', { now: REGISTERED })
  const deal = await newDeal(mock.gateway)
  mock.clock.setNow(T)
  return { mock, gateway: mock.gateway, code: deal.code }
}

describe('Fake actions: 수행일·종료일은 시각 없는 날짜다', () => {
  // 같은 수행일에 등록한 두 Action 중 나중에 등록한 것이 목록에서 앞이고 시각 키가 응답에 없다.
  // 테스트 코드: AC-117
  it('puts the later registered action first among the same acted day and has no time key', async () => {
    // given: 수행일 2026-11-10으로 두 Action을 차례로 등록했다
    const { gateway, code } = await setup()
    const first = await gateway.actions.create(code, input({ progress: '먼저', actedOn: '2026-11-10' }))
    const second = await gateway.actions.create(code, input({ progress: '나중', actedOn: '2026-11-10' }))

    // when: 기본 목록과 수행일 오름차순 목록을 읽는다
    const desc = await gateway.actions.list(code, {})
    const asc = await gateway.actions.list(code, { sort: 'actedAt', order: 'asc' })

    // then: actedOn은 날짜이고 actedAt 키가 없으며, 내림차순은 나중 → 먼저, 오름차순은 먼저 → 나중이다
    expect(first.actedOn).toBe('2026-11-10')
    expect(first).not.toHaveProperty('actedAt')
    expect(desc.map((a) => a.id)).toEqual([second.id, first.id])
    expect(asc.map((a) => a.id)).toEqual([first.id, second.id])
  })

  // 같은 수행일의 Next Action Action은 나중에 등록한 것이 Deal의 Next Action 기준 행이다.
  // 테스트 코드: AC-117
  it('makes the later registered action of the same acted day the basis of the deal next action', async () => {
    // given: 수행일 2026-11-12로 Next Action "A"와 "B"를 차례로 등록했다
    const { gateway, code } = await setup()
    await gateway.actions.create(code, input({ nextAction: 'A', actedOn: '2026-11-12' }))
    await gateway.actions.create(code, input({ nextAction: 'B', actedOn: '2026-11-12' }))

    // when: Deal을 읽는다
    const deal = await gateway.deals.get(code)

    // then: Next Action은 "B"이고 최종 업데이트일은 수행일 2026-11-12다
    expect(deal.nextAction?.text).toBe('B')
    expect(deal.lastUpdatedOn).toBe('2026-11-12')
  })

  // Open Action을 종료(수행)하면 종료일은 Fake 시계의 오늘이고 Open으로 되돌리면 null이다. 시각 키는 없다.
  // 테스트 코드: NA-072
  it('sets the closed date to the clock today on close and null on reopen', async () => {
    // given: Fake 시계의 오늘이 2026-11-13이고 Open Action이 있다
    const { gateway, code } = await setup()
    const open = await gateway.actions.create(code, input({ actedOn: '2026-11-10' }))

    // when: 종료(수행)한다
    const closed = await gateway.actions.changeNextActionStatus(open.id, { status: 'done', memo: '' })

    // then: 종료일은 "2026-11-13"이고 nextActionClosedAt 키가 없다
    expect(closed.nextActionClosedOn).toBe('2026-11-13')
    expect(closed).not.toHaveProperty('nextActionClosedAt')

    // when: Open으로 되돌린다
    const reopened = await gateway.actions.changeNextActionStatus(open.id, { status: 'open', memo: '' })

    // then: 종료일이 null이다
    expect(reopened.nextActionClosedOn).toBeNull()
  })

  // 서버 시계의 날짜가 바뀐 뒤에 종료하면 종료일은 그날의 업무 날짜다.
  // 테스트 코드: NA-072
  it('uses the business date of the request time as the closed date', async () => {
    // given: 2026-11-13에 등록한 Open Action이 있고 서버 시계가 하루 흘렀다
    const { mock, gateway, code } = await setup()
    const open = await gateway.actions.create(code, input())
    mock.clock.setNow('2026-11-14T00:10:00+09:00')

    // when: 종료(미수행)한다
    const closed = await gateway.actions.changeNextActionStatus(open.id, { status: 'notDone', memo: '취소' })

    // then: 종료일은 요청 시각의 업무 날짜 2026-11-14다(UTC 날짜 2026-11-13이 아니다)
    expect(closed.nextActionClosedOn).toBe('2026-11-14')
  })
})
