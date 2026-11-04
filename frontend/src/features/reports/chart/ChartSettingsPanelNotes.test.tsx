import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { withColumns } from '../../../test/reportDesigner'
import { ChartSettingsPanel } from './ChartSettingsPanel'
import type { ChartDraft } from './chartDraft'

/** 재리뷰 후속 AC11: 화면 안내와 같은 문구의 서버 `("chart","kind")` 문제는 한 번만 보인다. */
const MESSAGE = '이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다'
const headerOf = (uid: number): string => `H${uid}`
const draft: ChartDraft = {
  kind: 'pie',
  categoryUid: 1,
  seriesUid: null,
  valueUids: [3],
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

function renderPanel(serverTexts: string[]) {
  const columns = withColumns('deal.code', 'deal.status', 'deal.amount').columns
  const serverIssues = serverTexts.map((text, i) => ({ id: `s${i}`, part: 'kind', text }))
  render(
    <ChartSettingsPanel draft={draft} columns={columns} headerOf={headerOf} issues={[{ part: 'category', message: MESSAGE }]} serverIssues={serverIssues} dispatch={() => undefined} />,
  )
}

describe('ChartSettingsPanel: 같은 문구 안내 (재리뷰 후속 AC11)', () => {
  it('shows the group count notice once when the server reports the same sentence', () => {
    renderPanel([MESSAGE])

    expect(screen.getAllByText(MESSAGE)).toHaveLength(1)
  })

  it('still shows a different server sentence of the kind part', () => {
    renderPanel(['다른 서버 문제'])

    expect(screen.getByText('다른 서버 문제')).toBeInTheDocument()
    expect(screen.getAllByText(MESSAGE)).toHaveLength(1)
  })
})
