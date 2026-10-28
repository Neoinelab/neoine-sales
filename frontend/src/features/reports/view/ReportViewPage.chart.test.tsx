// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { lastChart, renderedCharts } from '../../../test/chartMock'
import { arrangement, chooseView, queryTile, tile, tileOrder, viewRadio } from '../../../test/reportLayout'
import { openView, setupReportClock } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
const MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
const open = (reports = [WITH_CHART]) => openView(reports[0]?.id ?? WITH_CHART.id, { savedReports: [...SAVED_SAMPLES, ...reports] })

describe('보기 화면의 차트 타일 (AC10, AC19, 작성/결과 탭 분리 AC9)', () => {
  it('shows the table tile and the chart tile of a report with a chart and draws the chart without a settings panel', async () => {
    await open()

    expect(await screen.findByRole('img')).toBeVisible()
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(tileOrder()).toEqual(['표', '차트']) // 저장된 값이 없으면 기본 배치(표 → 차트, 두 줄)
    expect(arrangement()).toBe('stacked')
    expect(lastChart().type).toBe('bar')
    expect(lastChart().options).toMatchObject({ plugins: { title: { display: true, text: VENDOR_CHART.title } } })
    for (const label of ['범주', '차트 제목', '범례']) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    for (const name of ['차트 만들기', '차트 삭제', '세로 막대', '차트 설정']) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  })

  it('has no result tabs any more', async () => {
    await open()
    await screen.findByRole('img')

    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  })

  it('hides the chart tile when the table only view is chosen and shows it again afterwards', async () => {
    const { user } = await open()
    await screen.findByRole('img')

    await chooseView(user, '표만')

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(queryTile('차트')).toBeNull()

    await chooseView(user, '표+차트')

    expect(await screen.findByRole('img')).toBeVisible()
  })

  it('shows only the chart for the chart only view', async () => {
    const { user } = await open()
    await screen.findByRole('img')

    await chooseView(user, '차트만')

    expect(queryTile('표')).toBeNull()
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(screen.getByRole('img')).toBeVisible()
  })

  it('opens with only the table tile and disabled chart views when the report has no chart', async () => {
    await openView(MINE_PUBLIC.id)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(viewRadio('표+차트')).toBeDisabled()
    expect(viewRadio('차트만')).toBeDisabled()
    expect(queryTile('차트')).toBeNull()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
    expect(renderedCharts()).toHaveLength(0)
  })

  it('tells that the stored chart could not be read when the server reports a chart problem', async () => {
    const broken = savedReport({ id: 22, name: '깨진 차트', chartProblem: PROBLEM })
    await open([broken])
    await screen.findByRole('table', { name: '조회 결과' })

    expect(screen.getByText(PROBLEM)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(viewRadio('차트만')).toBeDisabled()
  })

  it('tells that the chart does not fit the current result instead of drawing a wrong one', async () => {
    const mismatched = savedReport({ id: 23, name: '어긋난 차트', chart: { ...VENDOR_CHART, category: 1 } })
    await open([mismatched])

    expect(await screen.findByText(MISMATCH)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
