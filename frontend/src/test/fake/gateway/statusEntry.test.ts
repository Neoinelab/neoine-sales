import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

/** 테스트 시계(TEST_NOW)의 서버 업무 날짜. */
const TEST_DAY = TEST_NOW.slice(0, 10)

const DAY_MS = 86_400_000

async function setup() {
  const mock = await mockAs('kim')
  const created = await mock.gateway.deals.create(dealInput(USER_ID.kim))
  return { ...mock, code: created.code, created }
}

describe('Status 진입일 (R-22, R-21)', () => {
  // Fake는 등록 때 진입일을 등록일으로, 체류 일수를 0으로 둔다.
  // 테스트 코드: RK-066
  it('starts at registration with statusDays 0', async () => {
    // when: Deal을 등록한다
    const { created } = await setup()

    // then: 진입일이 Fake 시계의 오늘이고 체류 0일이다
    expect(created).toMatchObject({ statusChangedOn: TEST_DAY, statusDays: 0 })
  })

  // 체류 일수는 Fake 시계의 달력 날짜로 세고 상세와 목록 행이 같다.
  // 테스트 코드: RK-066
  it('counts statusDays by calendar days of the mock clock, on the detail and the list row', async () => {
    // given: 방금 등록한 Deal이다
    const { gateway, clock, code } = await setup()
    // when: Fake 시계를 3일 흘려 상세와 목록을 읽는다
    clock.advance(3 * DAY_MS)

    // then: 상세 체류 3일이고 목록 행의 진입일과 체류 일수가 같다
    expect((await gateway.deals.get(code)).statusDays).toBe(3)
    const row = (await gateway.deals.list({ keyword: code })).items[0]
    expect(row).toMatchObject({ statusChangedOn: TEST_DAY, statusDays: 3 })
  })

  // 폼 수정에서 Forecast만 바꾸면 진입일이 그대로다.
  // 테스트 코드: RK-066
  it('keeps statusChangedOn when only the forecast changes via update', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: Forecast만 best로 수정한다
    const updated = await gateway.deals.update(code, { forecastKey: 'best' })

    // then: 진입일이 등록일 그대로다
    expect(updated.statusChangedOn).toBe(TEST_DAY)
  })

  // 다른 필드만 바꾸거나 같은 Status를 다시 보내도 진입일이 그대로다.
  // 테스트 코드: RK-066
  it('keeps statusChangedOn for other fields and for sending the same status again', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: 이름만 바꾸고 같은 Status를 다시 보낸다
    await gateway.deals.update(code, { name: '이름 변경' })
    const same = await gateway.deals.update(code, { statusKey: 'prospecting' })

    // then: 진입일이 등록일 그대로이고 체류 1일이다
    expect(same.statusChangedOn).toBe(TEST_DAY)
    expect(same.statusDays).toBe(1)
  })

  // 폼 수정으로 Status가 바뀌면 진입일이 요청 날짜(오늘)이 된다.
  // 테스트 코드: RK-066
  it('sets statusChangedOn to the request date when update changes the status', async () => {
    // given: 이틀이 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(2 * DAY_MS)

    // when: Status를 introduction으로 수정한다
    const updated = await gateway.deals.update(code, { statusKey: 'introduction' })

    // then: 진입일이 Fake 시계의 오늘이고 체류 0일이다
    expect(updated.statusChangedOn).toBe(clock.now().slice(0, 10))
    expect(updated.statusDays).toBe(0)
  })

  // 변경 적용은 Status를 바꿀 때만 진입일을 옮긴다.
  // 테스트 코드: RK-066
  it('moves it on applyChange of the status but not of the forecast or the amount', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    // when: Forecast만, 금액만, Status를 차례로 변경 적용한다
    const forecast = await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const amount = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 700_000_000 } })
    // then: 앞의 둘은 등록일 그대로, Status 변경은 요청 날짜(오늘)이다
    expect([forecast.deal.statusChangedOn, amount.deal.statusChangedOn]).toEqual([TEST_DAY, TEST_DAY])

    const status = await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'introduction' } })
    expect(status.deal.statusChangedOn).toBe(clock.now().slice(0, 10))
  })

  // Forecast Won으로 계약완료가 함께 바뀌면 진입일이 옮겨진다.
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

    // then: Status가 contract_completed이고 진입일이 요청 날짜(오늘)이다
    expect(result.deal.statusKey).toBe('contract_completed')
    expect(result.deal.statusChangedOn).toBe(clock.now().slice(0, 10))
  })

  // Action 등록은 status_change가 있을 때만 진입일을 옮긴다.
  // 테스트 코드: RK-066
  it('moves it only when the action registration carries a status change', async () => {
    // given: 하루가 지난 Deal이다
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)
    const base = { type: { name: '미팅' }, progress: '방문', nextAction: '견적', dueDate: '2026-10-30', comment: '' }

    // when: status_change 없는 Action, Status를 바꾸는 Action을 차례로 등록한다
    await gateway.actions.create(code, base)
    // then: 앞은 등록일 그대로, 뒤는 요청 날짜(오늘)이다
    expect((await gateway.deals.get(code)).statusChangedOn).toBe(TEST_DAY)

    await gateway.actions.create(code, { ...base, statusChanges: [{ change: { field: 'statusKey', value: 'introduction' } }] })
    expect((await gateway.deals.get(code)).statusChangedOn).toBe(clock.now().slice(0, 10))
  })

  // 시드 Deal의 조달 정보 수정은 진입일을 바꾸지 않는다.
  // 테스트 코드: RK-066
  it('does not move it for a procurement edit on a seed deal', async () => {
    // given: 시드 Deal 1이고 하루가 지났다
    const { gateway, clock } = await mockAs('kim')
    const code = dealCode(1)
    const before = (await gateway.deals.get(code)).statusChangedOn
    clock.advance(DAY_MS)

    // when: 조달 정보만 수정한다
    const after = await gateway.deals.update(code, { procurement: '변경' })

    // then: 진입일이 그대로다
    expect(after.statusChangedOn).toBe(before)
  })
})
