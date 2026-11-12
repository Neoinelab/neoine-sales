import { describe, expect, it } from 'vitest'
import type { DesignerAction, DesignerState } from './designerState'
import { emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { describeScope, predictScope } from './scope'

/** 필드들을 컬럼으로 넣고, 지정한 인덱스를 그룹으로 만든 설계. */
function design(keys: string[], groupIndexes: number[] = [], extra: DesignerAction[] = []): DesignerState {
  const state = withColumns(...keys)
  return reduce(
    state,
    ...groupIndexes.map((i): DesignerAction => ({ type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })),
    ...extra,
  )
}

const actionCondition: DesignerAction = { type: 'addCondition', field: fieldOf('action.action') }

describe('predictScope', () => {
  const cases: [string, DesignerState, { rowScope: string; actionFilter: string; dealNumbersOnce: boolean }][] = [
    ['Deal columns only', design(['deal.code']), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['an Action condition only', design(['deal.code'], [], [actionCondition]), { rowScope: 'deal', actionFilter: 'exists', dealNumbersOnce: false }],
    ['a Deal condition only', design(['deal.code'], [], [{ type: 'addCondition', field: fieldOf('deal.name') }]), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['an Action column', design(['deal.code', 'action.action']), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['an Action column and an Action condition', design(['action.action'], [], [actionCondition]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['the Action count column', design(['deal.vendor', 'action.count'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['Deal numbers summed in Action rows with a group', design(['action.type', 'deal.amount'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }],
    ['Deal numbers averaged in Action rows with a group', design(['action.type', 'deal.status_days'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }],
    ['Deal numbers without a group in Action rows', design(['action.action', 'deal.amount']), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['a Deal number summed in Deal rows with a group', design(['deal.vendor', 'deal.amount'], [0]), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['a non Deal number counted in Action rows with a group', design(['action.type', 'deal.name'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
  ]

  // 테스트 코드: RQ-073
  it.each(cases)('서버와 같게 행 범위·Action 조건 방식·Deal당 한 번을 예측한다: %s', (_name, state, expected) => {
    // when: 사례별 설계(Deal 조건·Action 컬럼·그룹과 Deal 숫자 등)의 범위를 예측한다
    const actual = predictScope(state, REPORT_CATALOG)
    // then: 설계의 예측이 기대와 같다
    expect(actual).toEqual(expected)
  })

  // 테스트 코드: RQ-073
  it('최소·최대는 Deal당 한 번으로 치지 않는다', () => {
    // given: Action 유형을 그룹핑하고 금액을 넣은 설계
    const base = design(['action.type', 'deal.amount'], [0])
    // when: 금액 집계를 최소와 최대로 각각 바꾼다
    const withMin = reduce(base, { type: 'updateColumn', uid: uidAt(base, 1), patch: { aggregate: 'min' } })
    const withMax = reduce(base, { type: 'updateColumn', uid: uidAt(base, 1), patch: { aggregate: 'max' } })

    // then: 둘 다 Deal당 한 번이 아니다
    expect(predictScope(withMin, REPORT_CATALOG).dealNumbersOnce).toBe(false)
    expect(predictScope(withMax, REPORT_CATALOG).dealNumbersOnce).toBe(false)
  })

  // 테스트 코드: RQ-073
  it('빈 설계는 Deal 행으로 본다', () => {
    // when: 빈 설계의 범위를 예측한다
    const actual = predictScope(emptyDesign(), REPORT_CATALOG)
    // then: 빈 설계의 예측이 Deal 행·조건 없음·한 번 아님이다
    expect(actual).toEqual({ rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false })
  })
})

describe('describeScope', () => {
  // 테스트 코드: RQ-073
  it('Deal 행 범위의 안내 문구', () => {
    // when: Deal 행 범위의 설명을 만든다
    const actual = describeScope({ rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }, 'and')
    // then: 제목이 행 단위 Deal 1건이고 보충 안내가 없다
    expect(actual).toEqual({
      headline: '행 단위: Deal 1건',
      notes: [],
    })
  })

  // 테스트 코드: RQ-073
  it('Action 행 범위는 Join 안내 문구를 갖는다', () => {
    // when: Action 행 범위의 설명을 만든다
    const actual = describeScope({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }, 'and')
    // then: 제목이 Action 1건과 Join 안내이고 보충 안내가 없다
    expect(actual).toEqual({
      headline: '행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)',
      notes: [],
    })
  })

  // 테스트 코드: RQ-073
  it('EXISTS 안내는 AND와 OR에 따라 보충 문구가 다르다', () => {
    // given: Action 조건만 있는 EXISTS 범위
    const exists = { rowScope: 'deal', actionFilter: 'exists', dealNumbersOnce: false } as const

    // when: AND와 OR로 안내 문구를 만든다
    const and = describeScope(exists, 'and')
    const or = describeScope(exists, 'or')

    // then: 제목은 같고 보충 안내는 AND는 같은 Action 하나, OR는 조건 중 하나다
    expect(and.headline).toBe('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(or.headline).toBe('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(and.notes).toEqual(['(같은 Action 하나가 모든 Action 조건을 만족)'])
    expect(or.notes).toEqual(['(Action 조건 중 하나를 만족하는 Action이 있는 Deal)'])
  })

  // 테스트 코드: RQ-073
  it('Deal 숫자는 Deal당 한 번 더한다는 보충 안내가 붙는다', () => {
    // when: Deal당 한 번인 범위의 안내를 만든다
    const scope = describeScope({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }, 'and')

    // then: Deal 숫자는 Deal마다 한 번만 더한다는 안내다
    expect(scope.notes).toEqual(['Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다'])
  })
})
