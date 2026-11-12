import { describe, expect, it } from 'vitest'
import { activeFilters, filtersFromParams, paramsFromFilters, patchActive, queryOf, type DashboardFilters } from './dashboardParams'

const params = (query: string) => new URLSearchParams(query)

const DEFAULTS = { year: 2026, quarters: [] }

describe('filtersFromParams defaults', () => {
  // 테스트 코드: DSH-027
  it('조건 없는 주소는 두 탭 모두 올해이고 다른 조건이 없는 Status 탭이다', () => {
    // when: 빈 주소를 읽는다
    const filters = filtersFromParams(params(''), 2026)

    // then: Status 탭, 두 탭 모두 올해·분기 없음이다
    expect(filters).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })

  // 테스트 코드: DSH-027
  it('호출자가 준 대체 연도(앱 시계의 올해)를 두 탭에 쓴다', () => {
    // when: 대체 연도 2031로 빈 주소를 읽는다
    const filters = filtersFromParams(params(''), 2031)

    // then: 두 탭의 연도가 2031이다
    expect(filters.status.year).toBe(2031)
    expect(filters.forecast.year).toBe(2031)
  })

  // 테스트 코드: DSH-026
  it('URL에서 탭을 읽는다', () => {
    // when: tab=forecast를 읽는다
    const filters = filtersFromParams(params('tab=forecast'), 2026)

    // then: Forecast 탭이다
    expect(filters.tab).toBe('forecast')
  })
})

describe('filtersFromParams reads both tabs apart', () => {
  // 테스트 코드: DSH-028
  it('탭마다 자기 접두사 키에서 읽는다', () => {
    // when: 두 탭의 접두사 키가 있는 주소를 읽는다
    const filters = filtersFromParams(params('tab=forecast&status.year=2025&status.quarter=1%2C3&forecast.year=2026&forecast.owner=7'), 2026)

    // then: 각 탭이 자기 값을 가진다
    expect(filters).toEqual({
      tab: 'forecast',
      status: { year: 2025, quarters: [1, 3] },
      forecast: { year: 2026, quarters: [], ownerId: 7 },
    })
  })

  // 테스트 코드: DSH-028
  it('탭마다 담당자·Vendor·분기를 따로 읽는다', () => {
    // when: 두 탭에 서로 다른 값이 있는 주소를 읽는다
    const filters = filtersFromParams(
      params('tab=status&status.year=2025&status.quarter=2&status.owner=3&status.vendor=4&forecast.year=2027&forecast.quarter=4&forecast.owner=8&forecast.vendor=9'),
      2026,
    )

    // then: 값이 섞이지 않는다
    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 3, vendor: 4 })
    expect(filters.forecast).toEqual({ year: 2027, quarters: [4], ownerId: 8, vendor: 9 })
  })

  // 테스트 코드: DSH-035
  it('사용자가 누른 넷 다를 조건 상태에 그대로 둔다', () => {
    // when: 분기 1~4가 적힌 주소를 읽는다
    const quarters = filtersFromParams(params('status.quarter=1%2C2%2C3%2C4'), 2026).status.quarters

    // then: 넷 다 그대로다
    expect(quarters).toEqual([1, 2, 3, 4])
  })

  // 테스트 코드: DSH-034
  it('분기를 오름차순으로 정리하고 중복을 버린다', () => {
    // when: 3,1,1이 적힌 주소를 읽는다
    const quarters = filtersFromParams(params('forecast.quarter=3%2C1%2C1'), 2026).forecast.quarters

    // then: [1, 3]이다
    expect(quarters).toEqual([1, 3])
  })

  // 테스트 코드: DSH-028
  it('다른 탭의 키에서 탭 조건을 읽지 않는다', () => {
    // when: Status 담당자와 Forecast Vendor만 있는 주소를 읽는다
    const filters = filtersFromParams(params('status.owner=7&forecast.vendor=3'), 2026)

    // then: 각자 자기 키의 값만 가진다
    expect(filters.status).toEqual({ ...DEFAULTS, ownerId: 7 })
    expect(filters.forecast).toEqual({ ...DEFAULTS, vendor: 3 })
  })
})

describe('filtersFromParams ignores broken values', () => {
  // 테스트 코드: DSH-026
  it.each(['', 'Forecast', 'FORECAST', 'status ', 'reports', '1'])('모르는 tab 값 %j은 Status 탭으로 읽는다', (raw) => {
    // when: 모르는 tab 값을 읽는다
    const tab = filtersFromParams(params(`tab=${encodeURIComponent(raw)}`), 2026).tab

    // then: Status 탭이다
    expect(tab).toBe('status')
  })

  // 테스트 코드: DSH-031
  it.each(['abc', '', '26', '20266', '-2026', '2026.5', '0'])('틀린 연도 %j은 올해로 대체한다', (raw) => {
    // when: 틀린 연도가 적힌 주소를 읽는다
    const filters = filtersFromParams(params(`status.year=${encodeURIComponent(raw)}&forecast.year=${encodeURIComponent(raw)}`), 2026)

    // then: 두 탭 모두 올해다
    expect(filters.status.year).toBe(2026)
    expect(filters.forecast.year).toBe(2026)
  })

  // 테스트 코드: DSH-031
  it.each([
    ['5', []],
    ['x', []],
    ['0', []],
    ['1,5', [1]],
    ['x,2', [2]],
    ['', []],
  ])('%j에서 올바른 분기만 남긴다', (raw, expected) => {
    // when: 분기 값을 읽는다
    const quarters = filtersFromParams(params(`status.quarter=${encodeURIComponent(raw)}`), 2026).status.quarters

    // then: 올바른 항목만 남는다
    expect(quarters).toEqual(expected)
  })

  // 테스트 코드: DSH-031
  it.each(['0', '-1', '1.5', '1e3', '01', '+3', 'abc', '', '9007199254740992', 'u-kim', '10000000-0000-4000-8000-000000000003'])(
    '틀린 담당자·Vendor 값 %j은 무시한다',
    (raw) => {
      // when: 틀린 id가 적힌 주소를 읽는다
      const encoded = encodeURIComponent(raw)
      const filters = filtersFromParams(params(`status.owner=${encoded}&status.vendor=${encoded}&forecast.owner=${encoded}&forecast.vendor=${encoded}`), 2026)

      // then: 담당자·Vendor가 비어 있다
      expect(filters.status.ownerId).toBeUndefined()
      expect(filters.status.vendor).toBeUndefined()
      expect(filters.forecast.ownerId).toBeUndefined()
      expect(filters.forecast.vendor).toBeUndefined()
    },
  )

  // 테스트 코드: DSH-031
  it('가장 큰 안전 정수도 id로 받아들인다', () => {
    // when: 2^53-1이 적힌 주소를 읽는다
    const filters = filtersFromParams(params('status.owner=9007199254740991&forecast.vendor=9007199254740991'), 2026)

    // then: 그 값이 id다
    expect(filters.status.ownerId).toBe(9007199254740991)
    expect(filters.forecast.vendor).toBe(9007199254740991)
  })

  // 테스트 코드: DSH-030
  it('Forecast 화면의 월·기준 시점·선택 키는 읽지 않는다', () => {
    // when: month·snap·sel이 섞인 주소를 읽는다
    const filters = filtersFromParams(params('status.year=2026&month=3&snap=2026-09&sel=5'), 2026)

    // then: 기본값 그대로다
    expect(filters).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })
})

describe('paramsFromFilters', () => {
  // 테스트 코드: DSH-029
  it('기본값이어도 tab과 두 연도를 항상 쓴다', () => {
    // given: 기본 조건
    const filters: DashboardFilters = { tab: 'status', status: DEFAULTS, forecast: DEFAULTS }

    // when: 주소 쿼리로 바꾼다
    const text = paramsFromFilters(filters).toString()

    // then: tab과 두 연도다
    expect(text).toBe('tab=status&status.year=2026&forecast.year=2026')
  })

  // 테스트 코드: DSH-029
  it('두 탭의 조건을 고정 순서의 10진 글자로 쓴다', () => {
    // when: 두 탭에 모든 조건이 있는 상태를 쓴다
    const next = paramsFromFilters({
      tab: 'forecast',
      status: { year: 2025, quarters: [1, 3], ownerId: 2, vendor: 12 },
      forecast: { year: 2026, quarters: [4], ownerId: 5, vendor: 9 },
    })

    // then: tab, status.*, forecast.* 순서다
    expect(next.toString()).toBe(
      'tab=forecast&status.year=2025&status.quarter=1%2C3&status.owner=2&status.vendor=12&forecast.year=2026&forecast.quarter=4&forecast.owner=5&forecast.vendor=9',
    )
  })

  // 테스트 코드: DSH-029
  it('값이 없는 조건은 쓰지 않는다', () => {
    // when: 담당자만 있는 상태를 쓴다
    const next = paramsFromFilters({ tab: 'status', status: { year: 2026, quarters: [], ownerId: 2 }, forecast: DEFAULTS })

    // then: 빈 키가 없다
    expect(next.has('status.quarter')).toBe(false)
    expect(next.has('status.vendor')).toBe(false)
    expect(next.has('forecast.owner')).toBe(false)
    expect(next.toString()).toBe('tab=status&status.year=2026&status.owner=2&forecast.year=2026')
  })

  // 테스트 코드: DSH-035
  it('사용자가 넷 다 눌렀으면 넷 다 쓴다', () => {
    // when: 분기 1~4 상태를 쓴다
    const next = paramsFromFilters({ tab: 'status', status: { year: 2026, quarters: [1, 2, 3, 4] }, forecast: DEFAULTS })

    // then: 1,2,3,4다
    expect(next.get('status.quarter')).toBe('1,2,3,4')
    expect(next.toString()).toContain('status.quarter=1%2C2%2C3%2C4')
  })

  // 테스트 코드: DSH-029
  it('예전 공용 키와 sq는 쓰지 않는다', () => {
    // when: 모든 조건이 있는 상태를 쓴다
    const next = paramsFromFilters({ tab: 'forecast', status: { year: 2025, quarters: [2], ownerId: 7, vendor: 3 }, forecast: { year: 2025, quarters: [], ownerId: 7, vendor: 3 } })

    // then: 접두사 없는 키가 없다
    for (const key of ['year', 'quarter', 'owner', 'vendor', 'sq']) expect(next.has(key)).toBe(false)
  })

  // 테스트 코드: DSH-029
  it('쓴 것을 filtersFromParams로 다시 읽으면 같다', () => {
    // given: 두 탭에 조건이 있는 상태
    const filters: DashboardFilters = {
      tab: 'forecast',
      status: { year: 2027, quarters: [1, 2, 3, 4], ownerId: 5, vendor: 9 },
      forecast: { year: 2025, quarters: [2, 4], vendor: 1 },
    }

    // when: 쓰고 다시 읽는다
    const again = filtersFromParams(paramsFromFilters(filters), 2026)

    // then: 같은 상태다
    expect(again).toEqual(filters)
  })
})

describe('old shared addresses still open', () => {
  const OLD = 'tab=forecast&year=2025&quarter=2&owner=7&vendor=3&sq=3'

  // 테스트 코드: DSH-030
  it('예전 연도·담당자·Vendor는 두 탭에, 예전 분기는 Status 탭에만 읽는다', () => {
    // when: 예전 공용 키 주소를 읽는다
    const filters = filtersFromParams(params(OLD), 2026)

    // then: 분기는 Status에만 있다
    expect(filters.tab).toBe('forecast')
    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 7, vendor: 3 })
    expect(filters.forecast).toEqual({ year: 2025, quarters: [], ownerId: 7, vendor: 3 })
  })

  // 테스트 코드: DSH-030
  it('담당자 7은 두 탭에, 분기는 Status 탭에만 읽는다', () => {
    // when: 예전 공용 키(sq 포함) 주소를 읽는다
    const filters = filtersFromParams(params('tab=forecast&year=2025&quarter=2&owner=7&sq=3'), 2026)

    // then: Forecast에는 분기가 없고 Status에는 Q2가 있다
    expect(filters.forecast).toEqual({ year: 2025, quarters: [], ownerId: 7 })
    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 7 })
  })

  // 테스트 코드: DSH-030
  it('sq는 무시한다', () => {
    // when: sq만 있는 주소를 읽는다
    const filters = filtersFromParams(params('sq=3'), 2026)

    // then: 기본값이다
    expect(filters).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })

  // 테스트 코드: DSH-030
  it('예전 주소를 다시 쓰면 접두사 키만 쓴다', () => {
    // when: 예전 주소를 읽고 다시 쓴다
    const next = paramsFromFilters(filtersFromParams(params(OLD), 2026))

    // then: 접두사 없는 키가 없고 Status 분기·Forecast 담당자가 접두사 키로 있다
    for (const key of ['year', 'quarter', 'owner', 'vendor', 'sq']) expect(next.has(key)).toBe(false)
    expect(next.get('status.quarter')).toBe('2')
    expect(next.get('forecast.owner')).toBe('7')
    expect(next.has('forecast.quarter')).toBe(false)
  })

  // 테스트 코드: DSH-030
  it('같은 탭의 접두사 키가 예전 키보다 우선한다', () => {
    // when: 예전 키와 Forecast 접두사 키가 함께 있는 주소를 읽는다
    const filters = filtersFromParams(params('year=2025&owner=7&forecast.year=2027&forecast.owner=8'), 2026)

    // then: Forecast는 접두사 값, Status는 예전 값이다
    expect(filters.forecast).toMatchObject({ year: 2027, ownerId: 8 })
    expect(filters.status).toMatchObject({ year: 2025, ownerId: 7 })
  })

  // 테스트 코드: DSH-030
  it('접두사 값이 틀려도 예전 키로 대체하지 않는다', () => {
    // when: 틀린 Status 접두사 값과 예전 키가 있는 주소를 읽는다
    const filters = filtersFromParams(params('year=2025&owner=7&status.year=abc&status.owner=0'), 2026)

    // then: Status는 기본값·전체이고 Forecast는 예전 값을 쓴다
    expect(filters.status.year).toBe(2026)
    expect(filters.status.ownerId).toBeUndefined()
    expect(filters.forecast).toMatchObject({ year: 2025, ownerId: 7 })
  })

  // 테스트 코드: DSH-030
  it('Status 탭의 접두사 분기가 예전 분기보다 우선한다', () => {
    // when: 예전 분기 2와 접두사 분기 4가 함께 있는 주소를 읽는다
    const quarters = filtersFromParams(params('quarter=2&status.quarter=4'), 2026).status.quarters

    // then: [4]다
    expect(quarters).toEqual([4])
  })
})

describe('activeFilters and patchActive', () => {
  const FILTERS: DashboardFilters = {
    tab: 'status',
    status: { year: 2025, quarters: [2], ownerId: 7 },
    forecast: { year: 2026, quarters: [], vendor: 3 },
  }

  // 테스트 코드: DSH-028
  it('활성 탭의 조건을 돌려준다', () => {
    // when·then: Status가 활성일 때와 Forecast가 활성일 때 각 탭 조건이다
    expect(activeFilters(FILTERS)).toEqual(FILTERS.status)
    expect(activeFilters({ ...FILTERS, tab: 'forecast' })).toEqual(FILTERS.forecast)
  })

  // 테스트 코드: DSH-028
  it('활성 탭만 고치고 다른 탭은 그대로 둔다', () => {
    // when: Status 탭의 분기와 담당자를 고친다
    const next = patchActive(FILTERS, { quarters: [1, 3], ownerId: undefined })

    // then: Status만 바뀌고 Forecast는 그대로다
    expect(next.status).toEqual({ year: 2025, quarters: [1, 3] })
    expect(next.forecast).toEqual(FILTERS.forecast)
    expect(next.tab).toBe('status')
  })

  // 테스트 코드: DSH-028
  it('Forecast 탭이 활성이면 Forecast 탭을 고친다', () => {
    // when: Forecast 활성 상태에서 연도를 고친다
    const next = patchActive({ ...FILTERS, tab: 'forecast' }, { year: 2024 })

    // then: Forecast만 바뀐다
    expect(next.forecast).toEqual({ year: 2024, quarters: [], vendor: 3 })
    expect(next.status).toEqual(FILTERS.status)
  })

  // 테스트 코드: DSH-028
  it('받은 조건 객체를 바꾸지 않는다', () => {
    // when: 조건을 고친다
    patchActive(FILTERS, { year: 2020 })

    // then: 원본은 그대로다
    expect(FILTERS.status.year).toBe(2025)
  })
})

describe('queryOf', () => {
  // 테스트 코드: DSH-027
  it('다른 조건을 고르지 않으면 연도만 보낸다', () => {
    // when: 연도만 있는 조건을 조회 조건으로 바꾼다
    const query = queryOf({ year: 2026, quarters: [] })

    // then: 연도뿐이다
    expect(query).toEqual({ year: 2026 })
  })

  // 테스트 코드: DSH-034
  it('분기·담당자·Vendor를 게이트웨이 조회 조건으로 바꾼다', () => {
    // when: 모든 조건을 바꾼다
    const query = queryOf({ year: 2026, quarters: [1, 3], ownerId: 2, vendor: 12 })

    // then: 게이트웨이 이름(ownerId·vendorId)이다
    expect(query).toEqual({ year: 2026, quarters: [1, 3], ownerId: 2, vendorId: 12 })
  })

  // 테스트 코드: DSH-035
  it('넷 다는 분기를 보내지 않는다(없음과 같다)', () => {
    // when: 분기 1~4를 바꾼다
    const query = queryOf({ year: 2026, quarters: [1, 2, 3, 4] })

    // then: 분기 키가 없다
    expect(query).toEqual({ year: 2026 })
    expect(query).not.toHaveProperty('quarters')
  })

  // 테스트 코드: DSH-034
  it('id는 숫자로 둔다', () => {
    // when: 담당자·Vendor가 있는 조건을 바꾼다
    const query = queryOf({ year: 2026, quarters: [], ownerId: 2, vendor: 12 })

    // then: id가 number다
    expect(typeof query.ownerId).toBe('number')
    expect(typeof query.vendorId).toBe('number')
  })

  // 테스트 코드: DSH-034
  it('예전 단일 quarter 키는 보내지 않는다', () => {
    // when: 분기 [2]를 바꾼다
    const query = queryOf({ year: 2026, quarters: [2] })

    // then: quarter 키가 없다
    expect(query).not.toHaveProperty('quarter')
  })
})
