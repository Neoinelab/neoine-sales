import { describe, expect, it } from 'vitest'
import type { SavedReportSummary } from '../../../shared/model/reportTypes'
import { KIM, OLD, PARK, savedReport } from '../../../test/savedReports'
import { filterReports } from './filterReports'

/** 목록 검색·내가 만든 거르기. 서버 순서를 그대로 유지한다. */

const ITEMS: SavedReportSummary[] = [
  savedReport({ id: 5, name: 'Vendor별 Pipeline', description: '올해 Expected Close', owner: KIM }),
  savedReport({ id: 4, name: '담당자 현황', description: 'VENDOR 별 점검', owner: PARK }),
  savedReport({ id: 3, name: '미업데이트 Deal', description: '', owner: KIM }),
  savedReport({ id: 2, name: '퇴사자 리포트', description: '인수인계', owner: OLD }),
]
const ids = (items: SavedReportSummary[]): number[] => items.map((i) => i.id)

describe('filterReports', () => {
  // 테스트 코드: RS-056
  it('이름 또는 설명을 대소문자 없이 거르고 내가 만든 것만 거를 수 있다', () => {
    // when: 검색어 "vendor"로 전체·내 리포트만 걸러 번호를 구한다
    const actual = ids(filterReports(ITEMS, { q: 'vendor', mine: false }, KIM.id))
    const actual2 = ids(filterReports(ITEMS, { q: 'vendor', mine: true }, KIM.id))
    const actual3 = ids(filterReports(ITEMS, { q: '', mine: true }, KIM.id))
    // then: 검색어만 / 검색어+내가 만든 것 / 내가 만든 것만 거른 결과가 맞다
    expect(actual).toEqual([5, 4])
    expect(actual2).toEqual([5])
    expect(actual3).toEqual([5, 3])
  })

  // 테스트 코드: RS-056
  it('빈 검색어와 공백 검색어는 전부 돌려주고 서버 순서를 지킨다', () => {
    // when: 빈 검색어와 공백뿐인 검색어로 걸러 번호를 구한다
    const actual = ids(filterReports(ITEMS, { q: '', mine: false }, KIM.id))
    const actual2 = ids(filterReports(ITEMS, { q: '   ', mine: false }, KIM.id))
    // then: 빈 검색어·공백 검색어 모두 서버 순서의 전부다
    expect(actual).toEqual([5, 4, 3, 2])
    expect(actual2).toEqual([5, 4, 3, 2])
  })

  // 테스트 코드: RS-056
  it('검색어의 앞뒤 공백을 지우고 이름의 일부와 맞춘다', () => {
    // when: 앞뒤 공백이 있는 검색어 "업데이트"로 걸러 번호를 구한다
    const actual = ids(filterReports(ITEMS, { q: '  업데이트 ', mine: false }, KIM.id))
    // then: 공백이 있어도 이름 일부로 찾는다
    expect(actual).toEqual([3])
  })

  // 테스트 코드: RS-056
  it('설명에도 맞춘다', () => {
    // when: 검색어 "인수인계"로 걸러 번호를 구한다
    const actual = ids(filterReports(ITEMS, { q: '인수인계', mine: false }, KIM.id))
    // then: 설명에만 있는 말로 찾는다
    expect(actual).toEqual([2])
  })

  // 테스트 코드: RS-056
  it('맞는 것이 없으면 빈 목록이고 입력을 바꾸지 않는다', () => {
    // given: 입력 id 목록을 적어 둔다
    const before = ids(ITEMS)

    // when: 맞는 것이 없는다
    const actual = filterReports(ITEMS, { q: '없는말', mine: false }, KIM.id)
    // then: 빈 목록이다
    expect(actual).toEqual([])
    // then: 입력은 그대로다
    expect(ids(ITEMS)).toEqual(before)
  })

  // 테스트 코드: RS-056
  it('내가 만든 것은 보는 사람의 id로 판정한다', () => {
    // when: 내 리포트만 보기로 다른 사용자와 없는 사용자 번호로 걸러 번호를 구한다
    const actual = ids(filterReports(ITEMS, { q: '', mine: true }, PARK.id))
    const actual2 = ids(filterReports(ITEMS, { q: '', mine: true }, 9999))
    // then: 박영업 id면 박영업 것만, 없는 id면 빈 목록이다
    expect(actual).toEqual([4])
    expect(actual2).toEqual([])
  })
})
