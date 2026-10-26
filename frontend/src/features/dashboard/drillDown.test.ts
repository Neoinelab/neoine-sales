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
 * Drill-down URL(계획 4.5절 표 + Forecast 다중 조건 설계 5). 키 순서는 year, quarter, month, owner, vendor, status, forecast, overdue, stale로 고정(outcome은 2026-10-26부터 없음)한다.
 * Lost 제외·Open 숫자를 누르면 응답 `forecast.columns`로 만든 Forecast key 집합(알파벳순, 콤마 → %2C)이 `forecast`에 실린다.
 * scope = 대시보드 필터(연도·Quarter·담당자·Vendor). Vendor는 목록에 있는 id만 호출자가 넘긴다.
 */

const FULL = { year: 2026, quarter: 4, ownerId: 7, vendor: 3 } as const
const YEAR_ONLY = { year: 2026 } as const
const OWNER_ONLY = { year: 2026, ownerId: 7 } as const
const VENDOR_ONLY = { year: 2026, vendor: 3 } as const

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

describe('Forecast tile (하나)', () => {
  it('opens the deals of one forecast code with the whole filter', () => {
    expect(forecastTilePath(FULL, 'commit')).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=commit')
  })

  it('leaves out the quarter, owner and vendor that are not chosen', () => {
    expect(forecastTilePath(YEAR_ONLY, 'pipeline')).toBe('/deals?year=2026&forecast=pipeline')
    expect(forecastTilePath(OWNER_ONLY, 'best')).toBe('/deals?year=2026&owner=7&forecast=best')
    expect(forecastTilePath(VENDOR_ONLY, 'won')).toBe('/deals?year=2026&vendor=3&forecast=won')
  })
})

describe('Open total tile (Open 집합)', () => {
  it('opens the filter with every open forecast code', () => {
    expect(openTotalPath(FULL, SETS)).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${OPEN}`)
    expect(openTotalPath(YEAR_ONLY, SETS)).toBe(`/deals?year=2026&forecast=${OPEN}`)
  })

  it('has no link when there is no open code', () => {
    expect(openTotalPath(FULL, NO_OPEN)).toBeNull()
    expect(openTotalPath(FULL, NOTHING)).toBeNull()
  })
})

describe('Status bar and table (Lost 제외 집합)', () => {
  it('opens one status with the not-lost forecasts', () => {
    expect(statusPath(FULL, 'poc_completed', SETS)).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&status=poc_completed&forecast=${NOT_LOST}`)
  })

  it('matches the documented example: year 2026, owner 7, no vendor, POC완료', () => {
    expect(statusPath(OWNER_ONLY, 'poc_completed', SETS)).toBe(`/deals?year=2026&owner=7&status=poc_completed&forecast=${NOT_LOST}`)
  })

  it('opens all not-lost deals of the filter for the total row', () => {
    expect(statusTotalPath(FULL, SETS)).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${NOT_LOST}`)
    expect(statusTotalPath(YEAR_ONLY, SETS)).toBe(`/deals?year=2026&forecast=${NOT_LOST}`)
  })

  it('has no link when the not-lost set is empty', () => {
    expect(statusPath(FULL, 'poc_completed', NOTHING)).toBeNull()
    expect(statusTotalPath(FULL, NOTHING)).toBeNull()
  })

  it('still links with only Won, because Won is not lost', () => {
    expect(statusTotalPath(YEAR_ONLY, NO_OPEN)).toBe('/deals?year=2026&forecast=won')
  })
})

describe('attention tiles', () => {
  it('ignores the period for the overdue tile and keeps owner and vendor, without a forecast', () => {
    expect(overduePath(FULL)).toBe('/deals?owner=7&vendor=3&overdue=1')
    expect(overduePath(YEAR_ONLY)).toBe('/deals?overdue=1')
  })

  it('ignores the period for the stale tile and keeps owner and vendor, without a forecast', () => {
    expect(stalePath(FULL)).toBe('/deals?owner=7&vendor=3&stale=1')
    expect(stalePath(VENDOR_ONLY)).toBe('/deals?vendor=3&stale=1')
  })

  it('uses the server year and quarter of this quarter with the open forecasts', () => {
    expect(closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS)).toBe(`/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=${OPEN}`)
    expect(closingQuarterPath({ year: 2020, quarter: 1 }, { year: 2027, quarter: 1 }, SETS)).toBe(`/deals?year=2027&quarter=1&forecast=${OPEN}`)
  })

  it('uses the server year and month of this month with the open forecasts', () => {
    expect(closingMonthPath(FULL, { year: 2026, month: 10 }, SETS)).toBe(`/deals?year=2026&month=10&owner=7&vendor=3&forecast=${OPEN}`)
    expect(closingMonthPath({ year: 2020, quarter: 1 }, { year: 2027, month: 1 }, SETS)).toBe(`/deals?year=2027&month=1&forecast=${OPEN}`)
  })

  it('has no link for the closing tiles when there is no open code', () => {
    expect(closingQuarterPath(FULL, { year: 2026, quarter: 4 }, NO_OPEN)).toBeNull()
    expect(closingMonthPath(FULL, { year: 2026, month: 10 }, NO_OPEN)).toBeNull()
  })
})

describe('quarter chart and table (Forecast 탭)', () => {
  it('opens one forecast code of one quarter whatever quarter is chosen', () => {
    expect(quarterCellPath(FULL, 2, 'commit')).toBe('/deals?year=2026&quarter=2&owner=7&vendor=3&forecast=commit')
    expect(quarterCellPath(YEAR_ONLY, 3, 'won')).toBe('/deals?year=2026&quarter=3&forecast=won')
  })

  it('opens the not-lost deals of one quarter for the quarter total', () => {
    expect(quarterTotalPath(FULL, 1, SETS)).toBe(`/deals?year=2026&quarter=1&owner=7&vendor=3&forecast=${NOT_LOST}`)
    expect(quarterTotalPath(OWNER_ONLY, 4, SETS)).toBe(`/deals?year=2026&quarter=4&owner=7&forecast=${NOT_LOST}`)
  })

  it('has no link for the quarter total when the not-lost set is empty', () => {
    expect(quarterTotalPath(FULL, 1, NOTHING)).toBeNull()
  })
})

describe('round trip: the Deals list reads back the same condition (AC-15·16)', () => {
  it('forecast tile', () => {
    expect(queryOf(forecastTilePath(FULL, 'commit'))).toEqual({ ...PAGING, year: 2026, quarter: 4, ownerId: 7, vendorId: 3, forecastKeys: ['commit'] })
  })

  it('Open total', () => {
    expect(queryOf(openTotalPath(OWNER_ONLY, SETS) ?? '')).toEqual({ ...PAGING, year: 2026, ownerId: 7, forecastKeys: SETS.open })
  })

  it('status bar', () => {
    expect(queryOf(statusPath(FULL, 'poc_completed', SETS) ?? '')).toEqual({
      ...PAGING,
      year: 2026,
      quarter: 4,
      ownerId: 7,
      vendorId: 3,
      statusKey: 'poc_completed',
      forecastKeys: SETS.notLost,
    })
  })

  it('status total', () => {
    expect(queryOf(statusTotalPath(YEAR_ONLY, SETS) ?? '')).toEqual({ ...PAGING, year: 2026, forecastKeys: SETS.notLost })
  })

  it('overdue and stale tiles', () => {
    expect(queryOf(overduePath(FULL))).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, overdue: true })
    expect(queryOf(stalePath(FULL))).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, stale: true })
  })

  it('closing quarter and closing month tiles', () => {
    expect(queryOf(closingQuarterPath(FULL, { year: 2026, quarter: 4 }, SETS) ?? '')).toEqual({
      ...PAGING,
      year: 2026,
      quarter: 4,
      ownerId: 7,
      vendorId: 3,
      forecastKeys: SETS.open,
    })
    expect(queryOf(closingMonthPath(OWNER_ONLY, { year: 2026, month: 10 }, SETS) ?? '')).toEqual({
      ...PAGING,
      year: 2026,
      month: 10,
      ownerId: 7,
      forecastKeys: SETS.open,
    })
  })

  it('quarter cell and quarter total', () => {
    expect(queryOf(quarterCellPath(FULL, 2, 'commit'))).toEqual({ ...PAGING, year: 2026, quarter: 2, ownerId: 7, vendorId: 3, forecastKeys: ['commit'] })
    expect(queryOf(quarterTotalPath(FULL, 3, SETS) ?? '')).toEqual({
      ...PAGING,
      year: 2026,
      quarter: 3,
      ownerId: 7,
      vendorId: 3,
      forecastKeys: SETS.notLost,
    })
  })

  it('never carries sort, order or page (the list opens on its default order, page 1)', () => {
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

describe('outcome is gone from every path (AC-03)', () => {
  it('never carries outcome', () => {
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

    for (const path of paths) {
      expect(path).not.toContain('outcome')
      expect(queryOf(path ?? '')).not.toHaveProperty('forecastOutcome')
    }
  })

  it('keeps the documented condition order: forecast comes after status and before the flags', () => {
    expect(statusPath(FULL, 'prospecting', SETS)).toMatch(/\?year=2026&quarter=4&owner=7&vendor=3&status=prospecting&forecast=/)
    expect(closingMonthPath(FULL, { year: 2026, month: 10 }, SETS)).toMatch(/\?year=2026&month=10&owner=7&vendor=3&forecast=/)
    expect(quarterTotalPath(FULL, 1, SETS)).toMatch(/\?year=2026&quarter=1&owner=7&vendor=3&forecast=/)
  })
})
