import { describe, expect, it } from 'vitest'
import type { SavedReportSummary } from '../../../shared/model/reportTypes'
import { KIM, OLD, PARK, savedReport } from '../../../test/savedReports'
import { filterReports } from './filterReports'

/** 목록 검색·내가 만든 거르기(Reports 3단계 P5, AC12). 서버 순서를 그대로 유지한다. */

const ITEMS: SavedReportSummary[] = [
  savedReport({ id: 5, name: 'Vendor별 Pipeline', description: '올해 Expected Close', owner: KIM }),
  savedReport({ id: 4, name: '담당자 현황', description: 'VENDOR 별 점검', owner: PARK }),
  savedReport({ id: 3, name: '미업데이트 Deal', description: '', owner: KIM }),
  savedReport({ id: 2, name: '퇴사자 리포트', description: '인수인계', owner: OLD }),
]
const ids = (items: SavedReportSummary[]): number[] => items.map((i) => i.id)

describe('filterReports', () => {
  it('filters by name or description ignoring case and by mine', () => {
    expect(ids(filterReports(ITEMS, { q: 'vendor', mine: false }, KIM.id))).toEqual([5, 4])
    expect(ids(filterReports(ITEMS, { q: 'vendor', mine: true }, KIM.id))).toEqual([5])
    expect(ids(filterReports(ITEMS, { q: '', mine: true }, KIM.id))).toEqual([5, 3])
  })

  it('returns everything for an empty or blank search and keeps the server order', () => {
    expect(ids(filterReports(ITEMS, { q: '', mine: false }, KIM.id))).toEqual([5, 4, 3, 2])
    expect(ids(filterReports(ITEMS, { q: '   ', mine: false }, KIM.id))).toEqual([5, 4, 3, 2])
  })

  it('trims the search text and matches a part of the name', () => {
    expect(ids(filterReports(ITEMS, { q: '  업데이트 ', mine: false }, KIM.id))).toEqual([3])
  })

  it('matches the description too', () => {
    expect(ids(filterReports(ITEMS, { q: '인수인계', mine: false }, KIM.id))).toEqual([2])
  })

  it('returns nothing when nothing matches and does not change its input', () => {
    const before = ids(ITEMS)

    expect(filterReports(ITEMS, { q: '없는말', mine: false }, KIM.id)).toEqual([])
    expect(ids(ITEMS)).toEqual(before)
  })

  it('judges mine by the owner id of the viewer', () => {
    expect(ids(filterReports(ITEMS, { q: '', mine: true }, PARK.id))).toEqual([4])
    expect(ids(filterReports(ITEMS, { q: '', mine: true }, 9999))).toEqual([])
  })
})
