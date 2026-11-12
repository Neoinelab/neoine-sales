import { describe, expect, it } from 'vitest'
import type { ReportIssue } from '../../../../shared/model/reportTypes'
import { issueAnchors, visibleIssues } from './issues'

const RUN = { columnUids: [10, 11, 12], conditionUids: [20, 21] }

const issue = (location: (string | number)[], message = '문구'): ReportIssue => ({ location, code: 'x', message })

describe('위반 위치 붙이기', () => {
  // 테스트 코드: RQ-090
  it('서버 위치를 마지막 조회의 컬럼·조건 uid로 옮긴다', () => {
    // given: 컬럼·조건·결합·정렬·최대 행 위치의 위반들
    const issues = [
      issue(['columns', 1, 'field']),
      issue(['columns', 2]),
      issue(['columns']),
      issue(['conditions', 0, 'value']),
      issue(['conditions', 1]),
      issue(['conditions']),
      issue(['combine']),
      issue(['columns', 0, 'sort']),
      issue(['row_limit']),
    ]

    // when: 위반 위치를 마지막 조회의 uid에 붙인다
    const anchored = issueAnchors(issues, RUN)

    // then: 위치마다 알맞은 컬럼·조건·결합·최대 행 대상이 되고 위반은 그대로다
    expect(anchored.map((a) => a.target)).toEqual([
      { kind: 'column', uid: 11, part: 'field' },
      { kind: 'column', uid: 12, part: null },
      { kind: 'columns' },
      { kind: 'condition', uid: 20, part: 'value' },
      { kind: 'condition', uid: 21, part: null },
      { kind: 'conditions' },
      { kind: 'combine' },
      { kind: 'column', uid: 10, part: 'sort' },
      { kind: 'rowLimit' },
    ])
    expect(anchored.map((a) => a.issue)).toEqual(issues)
  })

  // 테스트 코드: RQ-091
  it('모르는 위치는 일반 목록에 둔다', () => {
    // when: 모르는 위치, 없는 컬럼 번호, 빈 위치의 위반을 붙인다
    const anchored = issueAnchors([issue(['nowhere']), issue(['columns', 9, 'field']), issue([])], RUN)

    // then: 모두 일반 목록이다
    expect(anchored.map((a) => a.target)).toEqual([{ kind: 'general' }, { kind: 'general' }, { kind: 'general' }])
  })

  // 테스트 코드: RQ-091
  it('예전 최상위 정렬 위치는 일반 목록에 둔다', () => {
    // when: 최상위 sort 위치의 위반을 붙인다
    const anchored = issueAnchors([issue(['sort', 'column']), issue(['sort'])], RUN)

    // then: 모두 일반 목록이다
    expect(anchored.map((a) => a.target)).toEqual([{ kind: 'general' }, { kind: 'general' }])
  })
})

describe('보이는 위반', () => {
  const anchored = issueAnchors(
    [issue(['columns', 0, 'aggregate'], 'a'), issue(['columns', 1, 'field'], 'b'), issue(['conditions', 0, 'value'], 'c'), issue(['row_limit'], 'd'), issue(['x'], 'e')],
    RUN,
  )
  const live = { columnUids: [10, 11, 12], conditionUids: [20, 21] }

  // 테스트 코드: RQ-092
  it('바뀐 것이 없으면 위반을 모두 유지한다', () => {
    // when: 편집한 항목이 없는다
    const actual = visibleIssues(anchored, live, new Set()).map((a) => a.issue.message)
    // then: 위반 다섯이 모두 보인다
    expect(actual).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  // 테스트 코드: RQ-092
  it('지웠거나 고친 항목의 위반은 뺀다', () => {
    // given: 컬럼 10과 조건 20을 지운 현재 상태에서 컬럼 11을 고쳤다
    const afterRemove = { columnUids: [11, 12], conditionUids: [21] }

    // when: 보이는 위반을 구한다
    const visible = visibleIssues(anchored, afterRemove, new Set([11]))

    // then: 남은 위반은 최대 행과 일반 위반뿐이다
    expect(visible.map((a) => a.issue.message)).toEqual(['d', 'e'])
  })

  // 테스트 코드: RQ-092
  it('고친 항목의 위반만 뺀다', () => {
    // when: 컬럼 10을 고친 상태에서 보이는 위반을 구한다
    const visible = visibleIssues(anchored, live, new Set([10]))

    // then: 컬럼 10의 위반만 빠진다
    expect(visible.map((a) => a.issue.message)).toEqual(['b', 'c', 'd', 'e'])
  })
})

describe('차트 위치의 위반', () => {
  // 테스트 코드: RC-069
  it('차트 위치의 위반은 차트 대상과 칸 이름으로 바꾼다', () => {
    // when: 차트 위치의 위반 다섯 개를 결과 위치로 바꾼다
    const anchored = issueAnchors(
      [issue(['chart']), issue(['chart', 'category']), issue(['chart', 'values']), issue(['chart', 'values', 1]), issue(['chart', 'value_min'])],
      RUN,
    )

    // then: 차트 대상이고 칸 이름이 전체(null)·category·values·values·value_min이다
    expect(anchored.map((a) => a.target)).toEqual([
      { kind: 'chart', part: null },
      { kind: 'chart', part: 'category' },
      { kind: 'chart', part: 'values' },
      { kind: 'chart', part: 'values' },
      { kind: 'chart', part: 'value_min' },
    ])
  })

  // 테스트 코드: RC-069
  it('중첩된 옵션 이름은 점으로 잇고 항목 번호는 버린다', () => {
    // when: 구간·콤보 계열·합계 위치의 위반을 결과 위치로 바꾼다
    const anchored = issueAnchors(
      [issue(['chart', 'histogram', 'bin_count']), issue(['chart', 'histogram']), issue(['chart', 'combo_series', 1]), issue(['chart', 'combo_series']), issue(['chart', 'show_total'])],
      RUN,
    )

    // then: 칸 이름이 histogram.bin_count·histogram·combo_series·combo_series·show_total이다
    expect(anchored.map((a) => a.target)).toEqual([
      { kind: 'chart', part: 'histogram.bin_count' },
      { kind: 'chart', part: 'histogram' },
      { kind: 'chart', part: 'combo_series' },
      { kind: 'chart', part: 'combo_series' },
      { kind: 'chart', part: 'show_total' },
    ])
  })
})
