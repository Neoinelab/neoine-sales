// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { lastChart, renderedCharts } from '../../../test/chartMock'
import { openChartTab, tabNamed } from '../../../test/reportChart'
import { openView, setupReportClock } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
const MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
const open = (reports = [WITH_CHART]) => openView(reports[0]?.id ?? WITH_CHART.id, { savedReports: [...SAVED_SAMPLES, ...reports] })

describe('보기 화면의 차트 (AC10, AC19)', () => {
  it('opens on the chart tab when the report has a chart and draws it without a settings panel', async () => {
    await open()

    expect(await screen.findByRole('tab', { name: '차트', selected: true })).toBeVisible()
    expect(await screen.findByRole('img')).toBeVisible()
    expect(lastChart().type).toBe('bar')
    expect(lastChart().options).toMatchObject({ plugins: { title: { display: true, text: VENDOR_CHART.title } } })
    for (const label of ['범주', '차트 제목', '범례']) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    for (const name of ['차트 만들기', '차트 삭제', '세로 막대']) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  })

  it('switches between the chart and the result table', async () => {
    const { user } = await open()
    await screen.findByRole('img')

    await user.click(tabNamed('결과 표'))

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('opens on the result table when the report has no chart and offers no chart making', async () => {
    const { user } = await openView(MINE_PUBLIC.id)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(tabNamed('결과 표')).toHaveAttribute('aria-selected', 'true')
    await openChartTab(user)
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
    expect(renderedCharts()).toHaveLength(0)
  })

  it('tells that the stored chart could not be read when the server reports a chart problem', async () => {
    const broken = savedReport({ id: 22, name: '깨진 차트', chartProblem: PROBLEM })
    const { user } = await open([broken])
    await screen.findByRole('table', { name: '조회 결과' })

    await openChartTab(user)

    expect(screen.getByText(PROBLEM)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('tells that the chart does not fit the current result instead of drawing a wrong one', async () => {
    const mismatched = savedReport({ id: 23, name: '어긋난 차트', chart: { ...VENDOR_CHART, category: 1 } })
    await open([mismatched])

    expect(await screen.findByText(MISMATCH)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
