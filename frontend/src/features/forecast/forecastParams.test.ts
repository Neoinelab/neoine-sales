import { describe, expect, it } from 'vitest'
import { filtersFromParams, paramsFromFilters, periodLabel, queryOf } from './forecastParams'

const params = (query: string) => new URLSearchParams(query)

describe('filtersFromParams ids', () => {
  // 테스트 코드: FC-062
  it('정수 vendor·owner·sel id를 읽는다', () => {
    // when: id가 담긴 쿼리를 필터로 읽는다
    const filters = filtersFromParams(params('year=2026&owner=2&vendor=12&sel=5'), 2026)

    // then: 연도와 세 id가 숫자로 읽힌다
    expect(filters).toMatchObject({ year: 2026, ownerId: 2, vendor: 12, selectedId: 5 })
  })

  // 테스트 코드: FC-062
  it('UUID나 이름 값은 vendor로 읽지 않는다', () => {
    // when·then: 이름·UUID 값의 vendor는 읽히지 않는다
    expect(filtersFromParams(params('vendor=Okta'), 2026).vendor).toBeUndefined()
    expect(filtersFromParams(params('vendor=10000000-0000-4000-8000-000000000003'), 2026).vendor).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it('예전 사용자 키(u-kim)는 owner·sel로 읽지 않는다', () => {
    // when: 예전 사용자 키가 담긴 쿼리를 읽는다
    const filters = filtersFromParams(params('owner=u-kim&sel=u-park'), 2026)

    // then: owner와 sel이 비어 있다
    expect(filters.ownerId).toBeUndefined()
    expect(filters.selectedId).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it.each(['0', '-1', '1.5', '1e3', '01', '+3', '9007199254740992'])('범위 밖이거나 정수가 아닌 id %j는 읽지 않는다', (raw) => {
    // given: 잘못된 id 문자열
    const encoded = encodeURIComponent(raw)
    // when: owner·vendor·sel로 읽는다
    const filters = filtersFromParams(params(`owner=${encoded}&vendor=${encoded}&sel=${encoded}`), 2026)

    // then: 세 id 모두 비어 있다
    expect(filters.ownerId).toBeUndefined()
    expect(filters.vendor).toBeUndefined()
    expect(filters.selectedId).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it('가장 큰 안전 정수도 id로 받는다', () => {
    // when·then: 2^53−1을 vendor로 읽는다
    expect(filtersFromParams(params('vendor=9007199254740991'), 2026).vendor).toBe(9007199254740991)
  })
})

describe('paramsFromFilters and queryOf ids', () => {
  // 테스트 코드: FC-062
  it('id를 십진수 글자로 URL에 쓴다', () => {
    // when: 필터를 URL 쿼리로 쓴다
    const next = paramsFromFilters({ year: 2026, quarter: 4, ownerId: 2, vendor: 12, selectedId: 5 })

    // then: year·quarter·owner·vendor·sel이 십진수로 들어간다
    expect(next.toString()).toBe('year=2026&quarter=4&owner=2&vendor=12&sel=5')
  })

  // 테스트 코드: FC-062
  it('요약 조회 조건에는 id를 숫자로 담고 sel은 뺀다', () => {
    // when: 필터를 요약 조회 조건으로 바꾼다
    const query = queryOf({ year: 2026, ownerId: 2, vendor: 12, selectedId: 5 })

    // then: vendorId·ownerId가 숫자로 담기고 선택 id는 없다
    expect(query).toEqual({ year: 2026, vendorId: 12, ownerId: 2 })
  })
})

describe('month', () => {
  // 테스트 코드: FC-062
  it('URL의 월을 읽는다', () => {
    // when·then: month=3을 읽으면 3월이다
    expect(filtersFromParams(params('year=2026&month=3'), 2026)).toMatchObject({ year: 2026, month: 3 })
  })

  // 테스트 코드: FC-062
  it.each(['0', '13', '-1', '1.5', 'abc', '03', ''])('잘못된 월 %j는 읽지 않는다', (raw) => {
    // when·then: 월 값이 없다
    expect(filtersFromParams(params(`year=2026&month=${raw}`), 2026).month).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it.each(['1', '12'])('경계 월 %s는 받는다', (raw) => {
    // when·then: 경계 월이 숫자로 읽힌다
    expect(filtersFromParams(params(`year=2026&month=${raw}`), 2026).month).toBe(Number(raw))
  })

  // 테스트 코드: FC-062
  it('분기와 월이 함께 있으면 분기만 쓴다', () => {
    // when: quarter=4&month=11을 읽는다
    const filters = filtersFromParams(params('year=2026&quarter=4&month=11'), 2026)

    // then: 분기 4만 남고 월은 없다
    expect(filters.quarter).toBe(4)
    expect(filters.month).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it('월을 URL에 쓰되 분기와 함께 쓰지 않는다', () => {
    // when·then: 월만 있으면 month가 쓰이고 분기와 월이 함께면 month를 쓰지 않는다
    expect(paramsFromFilters({ year: 2026, month: 3 }).toString()).toBe('year=2026&month=3')
    expect(paramsFromFilters({ year: 2026, quarter: 4, month: 3 }).has('month')).toBe(false)
  })

  // 테스트 코드: FC-062
  it('월은 요약 조회 조건에 담고 분기는 뺀다', () => {
    // when·then: 월 필터의 조회 조건에 month가 담긴다
    expect(queryOf({ year: 2026, month: 3, ownerId: 2 })).toEqual({ year: 2026, month: 3, ownerId: 2 })
  })

  it('기간 이름은 월·분기·연도 전체로 붙인다', () => {
    // when·then: 월은 "2026 3월", 분기는 "2026 Q4", 연도만이면 "2026 전체"다
    expect(periodLabel({ year: 2026, month: 3 })).toBe('2026 3월')
    expect(periodLabel({ year: 2026, quarter: 4 })).toBe('2026 Q4')
    expect(periodLabel({ year: 2026 })).toBe('2026 전체')
  })
})

describe('기준 시점(snap) URL 파라미터', () => {
  // 테스트 코드: FC-062
  it('YYYY-MM 기준 월을 읽는다', () => {
    // when·then: snap=2026-09를 읽으면 그 기준 월이다
    expect(filtersFromParams(params('year=2026&snap=2026-09'), 2026).snap).toBe('2026-09')
  })

  // 테스트 코드: FC-062
  it('snap이 없으면 스냅숏을 고르지 않은 것이다', () => {
    // when·then: snap 없이 읽으면 비어 있다
    expect(filtersFromParams(params('year=2026'), 2026).snap).toBeUndefined()
  })

  // 테스트 코드: FC-062
  it.each(['', '2026-9', '2026-13', '2026-00', '202609', '2026/09', ' 2026-09', 'abc', '2026-09-01'])(
    '형식이 틀린 기준 월 %j는 무시한다',
    (raw) => {
      // when·then: 형식이 틀린 snap은 읽히지 않는다
      expect(filtersFromParams(params(`year=2026&snap=${encodeURIComponent(raw)}`), 2026).snap).toBeUndefined()
    },
  )

  // 테스트 코드: FC-062
  it('기준 월을 다른 필터와 함께 URL에 쓴다', () => {
    // when: snap이 있는 필터를 URL로 쓴다
    const written = paramsFromFilters({ year: 2026, quarter: 3, ownerId: 2, snap: '2026-09' })

    // then: year·quarter·owner·snap이 들어간다
    expect(Object.fromEntries(written)).toEqual({ year: '2026', quarter: '3', owner: '2', snap: '2026-09' })
  })

  // 테스트 코드: FC-062
  it('고르지 않았으면 snap을 URL에 쓰지 않는다', () => {
    // when·then: snap이 없다
    expect(paramsFromFilters({ year: 2026 }).has('snap')).toBe(false)
  })

  // 테스트 코드: FC-062
  it('필터는 URL로 썼다 읽어도 같다', () => {
    // given: 월·담당자·선택·기준 월이 있는 필터
    const filters = { year: 2026, month: 8, ownerId: 3, selectedId: 3, snap: '2026-09' }

    // when·then: URL로 쓰고 다시 읽어도 같은 필터다
    expect(filtersFromParams(paramsFromFilters(filters), 2000)).toEqual({ ...filters, quarter: undefined, vendor: undefined })
  })

  // 테스트 코드: FC-062
  it('기준 월은 요약 조회 조건에 넣지 않는다', () => {
    // when·then: snap이 있어도 조회 조건에는 연도·분기만 있다
    expect(queryOf({ year: 2026, quarter: 3, snap: '2026-09' })).toEqual({ year: 2026, quarter: 3 })
  })
})
