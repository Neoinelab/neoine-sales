import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

const RANGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

describe('alerts.get (R-23)', () => {
  // Fake는 저장한 적이 없으면 모든 역할에게 14일과 빈 저장 기록을 준다.
  // 테스트 코드: RK-066
  it('answers the default 14 days, never saved, to every role', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      // when: admin·sales·user로 경고 기준을 조회한다
      const { gateway } = await mockAs(key)
      // then: {staleDays: 14, updatedAt: null, updatedBy: null}이다
      expect(await gateway.alerts.get()).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
    }
  })

  // 세션이 없으면 401이다.
  it('answers 401 without a session', async () => {
    const { gateway } = await mockAs(null)
    // when·then: 세션 없이 조회한다 → 401 ApiError다
    await expectApiError(gateway.alerts.get(), 401)
  })
})

describe('alerts.save (R-23)', () => {
  // Fake는 값과 저장자, Fake 시계 시각을 저장하고 다시 읽어도 같다.
  // 테스트 코드: RK-066
  it('stores the value with the saver and the mock clock time', async () => {
    // given: admin으로 로그인했다
    const { gateway } = await mockAs('root')

    // when: 30일로 저장한다
    const saved = await gateway.alerts.save(30)

    // then: 30일, Fake 시계 시각, 저장자 admin이 나오고 다시 읽어도 같다
    expect(saved).toMatchObject({ staleDays: 30, updatedAt: TEST_NOW, updatedBy: { id: USER_ID.root, role: 'admin' } })
    expect(await gateway.alerts.get()).toEqual(saved)
  })

  // sales·user의 저장은 403이고 값은 그대로다.
  // 테스트 코드: RK-066
  it('refuses sales and user with 403 and keeps the value', async () => {
    for (const key of ['kim', 'han'] as const) {
      // given: sales 또는 user로 로그인했다
      const mock = await mockAs(key)
      // when: 30일로 저장하려 한다
      await expectApiError(mock.gateway.alerts.save(30), 403)
      // then: 값은 14일 그대로다
      expect((await mock.gateway.alerts.get()).staleDays).toBe(14)
    }
  })

  // 범위 밖 정수는 422 범위 문장이고 값은 그대로다.
  // 테스트 코드: RK-066
  it.each([0, 366, -1])('rejects %s with 422 and the range sentence, keeping the value', async (value) => {
    // given: admin으로 로그인했다
    const { gateway } = await mockAs('root')

    // when: 범위 밖 값을 저장하려 한다
    await expectApiError(gateway.alerts.save(value), 422, RANGE)

    // then: 값은 14일 그대로다
    expect((await gateway.alerts.get()).staleDays).toBe(14)
  })

  // 정수가 아닌 값은 서버처럼 422 request-validation이고 값은 그대로다.
  // 테스트 코드: RK-066
  it.each([1.5, Number.NaN])('rejects the non-integer %s like the server: 422 request-validation, keeping the value', async (value) => {
    // given: admin으로 로그인했다
    const { gateway } = await mockAs('root')

    // when: 정수가 아닌 값을 저장하려 한다
    const error = await gateway.alerts.save(value).catch((e: unknown) => e)

    // then: request-validation 문구의 422이고 값은 14일 그대로다
    expect(error).toMatchObject({ status: 422, kind: 'validation', problem: { type: expect.stringMatching(/validation$/), detail: '요청 형식이 올바르지 않습니다' } })
    expect((await gateway.alerts.get()).staleDays).toBe(14)
  })

  // 경계값 1과 365는 저장된다.
  // 테스트 코드: RK-066
  it.each([1, 365])('accepts the boundary %s', async (value) => {
    // given: admin으로 로그인했다
    const { gateway } = await mockAs('root')

    // when: 경계값을 저장한다
    const actual = (await gateway.alerts.save(value)).staleDays

    // then: 저장된 값이 그 경계값이다
    expect(actual).toBe(value)
  })

  // resetData를 부르면 경고 기준이 14로 돌아간다.
  it('is reset to 14 by resetData', async () => {
    const mock = await mockAs('root')
    // given: 30일로 저장했다
    await mock.gateway.alerts.save(30)

    // when: Fake 데이터를 초기화한다
    mock.control.resetData()

    // then: 기본값 14와 빈 저장 기록이다
    expect(await mock.gateway.alerts.get()).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
  })
})

describe('risk follows the saved threshold (R-19)', () => {
  // 시드 Deal 4(새론병원 PAM)는 마지막 갱신이 21일 전이고 Due Date가 미래다.
  // Fake의 경고는 저장된 기준을 따라 21일 된 Deal이 21에서 stale, 22와 30에서 정상이다.
  // 테스트 코드: RK-066
  it('turns the 21-day-old deal stale at 21 and healthy at 22 or at 30', async () => {
    // given: 시드 Deal 4는 21일 전에 마지막 갱신되었고 Due가 미래다
    const { gateway } = await mockAs('root')
    const riskOf = async () => (await gateway.deals.get(dealCode(4))).risk

    // then: 기준 22에서 정상(null), 21에서 stale, 30에서 정상이다
    expect(await riskOf()).toBe('stale')
    // when: 기준을 22, 21, 30으로 차례로 저장한다
    await gateway.alerts.save(22)
    expect(await riskOf()).toBeNull()
    await gateway.alerts.save(21)
    expect(await riskOf()).toBe('stale')
    await gateway.alerts.save(30)
    expect(await riskOf()).toBeNull()
  })

  // 목록 행도 저장된 기준으로 판정한다.
  // 테스트 코드: RK-066
  it('applies the threshold to the list rows too', async () => {
    // given: admin으로 로그인했다
    const { gateway } = await mockAs('root')
    // when: 기준을 30일로 저장하고 목록을 읽는다
    await gateway.alerts.save(30)

    const rows = (await gateway.deals.list({ limit: 100 })).items

    // then: 21일 된 Deal 행의 risk가 null이다
    expect(rows.find((d) => d.code === dealCode(4))?.risk).toBeNull()
  })

  // 기준 3일이면 3일 된 Deal이 stale이다.
  // 테스트 코드: RK-066
  it('makes a 3-day-old deal stale at a 3-day threshold', async () => {
    // given: 시드 Deal 6은 3일 전에 마지막 갱신되었다
    const { gateway } = await mockAs('root')
    // when: 기준을 3일로 저장하고 상세를 읽는다
    await gateway.alerts.save(3)

    // 시드 Deal 6(푸른물류 SSO)은 마지막 갱신 3일 전, Due Date 미래, Forecast pipeline.
    // then: risk가 stale이다
    expect((await gateway.deals.get(dealCode(6))).risk).toBe('stale')
  })
})
