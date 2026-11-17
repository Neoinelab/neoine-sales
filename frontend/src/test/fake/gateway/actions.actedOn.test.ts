import { describe, expect, it } from 'vitest'
import { newDeal } from '../../../gateway/contract/actions.contract'
import type { ActionInput } from '../../../shared/model/types'
import { expectApiError, mockAs } from '../testing'

// 공통 예: 서버 시계 T = 2026-11-13T14:30+09:00(오늘 2026-11-13), Deal 등록 2026-11-01 09:00.
const REGISTERED = '2026-11-01T09:00:00+09:00'
const T = '2026-11-13T14:30:00+09:00'
const FUTURE = '수행일은 오늘 이후로 지정할 수 없습니다.'
const BEFORE_REGISTERED = '수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다.'
const EARLIER_THAN_BASIS = '이전 Next Action의 수행일(2026-11-12)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다.'
const CONTENT_REQUIRED = '진행사항 또는 Next Action을 입력하세요.'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  comment: '',
  ...over,
})

/** 11-01 09:00에 Deal을 등록하고 서버 시계를 T로 맞춘다. */
async function setup() {
  const mock = await mockAs('kim', { now: REGISTERED })
  const deal = await newDeal(mock.gateway)
  mock.clock.setNow(T)
  return { mock, gateway: mock.gateway, code: deal.code }
}

describe('Fake actions: 수행일(acted_on) 결정·범위·종료 비교·판정 순서(AC-R33, AC-R34~R36)', () => {
  // 수행일을 생략하거나 오늘로 보내면 수행일은 서버 업무 날짜의 오늘이다.
  // 테스트 코드: AC-110
  it.each([undefined, '2026-11-13'])('수행일 %s이면 수행일은 오늘이다', async (actedOn) => {
    // given: 서버 시계가 T인 Fake와 Deal
    const { gateway, code } = await setup()
    // when: 수행일을 생략하거나 오늘로 등록한다
    const created = await gateway.actions.create(code, input({ actedOn }))
    // then: 수행일이 오늘 2026-11-13이다
    expect(created.actedOn).toBe('2026-11-13')
  })

  // 지난 수행일은 그 날짜 그대로 기록되고 목록에도 같은 날짜로 보인다(시각 없음).
  // 테스트 코드: AC-110
  it('지난 수행일은 시각 없이 그 날짜로 기록된다', async () => {
    // given: 서버 시계가 T인 Fake와 Deal
    const { gateway, code } = await setup()
    // when: 수행일 2026-11-10으로 등록한다
    const created = await gateway.actions.create(code, input({ actedOn: '2026-11-10' }))
    // then: 수행일은 2026-11-10이다
    expect(created.actedOn).toBe('2026-11-10')
    // then: 목록에도 같은 수행일로 보인다
    expect((await gateway.actions.list(code, {}))[0]?.actedOn).toBe('2026-11-10')
  })

  // 내일 수행일은 거절하고 아무것도 저장하지 않는다.
  // 테스트 코드: AC-110
  it('내일 수행일은 422 문구로 거절하고 Action이 늘지 않는다', async () => {
    // given: 서버 시계가 T인 Fake와 Deal
    const { gateway, code } = await setup()
    // when·then: 수행일 2026-11-14로 등록하면 422다
    await expectApiError(gateway.actions.create(code, input({ actedOn: '2026-11-14' })), 422, FUTURE)
    // then: Action이 없다
    expect(await gateway.actions.list(code, {})).toHaveLength(0)
  })

  // Deal 등록일 전날은 거절하고 당일은 받는다.
  // 테스트 코드: AC-110
  it('Deal 등록일 전날 수행일은 422이고 등록일 당일은 등록된다', async () => {
    // given: 서버 시계가 T인 Fake와 Deal(등록 11-01)
    const { gateway, code } = await setup()
    // when·then: 10-31이면 422다
    await expectApiError(gateway.actions.create(code, input({ actedOn: '2026-10-31' })), 422, BEFORE_REGISTERED)
    expect(await gateway.actions.list(code, {})).toHaveLength(0)
    // when: 등록일 당일 11-01로 등록한다
    const created = await gateway.actions.create(code, input({ actedOn: '2026-11-01' }))
    // then: 수행일 2026-11-01 그대로 기록된다
    expect(created.actedOn).toBe('2026-11-01')
  })

  // 달력에 없는 수행일은 요청 형식 오류다.
  // 테스트 코드: AC-110
  it('달력 날짜가 아닌 수행일은 422 요청 형식 오류이고 저장되지 않는다', async () => {
    // given: 서버 시계가 T인 Fake와 Deal
    const { gateway, code } = await setup()
    // when·then: 2026-13-01이면 요청 형식 오류다
    await expectApiError(gateway.actions.create(code, input({ actedOn: '2026-13-01' })), 422, '요청 형식이 올바르지 않습니다')
    expect(await gateway.actions.list(code, {})).toHaveLength(0)
  })

  // 판정 순서: 내용 오류 → 수행일 → 이전 Next Action 409.
  // 테스트 코드: AC-110
  it('수행일 판정은 내용 오류 다음, 이전 Next Action 409 앞이다', async () => {
    // given: 서버 시계가 T인 Fake, Deal, 기준 행이 아닌 id를 만들 Action 두 건
    const { gateway, code } = await setup()
    const old = await gateway.actions.create(code, input({ nextAction: '', dueDate: '', progress: '이전' }))
    await gateway.actions.create(code, input({ progress: '기준 행' }))
    // when·then: 내용이 비고 내일 수행일이면 내용 오류가 먼저다
    await expectApiError(
      gateway.actions.create(code, input({ actedOn: '2026-11-14', progress: '', nextAction: '', dueDate: '' })),
      422,
      CONTENT_REQUIRED,
    )
    // when·then: 내용이 맞고 기준 행이 아닌 id를 닫으려 해도 수행일 422가 먼저다(409 아님)
    await expectApiError(
      gateway.actions.create(code, input({ actedOn: '2026-11-14', closePreviousNextActionId: old.id })),
      422,
      FUTURE,
    )
  })

  // 기준 행보다 앞선 수행일로 종료하면 거절하고 기준 행은 Open이며, 같은 날이면 닫히고 종료일은 오늘이다.
  // 테스트 코드: AC-110
  it('기준 행보다 앞선 수행일로 닫으면 422이고, 같은 날이면 닫히며 종료일은 오늘이다', async () => {
    // given: 11-12에 수행한 Open 기준 행
    const { mock, gateway, code } = await setup()
    mock.clock.setNow('2026-11-12T10:00:00+09:00')
    const basis = await gateway.actions.create(code, input())
    mock.clock.setNow(T)
    // when·then: 수행일 11-11로 닫으면 422이고 기준 행은 Open이다
    await expectApiError(
      gateway.actions.create(code, input({ actedOn: '2026-11-11', closePreviousNextActionId: basis.id })),
      422,
      EARLIER_THAN_BASIS,
    )
    expect((await gateway.actions.list(code, {})).find((a) => a.id === basis.id)?.nextActionStatus).toBe('open')
    expect(await gateway.actions.list(code, {})).toHaveLength(1)
    // when: 같은 날 11-12로 닫으며 등록한다
    const created = await gateway.actions.create(code, input({ actedOn: '2026-11-12', closePreviousNextActionId: basis.id }))
    // then: 기준 행은 종료(수행)이고 종료일은 오늘 2026-11-13이며 새 Action의 수행일은 11-12다
    expect((await gateway.actions.list(code, {})).find((a) => a.id === basis.id)).toMatchObject({
      nextActionStatus: 'done',
      nextActionClosedOn: '2026-11-13',
    })
    expect(created.actedOn).toBe('2026-11-12')
  })
})
