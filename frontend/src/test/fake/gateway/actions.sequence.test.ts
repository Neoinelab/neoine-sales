import { describe, expect, it } from 'vitest'
import { SYNC_CONFLICT_MESSAGE } from '../../../shared/model/sync'
import type { ActionInput, StatusChangeRequest } from '../../../shared/model/types'
import { dealCode, expectApiError, mockAs } from '../testing'

const CLOSING = { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' }
const INVALID_FORM = '요청 형식이 올바르지 않습니다'

const input = (statusChanges?: StatusChangeRequest[]): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  comment: '',
  ...(statusChanges ? { statusChanges } : {}),
})

const status = (value: string, resolution?: StatusChangeRequest['resolution']): StatusChangeRequest => ({
  change: { field: 'statusKey', value },
  ...(resolution ? { resolution } : {}),
})
const forecast = (value: string, resolution?: StatusChangeRequest['resolution']): StatusChangeRequest => ({
  change: { field: 'forecastKey', value },
  ...(resolution ? { resolution } : {}),
})

async function snapshot(gateway: Awaited<ReturnType<typeof mockAs>>['gateway'], code: string) {
  const deal = await gateway.deals.get(code)
  return {
    sync: [deal.statusKey, deal.forecastKey],
    actions: (await gateway.actions.list(code, {})).length,
    history: (await gateway.history.list(code, {})).length,
  }
}

describe('actions.create with statusChanges (two changes)', () => {
  // 두 변경을 모두 적용하고 변경 뒤 값을 저장하며 이력은 변경 순서 다음 등록이다.
  // 테스트 코드: AC-090
  it('applies both changes, stores the post-change values and logs them in order before the action', async () => {
    // given: sales(kim)와 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)

    // when: Status 제품소개, Forecast Best로 바꾸며 등록한다
    const created = await gateway.actions.create(code, input([status('introduction'), forecast('best')]))

    // then: Action 스냅숏이 변경 뒤 값이다
    expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
    // when: Deal을 읽는다
    const deal = await gateway.deals.get(code)
    // then: Deal도 바뀐다
    expect([deal.statusKey, deal.forecastKey]).toEqual(['introduction', 'best'])
    // then: 이력 최신 순서는 Action, Forecast, Status다
    const newestFirst = (await gateway.history.list(code, {})).slice(0, 3).map((h) => h.category)
    expect(newestFirst).toEqual(['action', 'forecast', 'status'])
  })

  // 두 번째 변경은 첫 변경을 적용한 상태로 판정한다.
  // 테스트 코드: AC-090
  it('judges the second change after the first (reopen a won deal, then move the status)', async () => {
    // given: sales(kim)와 Won Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)

    // when: Forecast Commit(답 PoC완료) 뒤 Status 제품소개로 바꾸며 등록한다
    const created = await gateway.actions.create(
      code,
      input([forecast('commit', { statusKey: 'poc_completed' }), status('introduction')]),
    )

    // then: 스냅숏은 제품소개·Commit이다
    expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'commit' })
  })

  // 첫 변경을 뒤집는 두 번째 변경은 422이고 아무것도 저장되지 않는다.
  // 테스트 코드: AC-090
  it('rejects a second change that overrides the first and stores nothing', async () => {
    // given: sales(kim)와 등록 전 Deal·Action·History 상태
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    // when·then: Status 제품소개 뒤 Forecast Won은 충돌 422다
    await expectApiError(
      gateway.actions.create(code, input([status('introduction'), forecast('won', CLOSING)])),
      422,
      SYNC_CONFLICT_MESSAGE,
    )

    // then: Deal·Action·History가 그대로다
    expect(await snapshot(gateway, code)).toEqual(before)
  })

  // 두 번째 변경이 실패하면 첫 변경도 저장되지 않는다.
  // 테스트 코드: AC-090
  it('does not keep the first change when the second one fails', async () => {
    // given: Lost Deal과 등록 전 상태
    const { gateway } = await mockAs('kim')
    const code = dealCode(16) // price_negotiation / lost
    const before = await snapshot(gateway, code)

    // when·then: Status 제품소개 뒤 답 없는 Forecast Commit은 선택 필수 422다
    await expectApiError(
      gateway.actions.create(code, input([status('introduction'), forecast('commit')])),
      422,
      '함께 바꿀 값을 선택하세요.',
    )

    // then: Deal·Action·History가 그대로다
    expect(await snapshot(gateway, code)).toEqual(before)
  })

  // 매출 판정 전에 모든 코드의 존재를 먼저 확인한다.
  // 테스트 코드: AC-090
  it('checks that every code exists before judging revenue (unknown code wins over a missing revenue)', async () => {
    // given: sales(kim)와 등록 전 상태
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    // when·then: 매출 없는 계약완료 뒤 없는 Forecast 코드는 코드 없음 422다
    await expectApiError(
      gateway.actions.create(code, input([status('contract_completed'), forecast('no_such_forecast')])),
      422,
      '존재하지 않는 코드입니다.',
    )

    // then: Deal·Action·History가 그대로다
    expect(await snapshot(gateway, code)).toEqual(before)
  })

  // 같은 필드를 두 번 바꾸거나 3건이면 요청 형식 오류다.
  // 테스트 코드: AC-090
  it.each([
    ['같은 필드를 두 번 바꾸는 목록', [status('introduction'), status('poc_completed')]],
    ['3건짜리 목록', [status('introduction'), forecast('best'), status('poc_completed')]],
  ])('%s은 요청 형식 오류로 거절한다', async (_name, changes) => {
    // given: sales(kim)와 등록 전 상태
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    // when·then: 해당 목록으로 등록하면 요청 형식 422다
    await expectApiError(gateway.actions.create(code, input(changes)), 422, INVALID_FORM)

    // then: Deal·Action·History가 그대로다
    expect(await snapshot(gateway, code)).toEqual(before)
  })

  // 잘못된 목록은 Deal 조회(404)보다 먼저 요청 형식 오류다.
  // 테스트 코드: AC-090
  it('rejects a malformed list as a request error before looking up the deal (like server request validation)', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal에 중복 목록으로 등록하면 404가 아닌 요청 형식 422다
    await expectApiError(
      gateway.actions.create('NO-SUCH-DEAL', input([status('introduction'), status('proposal')])),
      422,
      INVALID_FORM,
    )
  })

  // 빈 목록은 변경 없음이다.
  // 테스트 코드: AC-090
  it('treats an empty list as no change', async () => {
    // given: sales(kim)와 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)

    // when: 빈 변경 목록으로 등록한다
    const created = await gateway.actions.create(code, input([]))

    // then: 스냅숏은 현재 Status·Forecast다
    expect(created).toMatchObject({ statusKey: 'price_negotiation', forecastKey: 'commit' })
  })
})
