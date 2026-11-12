import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { withColumns } from '../../../test/reportDesigner'
import { ChartSettingsPanel } from './ChartSettingsPanel'
import type { ChartDraft } from './chartDraft'

/**
 * 그룹핑 없는 히스토그램의 값 후보는 숫자 컬럼만이다.
 * 계약: `ChartSettingsPanel`이 선택 props `isNumberField?: (field: string) => boolean`를 받는다.
 * 히스토그램이고 그룹핑 컬럼이 없을 때만 값 체크박스를 숫자 필드로 거른다(생략하면 거르지 않는다).
 */

const isNumber = (field: string): boolean => ['deal.amount', 'deal.users'].includes(field)
const headerOf = (uid: number): string => `H${uid}`

const draft: ChartDraft = {
  kind: 'histogram',
  categoryUid: null,
  seriesUid: null,
  valueUids: [2],
  swap: false,
  title: '',
  legend: 'top',
  dataLabels: false,
  categoryAxisTitle: '',
  valueAxisTitle: '',
  valueMin: '',
  valueMax: '',
  secondaryAxis: false,
  histogram: { mode: 'auto', count: '', width: '', overflow: '', underflow: '' },
  showTotal: false,
  comboTypes: {},
}

function renderPanel(over: Partial<ChartDraft> = {}) {
  // uid 1 = Deal code(텍스트), 2 = 금액, 3 = Users
  const columns = withColumns('deal.code', 'deal.amount', 'deal.users').columns
  render(<ChartSettingsPanel draft={{ ...draft, ...over }} columns={columns} headerOf={headerOf} issues={[]} serverIssues={[]} dispatch={() => undefined} isNumberField={isNumber} />)
}

describe('ChartSettingsPanel: 히스토그램 값 후보', () => {
  // 테스트 코드: RC-060
  it('그룹핑 없는 히스토그램의 값 후보는 숫자 컬럼만이다', () => {
    // when: 그룹핑 없는 히스토그램 설정 패널을 그린다 (전제: 텍스트·금액·Users 컬럼)
    renderPanel()

    // then: 텍스트 컬럼은 값 체크박스에 없고 금액·Users만 있다
    expect(screen.queryByRole('checkbox', { name: 'H1' })).toBeNull()
    expect(screen.getByRole('checkbox', { name: 'H2' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'H3' })).toBeInTheDocument()
  })

  // 테스트 코드: RC-059
  it('히스토그램이 아닌 종류는 모든 컬럼이 값 후보다', () => {
    // when: 파레토 설정 패널을 그린다
    renderPanel({ kind: 'pareto', categoryUid: 1, valueUids: [2] })

    // then: 텍스트 컬럼도 값 체크박스에 있다
    expect(screen.getByRole('checkbox', { name: 'H1' })).toBeInTheDocument()
  })
})
