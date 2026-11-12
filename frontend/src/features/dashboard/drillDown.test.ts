import { describe, expect, it } from 'vitest'
import { listQueryFromParams } from '../deals/list/listQuery'
import { forecastSetsOf } from '../../shared/model/forecastKeys'
import type { ForecastColumn } from '../../shared/model/types'
import {
  closingMonthPath,
  closingQuarterPath,
  forecastTilePath,
  openTotalPath,
  overduePath,
  quarterCellPath,
  quarterTotalPath,
  stalePath,
  statusPath,
  statusTotalPath,
} from './drillDown'

/**
 * Drill-down URL(DSH-R25 표). 키 순서는 year, quarter, month, owner, vendor, status, forecast, overdue, stale로 고정(outcome은 없음)한다.
 * Lost 제외·Open 숫자를 누르면 응답 `forecast.columns`로 만든 Forecast key 집합(알파벳순, 콤마 → %2C)이 `forecast`에 실린다.
 * scope = 대시보드 필터(연도·Quarter·담당자·Vendor). Vendor는 목록에 있는 id만 호출자가 넘긴다.
 */

const FULL = { year: 2026, quarters: [4], ownerId: 7, vendor: 3 } as const
const YEAR_ONLY = { year: 2026, quarters: [] } as const
const OWNER_ONLY = { year: 2026, quarters: [], ownerId: 7 } as const
const VENDOR_ONLY = { year: 2026, quarters: [], vendor: 3 } as const
// 활성 탭에서 고른 분기(오름차순). 넷 다·없음은 호출자가 []로 정규화해 넘긴다
const SEVERAL = { year: 2026, quarters: [1, 3], ownerId: 7, vendor: 3 } as const

const column = (key: string, outcome: 'open' | 'won', order: number): ForecastColumn => ({ key, name: key, outcome, order })
// 응답 columns(Lost 제외): Pipeline·Best·Most Likely·Commit과 admin이 추가한 Open 코드 verbal, Won
const COLUMNS: ForecastColumn[] = [
  column('pipeline', 'open', 1),
  column('best', 'open', 2),
  column('verbal', 'open', 3),
  column('most_likely', 'open', 4),
  column('commit', 'open', 5),
  column('won', 'won', 6),
]
const SETS = forecastSetsOf(COLUMNS)
const NO_OPEN = forecastSetsOf([column('won', 'won', 1)])
const NOTHING = forecastSetsOf([])
// URLSearchParams는 콤마를 %2C로 쓴다
const OPEN = 'best%2Ccommit%2Cmost_likely%2Cpipeline%2Cverbal'
const NOT_LOST = `${OPEN}%2Cwon`

const queryOf = (path: string) => listQueryFromParams(new URLSearchParams(path.split('?')[1] ?? ''))
const PAGING = { offset: 0, limit: 20 }

describe('Forecast 타일 (key 하나)', () => {
  // 테스트 코드: DSH-048
  it('Forecast 코드 하나의 Deal을 필터 전체와 함께 연다', () => {
    // when: 전체 필터로 Commit 타일 주소를 만든다
    const path = forecastTilePath(FULL, 'commit')

    // then: 연도·분기·담당자·Vendor와 forecast=commit이다
    expect(path).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=commit')
  })

  // 테스트 코드: DSH-048
  it('고르지 않은 분기·담당자·Vendor는 뺀다', () => {
    // when: 연도만, 담당자만, Vendor만 있는 필터로 주소를 만든다
    const year = forecastTilePath(YEAR_ONLY, 'pipeline')
    const owner = forecastTilePath(OWNER_ONLY, 'best')
    const vendor = forecastTilePath(VENDOR_ONLY, 'won')

    // then: 고른 조건만 주소에 있다
    expect(year).toBe('/deals?year=2026&forecast=pipeline')
    expect(owner).toBe('/deals?year=2026&owner=7&forecast=best')
    expect(vendor).toBe('/deals?year=2026&vendor=3&forecast=won')
  })
})

describe('Open 합계 타일 (Open 집합)', () => {
  // 테스트 코드: DSH-048
  it('필터에 모든 Open Forecast 코드를 더해 연다', () => {
    // when: Open 합계 주소를 만든다
    const full = openTotalPath(FULL, SETS)
    const year = openTotalPath(YEAR_ONLY, SETS)

    // then: 알파벳순 Open 집합이 forecast에 실린다
    expect(full).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${OPEN}`)
    expect(year).toBe(`/deals?year=2026&forecast=${OPEN}`)
  })

  // 테스트 코드: DSH-049
  it('Open 코드가 없으면 링크가 없다', () => {
    // when: Open 코드가 없는 집합으로 주소를 만든다
    const noOpen = openTotalPath(FULL, NO_OPEN)
    const nothing = openTotalPath(FULL, NOTHING)

    // then: 주소를 만들지 않는다
    expect(noOpen).toBeNull()
    expect(nothing).toBeNull()
  })
})

describe('Status 막대와 표 (Lost 제외 집합)', () => {
  // 테스트 코드: DSH-048
  it('Status 하나를 Lost 제외 Forecast와 함께 연다', () => {
    // when: POC완료 주소를 만든다
    const path = statusPath(FULL, 'poc_completed', SETS)

    // then: status와 Lost 제외 집합이 실린다
    expect(path).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&status=poc_completed&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-048
  it('문서의 예: 2026년·담당자 7·Vendor 없음·POC완료', () => {
    // when: 담당자만 있는 필터로 POC완료 주소를 만든다
    const path = statusPath(OWNER_ONLY, 'poc_completed', SETS)

    // then: 문서 표의 주소와 같다
    expect(path).toBe(`/deals?year=2026&owner=7&status=poc_completed&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-048
  it('합계 행은 필터의 Lost 제외 Deal 전체를 연다', () => {
    // when: 합계 주소를 만든다
    const full = statusTotalPath(FULL, SETS)
    const year = statusTotalPath(YEAR_ONLY, SETS)

    // then: Lost 제외 집합만 forecast에 실린다
    expect(full).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${NOT_LOST}`)
    expect(year).toBe(`/deals?year=2026&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-049
  it('Lost 제외 집합이 비면 링크가 없다', () => {
    // when: 빈 집합으로 주소를 만든다
    const row = statusPath(FULL, 'poc_completed', NOTHING)
    const total = statusTotalPath(FULL, NOTHING)

    // then: 주소를 만들지 않는다
    expect(row).toBeNull()
    expect(total).toBeNull()
  })

  // 테스트 코드: DSH-049
  it('Won만 있어도 Won은 Lost가 아니므로 링크가 있다', () => {
    // when: Won만 있는 집합으로 합계 주소를 만든다
    const path = statusTotalPath(YEAR_ONLY, NO_OPEN)

    // then: forecast=won이다
    expect(path).toBe('/deals?year=2026&forecast=won')
  })
})

describe('주의 필요 타일', () => {
  // 테스트 코드: DSH-048
  it('기한초과 타일은 기간을 무시하고 담당자·Vendor만 싣는다(Forecast 없음)', () => {
    // when: 기한초과 주소를 만든다
    const full = overduePath(FULL)
    const year = overduePath(YEAR_ONLY)

    // then: 담당자·Vendor와 overdue=1뿐이다
    expect(full).toBe('/deals?owner=7&vendor=3&overdue=1')
    expect(year).toBe('/deals?overdue=1')
  })

  // 테스트 코드: DSH-048
  it('미업데이트 타일은 기간을 무시하고 담당자·Vendor만 싣는다(Forecast 없음)', () => {
    // when: 미업데이트 주소를 만든다
    const full = stalePath(FULL)
    const vendor = stalePath(VENDOR_ONLY)

    // then: 담당자·Vendor와 stale=1뿐이다
    expect(full).toBe('/deals?owner=7&vendor=3&stale=1')
    expect(vendor).toBe('/deals?vendor=3&stale=1')
  })

  // 테스트 코드: DSH-048
  it('이번 분기 타일은 서버의 연·분기와 Open Forecast를 쓴다', () => {
    // when: 서버 연·분기로 이번 분기 주소를 만든다
    const same = closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS)
    const other = closingQuarterPath({ year: 2020, quarters: [1] }, { year: 2027, quarter: 1 }, SETS)

    // then: 고른 기간이 아니라 서버 연·분기다
    expect(same).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${OPEN}`)
    expect(other).toBe(`/deals?year=2027&quarter=1&forecast=${OPEN}`)
  })

  // 테스트 코드: DSH-048
  it('이번 달 타일은 서버의 연·월과 Open Forecast를 쓴다', () => {
    // when: 서버 연·월로 이번 달 주소를 만든다
    const same = closingMonthPath(FULL, { year: 2026, month: 10 }, SETS)
    const other = closingMonthPath({ year: 2020, quarters: [1] }, { year: 2027, month: 1 }, SETS)

    // then: 고른 기간이 아니라 서버 연·월이다
    expect(same).toBe(`/deals?year=2026&month=10&owner=7&vendor=3&forecast=${OPEN}`)
    expect(other).toBe(`/deals?year=2027&month=1&forecast=${OPEN}`)
  })

  // 테스트 코드: DSH-049
  it('Open 코드가 없으면 이번 분기·이번 달 링크가 없다', () => {
    // when: Open 코드가 없는 집합으로 주소를 만든다
    const quarter = closingQuarterPath(FULL, { year: 2026, quarter: 4 }, NO_OPEN)
    const month = closingMonthPath(FULL, { year: 2026, month: 10 }, NO_OPEN)

    // then: 주소를 만들지 않는다
    expect(quarter).toBeNull()
    expect(month).toBeNull()
  })
})

describe('분기 차트와 표 (Forecast 탭)', () => {
  // 테스트 코드: DSH-048
  it('고른 분기와 무관하게 분기 하나의 Forecast 코드 하나를 연다', () => {
    // when: 분기 칸 주소를 만든다
    const commit = quarterCellPath(FULL, 2, 'commit')
    const won = quarterCellPath(YEAR_ONLY, 3, 'won')

    // then: 그 분기 하나와 key다
    expect(commit).toBe('/deals?year=2026&quarter=2&owner=7&vendor=3&forecast=commit')
    expect(won).toBe('/deals?year=2026&quarter=3&forecast=won')
  })

  // 테스트 코드: DSH-048
  it('분기 합계는 그 분기의 Lost 제외 Deal을 연다', () => {
    // when: 분기 합계 주소를 만든다
    const full = quarterTotalPath(FULL, 1, SETS)
    const owner = quarterTotalPath(OWNER_ONLY, 4, SETS)

    // then: 그 분기 하나와 Lost 제외 집합이다
    expect(full).toBe(`/deals?year=2026&quarter=1&owner=7&vendor=3&forecast=${NOT_LOST}`)
    expect(owner).toBe(`/deals?year=2026&quarter=4&owner=7&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-049
  it('Lost 제외 집합이 비면 분기 합계 링크가 없다', () => {
    // when: 빈 집합으로 분기 합계 주소를 만든다
    const path = quarterTotalPath(FULL, 1, NOTHING)

    // then: 주소를 만들지 않는다
    expect(path).toBeNull()
  })
})

describe('왕복: Deals 목록이 같은 조건을 다시 읽는다', () => {
  // 테스트 코드: DSH-048
  it('Forecast 타일', () => {
    // when: 타일 주소를 목록 조회 조건으로 읽는다
    const query = queryOf(forecastTilePath(FULL, 'commit'))

    // then: 같은 조건이다
    expect(query).toEqual({ ...PAGING, year: 2026, quarters: [4], ownerId: 7, vendorId: 3, forecastKeys: ['commit'] })
  })

  // 테스트 코드: DSH-048
  it('Open 합계', () => {
    // when: 주소를 목록 조회 조건으로 읽는다
    const query = queryOf(openTotalPath(OWNER_ONLY, SETS) ?? '')

    // then: Open 집합이다
    expect(query).toEqual({ ...PAGING, year: 2026, ownerId: 7, forecastKeys: SETS.open })
  })

  // 테스트 코드: DSH-048
  it('Status 막대', () => {
    // when: 주소를 목록 조회 조건으로 읽는다
    const query = queryOf(statusPath(FULL, 'poc_completed', SETS) ?? '')

    // then: Status와 Lost 제외 집합이다
    expect(query).toEqual({
      ...PAGING,
      year: 2026,
      quarters: [4],
      ownerId: 7,
      vendorId: 3,
      statusKey: 'poc_completed',
      forecastKeys: SETS.notLost,
    })
  })

  // 테스트 코드: DSH-048
  it('Status 합계', () => {
    // when: 주소를 목록 조회 조건으로 읽는다
    const query = queryOf(statusTotalPath(YEAR_ONLY, SETS) ?? '')

    // then: Lost 제외 집합이다
    expect(query).toEqual({ ...PAGING, year: 2026, forecastKeys: SETS.notLost })
  })

  // 테스트 코드: DSH-048
  it('기한초과·미업데이트 타일', () => {
    // when: 두 주소를 목록 조회 조건으로 읽는다
    const overdue = queryOf(overduePath(FULL))
    const stale = queryOf(stalePath(FULL))

    // then: 담당자·Vendor와 각 플래그다
    expect(overdue).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, overdue: true })
    expect(stale).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, stale: true })
  })

  // 테스트 코드: DSH-048
  it('이번 분기·이번 달 타일', () => {
    // when: 두 주소를 목록 조회 조건으로 읽는다
    const quarter = queryOf(closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS) ?? '')
    const month = queryOf(closingMonthPath(OWNER_ONLY, { year: 2026, month: 10 }, SETS) ?? '')

    // then: 서버 연·분기/월과 Open 집합이다
    expect(quarter).toEqual({
      ...PAGING,
      year: 2026,
      quarters: [4],
      ownerId: 7,
      vendorId: 3,
      forecastKeys: SETS.open,
    })
    expect(month).toEqual({
      ...PAGING,
      year: 2026,
      month: 10,
      ownerId: 7,
      forecastKeys: SETS.open,
    })
  })

  // 테스트 코드: DSH-048
  it('분기 칸과 분기 합계', () => {
    // when: 두 주소를 목록 조회 조건으로 읽는다
    const cell = queryOf(quarterCellPath(FULL, 2, 'commit'))
    const total = queryOf(quarterTotalPath(FULL, 3, SETS) ?? '')

    // then: 그 분기 하나의 조건이다
    expect(cell).toEqual({ ...PAGING, year: 2026, quarters: [2], ownerId: 7, vendorId: 3, forecastKeys: ['commit'] })
    expect(total).toEqual({
      ...PAGING,
      year: 2026,
      quarters: [3],
      ownerId: 7,
      vendorId: 3,
      forecastKeys: SETS.notLost,
    })
  })

  // 테스트 코드: DSH-048
  it('정렬·순서·페이지를 싣지 않는다(목록은 기본 정렬 1페이지로 연다)', () => {
    // given: 모든 종류의 주소
    const paths = [
      forecastTilePath(FULL, 'commit'),
      openTotalPath(FULL, SETS),
      statusPath(FULL, 'prospecting', SETS),
      statusTotalPath(FULL, SETS),
      overduePath(FULL),
      stalePath(FULL),
      closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS),
      closingMonthPath(FULL, { year: 2026, month: 10 }, SETS),
      quarterCellPath(FULL, 2, 'commit'),
      quarterTotalPath(FULL, 2, SETS),
    ]

    // when·then: 각 주소의 쿼리 키를 보면 sort·order·page가 없다
    for (const path of paths) {
      expect(path).not.toBeNull()
      const keys = [...new URLSearchParams((path ?? '').split('?')[1] ?? '').keys()]
      expect(keys).not.toContain('sort')
      expect(keys).not.toContain('order')
      expect(keys).not.toContain('page')
      expect((path ?? '').startsWith('/deals?')).toBe(true)
    }
  })
})

describe('outcome은 어느 주소에도 없다', () => {
  // 테스트 코드: DSH-048
  it('outcome을 싣지 않는다', () => {
    // given: 모든 종류의 주소
    const paths = [
      forecastTilePath(FULL, 'commit'),
      openTotalPath(FULL, SETS),
      statusPath(FULL, 'prospecting', SETS),
      statusTotalPath(FULL, SETS),
      overduePath(FULL),
      stalePath(FULL),
      closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS),
      closingMonthPath(FULL, { year: 2026, month: 10 }, SETS),
      quarterCellPath(FULL, 2, 'commit'),
      quarterTotalPath(FULL, 2, SETS),
    ]

    // when·then: 어느 주소에도 outcome이 없고 목록 조회 조건에도 outcome이 없다
    for (const path of paths) {
      expect(path).not.toContain('outcome')
      expect(queryOf(path ?? '')).not.toHaveProperty('forecastOutcome')
    }
  })

  // 테스트 코드: DSH-048
  it('조건 순서가 문서와 같다: forecast는 status 뒤, 플래그 앞이다', () => {
    // when: 주소를 만든다
    const status = statusPath(FULL, 'prospecting', SETS)
    const month = closingMonthPath(FULL, { year: 2026, month: 10 }, SETS)
    const quarter = quarterTotalPath(FULL, 1, SETS)

    // then: 키 순서가 고정이다
    expect(status).toMatch(/\?year=2026&quarter=4&owner=7&vendor=3&status=prospecting&forecast=/)
    expect(month).toMatch(/\?year=2026&month=10&owner=7&vendor=3&forecast=/)
    expect(quarter).toMatch(/\?year=2026&quarter=1&owner=7&vendor=3&forecast=/)
  })
})

describe('여러 분기를 고른 경우', () => {
  const PARAM = 'quarter=1%2C3'

  // 테스트 코드: DSH-052
  it('기간에 묶이는 모든 링크에 고른 분기를 오름차순 콤마 목록 하나로 싣는다', () => {
    // when: Q1·Q3를 고른 필터로 주소를 만든다
    const tile = forecastTilePath(SEVERAL, 'commit')
    const open = openTotalPath(SEVERAL, SETS)
    const status = statusPath(SEVERAL, 'poc_completed', SETS)
    const total = statusTotalPath(SEVERAL, SETS)

    // then: 모두 quarter=1,3을 가진다
    expect(tile).toBe(`/deals?year=2026&${PARAM}&owner=7&vendor=3&forecast=commit`)
    expect(open).toBe(`/deals?year=2026&${PARAM}&owner=7&vendor=3&forecast=${OPEN}`)
    expect(status).toBe(`/deals?year=2026&${PARAM}&owner=7&vendor=3&status=poc_completed&forecast=${NOT_LOST}`)
    expect(total).toBe(`/deals?year=2026&${PARAM}&owner=7&vendor=3&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-035
  it('분기를 넘기지 않으면 quarter 키가 없다(없음·넷 다는 호출자가 정규화한다)', () => {
    // when: 분기 없는 필터로 주소를 만든다
    const tile = forecastTilePath(YEAR_ONLY, 'commit')
    const total = statusTotalPath(YEAR_ONLY, SETS)

    // then: quarter 키가 없다
    expect(tile).not.toContain('quarter')
    expect(total).not.toContain('quarter')
  })

  // 테스트 코드: DSH-052
  it('분기 칸과 분기 합계는 고른 분기를 무시하고 정확히 한 분기를 연다', () => {
    // when: Q1·Q3를 고른 필터로 분기 칸·분기 합계 주소를 만든다
    const cell = quarterCellPath(SEVERAL, 2, 'commit')
    const total = quarterTotalPath(SEVERAL, 4, SETS)

    // then: 누른 분기 하나다
    expect(cell).toBe('/deals?year=2026&quarter=2&owner=7&vendor=3&forecast=commit')
    expect(total).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${NOT_LOST}`)
  })

  // 테스트 코드: DSH-052
  it('이번 분기·이번 달·기한초과·미업데이트 링크는 무엇을 골랐든 같다', () => {
    // when: Q1·Q3를 고른 필터로 네 주소를 만든다
    const quarter = closingQuarterPath(SEVERAL, { year: 2026, quarter: 4 }, SETS)
    const month = closingMonthPath(SEVERAL, { year: 2026, month: 10 }, SETS)
    const overdue = overduePath(SEVERAL)
    const stale = stalePath(SEVERAL)

    // then: 고르지 않았을 때와 같다
    expect(quarter).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${OPEN}`)
    expect(month).toBe(`/deals?year=2026&month=10&owner=7&vendor=3&forecast=${OPEN}`)
    expect(overdue).toBe('/deals?owner=7&vendor=3&overdue=1')
    expect(stale).toBe('/deals?owner=7&vendor=3&stale=1')
  })

  // 테스트 코드: DSH-052
  it('왕복: Deals 목록이 고른 분기를 다시 읽는다', () => {
    // when: 네 주소를 목록 조회 조건으로 읽는다
    const tile = queryOf(forecastTilePath(SEVERAL, 'commit'))
    const open = queryOf(openTotalPath(SEVERAL, SETS) ?? '')
    const status = queryOf(statusPath(SEVERAL, 'poc_completed', SETS) ?? '')
    const total = queryOf(statusTotalPath(SEVERAL, SETS) ?? '')

    // then: 모두 분기 [1, 3]을 가진다
    expect(tile).toMatchObject({ year: 2026, quarters: [1, 3], forecastKeys: ['commit'] })
    expect(open).toMatchObject({ quarters: [1, 3], forecastKeys: SETS.open })
    expect(status).toMatchObject({ quarters: [1, 3], statusKey: 'poc_completed', forecastKeys: SETS.notLost })
    expect(total).toMatchObject({ quarters: [1, 3], forecastKeys: SETS.notLost })
  })

  // 테스트 코드: DSH-035
  it('분기 없는 왕복은 목록 조회 조건에도 분기가 없다', () => {
    // when: 분기 없는 주소를 목록 조회 조건으로 읽는다
    const query = queryOf(statusTotalPath(YEAR_ONLY, SETS) ?? '')

    // then: quarters가 없다
    expect(query).not.toHaveProperty('quarters')
  })
})
