import { describe, expect, it } from 'vitest'
import { REQUEST_VALIDATION_MESSAGE } from '../errors'
import { dealInput, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

/**
 * Fake 대시보드 규칙(서버와 같은 규칙을 시드에서 직접 계산): Lost 제외, 분기 경계, 오늘 기준 이번 달·분기,
 * 주의 타일의 기간 무시, 범위 밖 연도·분기는 서버와 같은 422(DSH-R29). 기준일은 Fake 시계(2026-10-15)다.
 * 서버와의 일치는 계약 스위트(dashboard.contract)가 본다. 이 파일은 BDD 케이스가 아닌 Fake 자체 테스트다.
 */

const NOW_2026_12_31 = '2026-12-31T12:00:00+09:00'

describe('Fake 대시보드 요약', () => {
  it('Forecast 타일과 Status 항목에서 Lost Deal은 빼고 Won은 넣는다', async () => {
    // given: 같은 해에 Lost 9백만, Won 4백만, Open 1백만 Deal이 있다
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Lost 제외', forecastKey: 'lost', statusKey: 'price_negotiation', revenueDate: '2031-05-05', revenueAmount: 9_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Won 포함', forecastKey: 'won', statusKey: 'contract_completed', revenueDate: '2031-05-06', revenueAmount: 4_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Open 포함', forecastKey: 'commit', statusKey: 'prospecting', revenueDate: '2031-05-07', revenueAmount: 1_000_000 }))

    // when: 그 연도 요약을 조회한다
    const { forecast, statuses } = await gateway.dashboard.summary({ year: 2031 })

    // then: Lost 열은 없고 Won은 있으며 Lost 금액은 Status 어디에도 없다
    expect(forecast.columns.map((c) => c.key)).not.toContain('lost')
    expect(forecast.cells.commit).toEqual({ count: 1, amount: 1_000_000 })
    expect(forecast.cells.won).toEqual({ count: 1, amount: 4_000_000 })
    expect(forecast.openTotal).toEqual({ count: 1, amount: 1_000_000 })
    expect(statuses.items.find((i) => i.key === 'price_negotiation')).toMatchObject({ count: 0, amount: 0 })
    expect(statuses.items.find((i) => i.key === 'contract_completed')).toMatchObject({ count: 1, amount: 4_000_000 })
    expect(statuses.total).toEqual({ count: 2, amount: 5_000_000 })
  })

  it('맞는 Deal이 없어도 모든 Status 코드를 순서대로 0으로 나열한다', async () => {
    // given: Deal이 없는 연도
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    // when: 2099년 요약을 조회한다
    const { statuses } = await gateway.dashboard.summary({ year: 2099 })

    // then: 코드 7개가 순서대로 0이다
    expect(statuses.items.map((i) => i.key)).toEqual(['prospecting', 'introduction', 'poc_preparation', 'poc_completed', 'technical_evaluation', 'price_negotiation', 'contract_completed'])
    expect(statuses.items.every((i) => i.count === 0 && i.amount === 0)).toBe(true)
    expect(statuses.total).toEqual({ count: 0, amount: 0 })
  })

  it('12월 31일은 그 해 Q4, 1월 1일은 다음 해 Q1에 든다', async () => {
    // given: Expected Close가 2032-12-31, 2033-01-01인 Deal
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 12/31', revenueDate: '2032-12-31', forecastKey: 'commit', revenueAmount: 7_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 1/1', revenueDate: '2033-01-01', forecastKey: 'best', revenueAmount: 3_000_000 }))

    // when: 2032년과 2033년 요약을 조회한다
    const y2032 = await gateway.dashboard.summary({ year: 2032 })
    const y2033 = await gateway.dashboard.summary({ year: 2033 })

    // then: 12-31은 2032 Q4에, 01-01은 2033 Q1에 있다
    expect(y2032.quarters[3]?.total).toEqual({ count: 1, amount: 7_000_000 })
    expect(y2032.quarters[0]?.total).toEqual({ count: 0, amount: 0 })
    expect(y2033.quarters[0]?.total).toEqual({ count: 1, amount: 3_000_000 })
  })

  it('어느 분기를 골라도 분기 행은 Q1~Q4 순서이고 위쪽 부분만 좁아진다', async () => {
    // given: Q1·Q3에 Deal이 하나씩 있다
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Q1', revenueDate: '2034-02-01', forecastKey: 'commit', revenueAmount: 1_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Q3', revenueDate: '2034-08-01', forecastKey: 'commit', revenueAmount: 2_000_000 }))

    // when: Q3를 골라 조회한다
    const q3 = await gateway.dashboard.summary({ year: 2034, quarters: [3] })

    // then: 분기 행은 네 개이고 Status·타일은 Q3만 센다
    expect(q3.quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
    expect(q3.quarters.map((q) => q.total.count)).toEqual([1, 0, 1, 0])
    expect(q3.statuses.total).toEqual({ count: 1, amount: 2_000_000 })
    expect(q3.forecast.cells.commit).toEqual({ count: 1, amount: 2_000_000 })
  })

  it('이번 달·이번 분기 건수는 Fake 시계의 업무 날짜 기준 Open Deal만 센다', async () => {
    // given: 10월 Open, 10월 Lost, 12월 Open Deal
    const { gateway, clock } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '이번 달 Open', revenueDate: '2026-10-30', forecastKey: 'commit' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '이번 달 Lost', revenueDate: '2026-10-31', forecastKey: 'lost' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '다음 달 Open', revenueDate: '2026-12-01', forecastKey: 'best' }))

    // when: 10월 15일과 12월 31일에 각각 요약을 조회한다
    const before = (await gateway.dashboard.summary({ year: 2020 })).attention
    const openIn = async (month: number) =>
      (await gateway.deals.list({ year: 2026, month, limit: 200 })).items.filter((d) => d.forecastKey !== 'lost' && d.forecastKey !== 'won').length
    const octoberOpen = await openIn(10)
    clock.setNow(NOW_2026_12_31)
    const after = (await gateway.dashboard.summary({ year: 2020 })).attention

    // then: 이번 달은 업무 날짜의 월·Open 목록 건수와 같고 이번 분기는 Q4다
    expect(before.closingThisMonth).toMatchObject({ year: 2026, month: 10, count: octoberOpen })
    expect(octoberOpen).toBeGreaterThanOrEqual(1)
    expect(before.closingThisQuarter).toMatchObject({ year: 2026, quarter: 4 })
    expect(after.closingThisMonth).toMatchObject({ year: 2026, month: 12, count: await openIn(12) })
    expect(after.closingThisQuarter).toMatchObject({ year: 2026, quarter: 4, count: before.closingThisQuarter.count })
  })

  it('1월 1일이면 새해의 1월·Q1로 바뀐다', async () => {
    // given: Fake 시계가 2027-01-01이다
    const { gateway, clock } = await mockAs('kim', { now: TEST_NOW })
    clock.setNow('2027-01-01T12:00:00+09:00')

    // when: 2026년 요약을 조회한다
    const { attention, today } = await gateway.dashboard.summary({ year: 2026 })

    // then: 업무 날짜와 이번 달·이번 분기가 새해다
    expect(today).toBe('2027-01-01')
    expect(attention.closingThisMonth).toMatchObject({ year: 2027, month: 1 })
    expect(attention.closingThisQuarter).toMatchObject({ year: 2027, quarter: 1 })
  })

  it('주의 건수는 연도·분기를 무시하고 담당자만 따른다', async () => {
    // given: Fake 시드 데이터
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    // when: 연도·분기를 바꿔 조회하고 담당자 조건도 준다
    const whole = await gateway.dashboard.summary({ year: 2026 })
    const other = await gateway.dashboard.summary({ year: 1999, quarters: [2] })
    const mine = await gateway.dashboard.summary({ year: 1999, ownerId: USER_ID.kim })

    // then: 연도·분기가 달라도 같고 담당자 조건은 전체를 넘지 않는다
    expect(other.attention).toEqual(whole.attention)
    expect(mine.attention.overdue).toBeLessThanOrEqual(whole.attention.overdue)
    expect(mine.attention.stale).toBeLessThanOrEqual(whole.attention.stale)
  })

  it.each([
    ['연도 1899', { year: 1899 }],
    ['연도 10000', { year: 10000 }],
    ['소수 연도', { year: 2026.5 }],
    ['분기 0', { year: 2026, quarters: [0] }],
    ['분기 5', { year: 2026, quarters: [5] }],
    ['분기 5개', { year: 2026, quarters: [1, 2, 3, 4, 2] }],
  ] as const)('범위 밖 값(%s)은 서버와 같은 422 request-validation 문구다', async (_name, query) => {
    // given: 로그인한 사용자
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    // when·then: 범위 밖 값으로 조회하면 공통 요청 형식 오류(Fake 고유 문구 없음)다
    const error = await expectApiError(gateway.dashboard.summary({ ...query } as never), 422, REQUEST_VALIDATION_MESSAGE)
    expect(error.problem?.type).toMatch(/\/validation$/)
  })

  it('연도 경계 1900·9999와 분기 네 개는 받아들인다', async () => {
    // given: 로그인한 사용자
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    // when: 경계 연도와 분기 1~4로 조회한다
    const low = await gateway.dashboard.summary({ year: 1900 })
    const high = await gateway.dashboard.summary({ year: 9999, quarters: [1, 2, 3, 4] })

    // then: 오류 없이 응답한다(넷 다는 분기 조건 없음)
    expect(low.period.year).toBe(1900)
    expect(high.period.quarters).toEqual([])
  })

  it('로그인하지 않으면 401이다', async () => {
    // given: 로그인하지 않은 상태
    const { gateway } = await mockAs(null, { now: TEST_NOW })

    // when·then: 요약을 조회하면 401이다
    await expectApiError(gateway.dashboard.summary({ year: 2026 }), 401)
  })
})
