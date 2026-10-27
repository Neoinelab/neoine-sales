import type { ReportCatalog, ReportCombine } from '../../../../shared/model/reportTypes'
import { fieldByKey } from './columnRules'
import type { DesignerState } from './designerState'

export interface ScopePrediction {
  rowScope: 'deal' | 'action'
  actionFilter: 'none' | 'exists' | 'join'
  dealNumbersOnce: boolean
}

/**
 * 설계가 어떤 행 단위로 조회될지 미리 보인다. 서버 `row_scope`·`action_filter`·`deal_numbers_once`와 같은 규칙이다:
 * Action 필드가 컬럼에 있으면 Action 행(Deal과 Join), 조건에만 있으면 Deal 행에 EXISTS,
 * Action 행에 그룹핑이 있고 Deal 숫자의 합계·평균 컬럼이 있으면 Deal마다 한 번만 더한다.
 */
export function predictScope(state: DesignerState, catalog: ReportCatalog): ScopePrediction {
  const entityOf = (key: string) => fieldByKey(catalog, key)?.entity
  const rowScope = state.columns.some((c) => entityOf(c.field) === 'action') ? 'action' : 'deal'
  const actionFilter = rowScope === 'action' ? 'join' : state.conditions.some((c) => entityOf(c.field) === 'action') ? 'exists' : 'none'
  const dealNumbersOnce =
    rowScope === 'action' &&
    state.columns.some((c) => c.group) &&
    state.columns.some((c) => !c.group && fieldByKey(catalog, c.field)?.dealNumber === true && (c.aggregate === 'sum' || c.aggregate === 'avg'))
  return { rowScope, actionFilter, dealNumbersOnce }
}

export interface ScopeText {
  headline: string
  notes: string[]
}

export function describeScope(prediction: ScopePrediction, combine: ReportCombine): ScopeText {
  const notes: string[] = []
  let headline = '행 단위: Deal 1건'
  if (prediction.rowScope === 'action') {
    headline = '행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)'
  } else if (prediction.actionFilter === 'exists') {
    headline = '행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만'
    notes.push(combine === 'and' ? '(같은 Action 하나가 모든 Action 조건을 만족)' : '(Action 조건 중 하나를 만족하는 Action이 있는 Deal)')
  }
  if (prediction.dealNumbersOnce) notes.push('Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다')
  return { headline, notes }
}
