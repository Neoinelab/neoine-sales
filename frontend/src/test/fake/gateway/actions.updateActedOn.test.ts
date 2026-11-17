import { describe, expect, it } from 'vitest'
import { newDeal } from '../../../gateway/contract/actions.contract'
import type { ActionInput, ActionUpdateInput } from '../../../shared/model/types'
import { USER_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'

// 공통 예: 서버 시계 T = 2026-11-13T14:30+09:00(오늘 2026-11-13), Deal 등록 2026-11-01 09:00.
const REGISTERED = '2026-11-01T09:00:00+09:00'
const T = '2026-11-13T14:30:00+09:00'
const FUTURE = '수행일은 오늘 이후로 지정할 수 없습니다.'
const BEFORE_REGISTERED = '수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다.'
const CONTENT_REQUIRED = '진행사항 또는 Next Action을 입력하세요.'
const FORMAT = '요청 형식이 올바르지 않습니다'
const SUMMARY = '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01)'

/** 수행일을 함께 실을 수 있는 수정 입력(공용 `ActionUpdateInput`에 수행일이 없어도 타입이 맞는다). */
type Edit = ActionUpdateInput & { actedOn?: string | null }

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  comment: '',
  ...over,
})

const edit = (over: Partial<Edit> = {}): Edit => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  ...over,
})

/** 11-01 09:00에 Deal을 등록하고 서버 시계를 T로 맞춘 뒤 오늘(11-13) 수행일 Action 하나를 남긴다. */
async function setup() {
  const mock = await mockAs('kim', { now: REGISTERED })
  const deal = await newDeal(mock.gateway)
  mock.clock.setNow(T)
  const action = await mock.gateway.actions.create(deal.code, input())
  return { mock, gateway: mock.gateway, code: deal.code, action }
}

describe('Fake actions.update: 수행일 변경·유지·범위·판정 순서·이력(AC-R33, AC-R45, AC-R46)', () => {
  // 수행일만 고치면 수행일이 바뀌고 이력 끝에 수행일 부분이 붙는다.
  // 테스트 코드: AC-131
  it('수행일만 고치면 수행일만 바뀌고 수행일이 붙은 이력 1건이 남는다', async () => {
    // given: 오늘(11-13) 수행일 Action과 수정 전 이력 건수
    const { gateway, code, action } = await setup()
    const base = (await gateway.history.list(code, {})).length
    // when: 내용은 그대로 두고 수행일을 11-10으로 고친다
    const updated = await gateway.actions.update(action.id, edit({ actedOn: '2026-11-10' }))
    // then: 수행일만 바뀌고 담당자·스냅숏·Next Action 상태는 그대로다
    expect(updated).toMatchObject({
      actedOn: '2026-11-10',
      progress: '고객사 방문',
      actor: action.actor,
      statusKey: action.statusKey,
      nextActionStatus: 'open',
    })
    // then: 이력이 1건 늘고 변경 전·후 끝에 수행일이 붙는다
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({
      category: 'action',
      target: 'Action',
      before: `${SUMMARY} / 수행일: 2026-11-13`,
      after: `수정: ${SUMMARY} / 수행일: 2026-11-10`,
    })
  })

  // 수행일과 내용을 함께 고치면 이력 1건에 둘 다 반영된다.
  // 테스트 코드: AC-131
  it('수행일과 내용을 함께 고치면 이력 1건에 둘 다 반영된다', async () => {
    // given: 오늘 수행일 Action과 수정 전 이력 건수
    const { gateway, code, action } = await setup()
    const base = (await gateway.history.list(code, {})).length
    // when: 진행사항과 수행일을 함께 고친다
    await gateway.actions.update(action.id, edit({ progress: '제안 발표', actedOn: '2026-11-10' }))
    // then: 이력 1건에 새 요약과 수행일이 있다
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]?.before).toBe(`${SUMMARY} / 수행일: 2026-11-13`)
    expect(history[0]?.after).toBe('수정: 미팅 · 제안 발표 / Next Action: 견적 재전달 (Due 2026-12-01) / 수행일: 2026-11-10')
  })

  // 수행일을 생략·null·같은 날짜로 보내면 수행일을 그대로 두고, 내용도 같으면 이력이 없다.
  // 테스트 코드: AC-131
  it.each([undefined, null, '2026-11-13'])('수행일 %s와 같은 내용이면 아무것도 바뀌지 않는다', async (actedOn) => {
    // given: 오늘 수행일 Action과 수정 전 이력 건수
    const { gateway, code, action } = await setup()
    const base = (await gateway.history.list(code, {})).length
    // when: 같은 내용에 수행일을 생략·null·같은 날짜로 고친다
    const updated = await gateway.actions.update(action.id, edit({ actedOn }))
    // then: 수행일 그대로이고 이력이 늘지 않는다
    expect(updated.actedOn).toBe('2026-11-13')
    expect(await gateway.history.list(code, {})).toHaveLength(base)
  })

  // 수행일 없이 내용만 고치면 수행일은 그대로이고 이력에 수행일 부분이 없다.
  // 테스트 코드: AC-131
  it('수행일 없이 내용만 고치면 수행일은 그대로이고 이력에 수행일 부분이 없다', async () => {
    // given: 지난 수행일(11-10) Action
    const { gateway, code } = await setup()
    const past = await gateway.actions.create(code, input({ actedOn: '2026-11-10', progress: '지난 일' }))
    // when: 수행일 없이 진행사항만 고친다
    const updated = await gateway.actions.update(past.id, edit({ progress: '고친 일' }))
    // then: 수행일은 11-10 그대로이고 이력에 "수행일" 문구가 없다
    expect(updated.actedOn).toBe('2026-11-10')
    const [latest] = await gateway.history.list(code, {})
    expect(latest?.after).toBe('수정: 미팅 · 고친 일 / Next Action: 견적 재전달 (Due 2026-12-01)')
    expect(latest?.before).not.toContain('수행일')
  })

  // 내일 수행일은 422이고 Action·이력·새 유형이 그대로다. 오늘은 된다.
  // 테스트 코드: AC-131
  it('내일 수행일은 422이고 Action·새 유형이 그대로이며 오늘은 받는다', async () => {
    // given: 지난 수행일 Action, 수정 전 이력 건수·유형 수
    const { gateway, code } = await setup()
    const past = await gateway.actions.create(code, input({ actedOn: '2026-11-10', progress: '지난 일' }))
    const base = (await gateway.history.list(code, {})).length
    const types = (await gateway.actionTypes.list()).length
    // when·then: 새 유형과 함께 내일(11-14)로 고치면 422다
    await expectApiError(gateway.actions.update(past.id, edit({ actedOn: '2026-11-14', type: { name: '새 유형' } })), 422, FUTURE)
    // then: 수행일·이력·유형이 그대로다
    expect((await gateway.actions.list(code, {})).find((a) => a.id === past.id)?.actedOn).toBe('2026-11-10')
    expect(await gateway.history.list(code, {})).toHaveLength(base)
    expect(await gateway.actionTypes.list()).toHaveLength(types)
    // when: 오늘(11-13)로 고친다
    const updated = await gateway.actions.update(past.id, edit({ actedOn: '2026-11-13', progress: '지난 일' }))
    // then: 받는다
    expect(updated.actedOn).toBe('2026-11-13')
  })

  // Deal 등록일 전날은 422이고 등록일 당일은 받는다.
  // 테스트 코드: AC-131
  it('Deal 등록일 전날 수행일은 422이고 등록일 당일은 받는다', async () => {
    // given: 오늘 수행일 Action
    const { gateway, action } = await setup()
    // when·then: 10-31이면 422다
    await expectApiError(gateway.actions.update(action.id, edit({ actedOn: '2026-10-31' })), 422, BEFORE_REGISTERED)
    expect((await gateway.actions.list(action.dealCode, {}))[0]?.actedOn).toBe('2026-11-13')
    // when: 등록일 당일 11-01로 고친다
    const updated = await gateway.actions.update(action.id, edit({ actedOn: '2026-11-01' }))
    // then: 받는다
    expect(updated.actedOn).toBe('2026-11-01')
  })

  // 달력에 없는 수행일은 요청 형식 오류이고 없는 Action 404보다 먼저다.
  // 테스트 코드: AC-131
  it('달력 날짜가 아닌 수행일은 422 요청 형식 오류이고 없는 Action 404보다 먼저다', async () => {
    // given: 서버 시계가 T인 Fake
    const { gateway } = await setup()
    // when·then: 없는 id에 2026-13-01을 보내도 요청 형식 오류다
    await expectApiError(gateway.actions.update(999_999, edit({ actedOn: '2026-13-01' })), 422, FORMAT)
  })

  // 판정 순서: 404 → 403 → 유형 → 내용 → 수행일.
  // 테스트 코드: AC-131
  it('판정 순서는 없는 Action 404, 담당자 아님 403, 내용 오류, 수행일 순이다', async () => {
    // given: kim의 Action과 다른 sales(lee)가 로그인한 같은 저장소
    const { mock, gateway, action } = await setup()
    // when·then: 없는 id는 내일 수행일이어도 404다
    await expectApiError(gateway.actions.update(999_999, edit({ actedOn: '2026-11-14' })), 404, 'Action을 찾을 수 없습니다.')
    // when·then: 내용이 비고 내일 수행일이면 내용 오류가 먼저다
    await expectApiError(
      gateway.actions.update(action.id, edit({ actedOn: '2026-11-14', progress: '', nextAction: '', dueDate: '' })),
      422,
      CONTENT_REQUIRED,
    )
    // when: lee로 바꿔 kim의 Action을 내일 수행일로 고친다
    await mock.signInAs(USER_ID.lee)
    // then: 수행일 오류가 아니라 수정 권한 오류다
    await expectApiError(mock.gateway.actions.update(action.id, edit({ actedOn: '2026-11-14' })), 403, '본인 Action 또는 admin만 수정할 수 있습니다.')
  })

  // 기준 행·종료일·닫은 Action과의 선후는 보지 않고, 목록 순서·최종 업데이트일은 바뀐 수행일로 다시 계산된다.
  // 테스트 코드: AC-131
  it('수행일을 고치면 선후를 따지지 않고 목록 순서와 최종 업데이트일이 다시 계산된다', async () => {
    // given: 오늘 수행한 기준 행 X, X를 닫으며 오늘 등록한 Y
    const { gateway, code, action } = await setup()
    const closing = await gateway.actions.create(code, input({ progress: 'Y', closePreviousNextActionId: action.id }))
    // when: Y의 수행일을 자기가 닫은 X의 수행일(오늘)보다 앞선 11-02로 고친다
    const updated = await gateway.actions.update(closing.id, edit({ progress: 'Y', actedOn: '2026-11-02' }))
    // then: 거절되지 않고 수행일만 바뀌며 X의 종료(수행) 상태는 그대로다
    expect(updated.actedOn).toBe('2026-11-02')
    expect((await gateway.actions.list(code, {})).find((a) => a.id === action.id)?.nextActionStatus).toBe('done')
    // then: 목록 순서는 수행일 내림차순(X 11-13 → Y 11-02)이고 최종 업데이트일은 11-13이다
    expect((await gateway.actions.list(code, {})).map((a) => a.id)).toEqual([action.id, closing.id])
    expect((await gateway.deals.get(code)).lastUpdatedOn).toBe('2026-11-13')
  })
})
