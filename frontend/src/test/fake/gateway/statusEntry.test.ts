import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

const DAY_MS = 86_400_000

async function setup() {
  const mock = await mockAs('kim')
  const created = await mock.gateway.deals.create(dealInput(USER_ID.kim))
  return { ...mock, code: created.code, created }
}

describe('Status 진입 시각 (R-22, R-21)', () => {
  // Fake는 등록 때 진입 시각을 등록 시각으로, 체류 일수를 0으로 둔다.
  // 테스트 코드: RK-066
  it('starts at registration with statusDays 0', async () => {
    // when: Deal을 등록한다
    const { created } = await setup()

    // then: 진입 시각이 Fake 시계 시각이고 체류 0일이다
    expect(created).toMatchObject({ statusChangedAt: TEST_NOW, statusDays: 0 })
  })

  // 체류 일수는 Fake 시계의 달력 날짜로 세고 상세와 목록 행이 같다.
  // 테스트 코드: RK-066
  it('counts statusDays by calendar days of the mock clock, on the detail and the list row', async () => {
    // given: 방금 등록한 Deal이다
    const { gateway, clock, code } = await setup()
    // when: Fake 시계를 3일 흘려 상세와 목록을 읽는다
    clock.advance(3 * DAY_MS)

    // then: 상세 체류 3일이고 목록 행의 진입 시각과 체류 일수가 같다
    expect((await gateway.deals.get(code)).statusDays).toBe(3)
    const row = (await gateway.deals.list({ keyword: code })).items[0]
    expect(row).toMatchObject({ statusChangedAt: TEST_NOW, statusDays: 3 })
  })

  // 폼 수정에서 Forecast만 바꾸면 진입 시각이 그대로다.
  // 테스트 코드: RK-066
  it('keeps statusChangedAt when only the forecast changes via update', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: Forecast만 best로 수정한다
    const updated = await gateway.deals.update(code, { forecastKey: 'best' })

    // then: 진입 시각이 등록 시각 그대로다
    expect(updated.statusChangedAt).toBe(TEST_NOW)
  })

  // 다른 필드만 바꾸거나 같은 Status를 다시 보내도 진입 시각이 그대로다.
  // 테스트 코드: RK-066
  it('keeps statusChangedAt for other fields and for sending the same status again', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: 이름만 바꾸고 같은 Status를 다시 보낸다
    await gateway.deals.update(code, { name: '이름 변경' })
    const same = await gateway.deals.update(code, { statusKey: 'prospecting' })

    // then: 진입 시각이 등록 시각 그대로이고 체류 1일이다
    expect(same.statusChangedAt).toBe(TEST_NOW)
    expect(same.statusDays).toBe(1)
  })

  // 폼 수정으로 Status가 바뀌면 진입 시각이 요청 시각이 된다.
  // 테스트 코드: RK-066
  it('sets statusChangedAt to the request time when update changes the status', async () => {
    // given: 이틀이 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(2 * DAY_MS)

    // when: Status를 introduction으로 수정한다
    const updated = await gateway.deals.update(code, { statusKey: 'introduction' })

    // then: 진입 시각이 Fake 시계 시각이고 체류 0일이다
    expect(updated.statusChangedAt).toBe(clock.now())
    expect(updated.statusDays).toBe(0)
  })

  // 변경 적용은 Status를 바꿀 때만 진입 시각을 옮긴다.
  // 테스트 코드: RK-066
  it('moves it on applyChange of the status but not of the forecast or the amount', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: Forecast만, 금액만, Status를 차례로 변경 적용한다
    const forecast = await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const amount = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 700_000_000 } })
    // then: 앞의 둘은 등록 시각 그대로, Status 변경은 요청 시각이다
    expect([forecast.deal.statusChangedAt, amount.deal.statusChangedAt]).toEqual([TEST_NOW, TEST_NOW])

    const status = await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'introduction' } })
    expect(status.deal.statusChangedAt).toBe(clock.now())
  })

  // Forecast Won으로 계약완료가 함께 바뀌면 진입 시각이 옮겨진다.
  // 테스트 코드: RK-066
  it('moves it when the contract completion also changes the status (forecast to Won)', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: Forecast를 won으로 변경 적용한다
    const result = await gateway.deals.applyChange(code, {
      change: { field: 'forecastKey', value: 'won' },
      resolution: { revenueAmount: 500_000_000, revenueDate: '2026-10-16' },
    })

    // then: Status가 contract_completed이고 진입 시각이 요청 시각이다
    expect(result.deal.statusKey).toBe('contract_completed')
    expect(result.deal.statusChangedAt).toBe(clock.now())
  })

  // Action 등록은 status_change가 있을 때만 진입 시각을 옮긴다.
  // 테스트 코드: RK-066
  it('moves it only when the action registration carries a status change', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)
    const base = { type: { name: '미팅' }, progress: '방문', nextAction: '견적', dueDate: '2026-10-30', memo: '' }

    // when: status_change 없는 Action, Status를 바꾸는 Action을 차례로 등록한다
    await gateway.actions.create(code, base)
    // then: 앞은 등록 시각 그대로, 뒤는 요청 시각이다
    expect((await gateway.deals.get(code)).statusChangedAt).toBe(TEST_NOW)

    await gateway.actions.create(code, { ...base, statusChanges: [{ change: { field: 'statusKey', value: 'introduction' } }] })
    expect((await gateway.deals.get(code)).statusChangedAt).toBe(clock.now())
  })

  // 시드 Deal의 조달 정보 수정은 진입 시각을 바꾸지 않는다.
  // 테스트 코드: RK-066
  it('does not move it for a procurement edit on a seed deal', async () => {
    // given: 시드 Deal 1이고 하루가 지났다
    const { gateway, clock } = await mockAs('kim')
    const code = dealCode(1)
    const before = (await gateway.deals.get(code)).statusChangedAt
    clock.advance(DAY_MS)

    // when: 조달 정보만 수정한다
    const after = await gateway.deals.update(code, { procurement: '변경' })

    // then: 진입 시각이 그대로다
    expect(after.statusChangedAt).toBe(before)
  })
})
