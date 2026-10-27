// 편집 화면은 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { lastChart } from '../../../test/chartMock'
import { mockControl } from '../../../test/fake/default'
import { createChart, expectPressed, kindButton, openChartTab, optionAt, panelField } from '../../../test/reportChart'
import { addCountedColumn, chipItems, openEditor, saveButton, saveDialog, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const LEAVE_TITLE = '저장하지 않은 변경이 있습니다'
const REVERT_TITLE = '저장된 설계로 되돌릴까요?'
const WITH_CHART_ID = WITH_CHART.id
const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const unsavedMark = () => screen.queryByText(UNSAVED_MARK)
const openWithChart = () => openEditor(WITH_CHART_ID, { savedReports: [...SAVED_SAMPLES, WITH_CHART] })

async function overwrite(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(saveButton())
  await user.click(within(await saveDialog()).getByRole('button', { name: '저장' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

async function revert(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await user.click(screen.getByRole('button', { name: '되돌리기' }))
  await user.click(within(await screen.findByRole('dialog', { name: REVERT_TITLE })).getByRole('button', { name: '되돌리기' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

describe('저장된 차트 열기 (AC18)', () => {
  it('opens a saved chart with the same panel values and chart options', async () => {
    const { user } = await openWithChart()

    await openChartTab(user)

    expectPressed('세로 막대')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(panelField('범례')).toHaveDisplayValue('위')
    expect(panelField('가로축 제목')).toHaveValue('Vendor')
    expect(panelField('세로축 제목')).toHaveValue('금액 합계')
    expect(lastChart().type).toBe('bar')
    expect(optionAt('plugins', 'title')).toMatchObject({ display: true, text: 'Vendor별 금액' })
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('offers to make a chart for a saved report without one', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)

    await openChartTab(user)

    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('saves a new chart by overwrite and shows the same settings when the report is opened again', async () => {
    const { user, goTo } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)
    await user.click(kindButton('꺾은선'))
    await user.type(panelField('차트 제목'), '저장할 제목')
    await user.selectOptions(panelField('범례'), '오른쪽')
    await user.click(panelField('데이터 레이블'))

    await overwrite(user)

    const sent = mockControl.savedReportRequests().find((r) => r.op === 'update')
    expect((sent?.body as { chart: unknown }).chart).toMatchObject({ kind: 'line', category: 0, values: [1], title: '저장할 제목', legend: 'right', dataLabels: true })
    expect((await gateway.reports.get(MINE_PUBLIC.id)).chart).toMatchObject({ kind: 'line', title: '저장할 제목' })
    expect(unsavedMark()).not.toBeInTheDocument()

    goTo('/reports')
    await screen.findByRole('table', { name: '리포트 목록' })
    goTo(`/reports/${MINE_PUBLIC.id}/edit`)
    await screen.findByRole('table', { name: '조회 결과' })
    await openChartTab(user)
    expectPressed('꺾은선')
    expect(panelField('차트 제목')).toHaveValue('저장할 제목')
    expect(panelField('범례')).toHaveDisplayValue('오른쪽')
    expect(panelField('데이터 레이블')).toBeChecked()
    expect(lastChart().type).toBe('line')
    expect(optionAt('plugins', 'legend', 'position')).toBe('right')
  })

  it('removes the saved chart on overwrite after the delete button', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.click(await screen.findByRole('button', { name: '차트 삭제' }))

    await overwrite(user)

    expect((await gateway.reports.get(WITH_CHART_ID)).chart).toBeNull()
    expect((await gateway.reports.list()).find((r) => r.id === WITH_CHART_ID)?.chartKind).toBeNull()
  })

  it('keeps the chart of a report on overwrite when only the chart title is changed', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 수정')

    await overwrite(user)

    expect((await gateway.reports.get(WITH_CHART_ID)).chart).toMatchObject({ ...VENDOR_CHART, title: 'Vendor별 금액 수정' })
    expect((await gateway.reports.get(WITH_CHART_ID)).revision).toBe(2)
  })
})

describe('저장 안 됨과 떠날 때 확인 (AC16)', () => {
  it('marks unsaved when a chart is made, keeps the result fresh and asks before leaving', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    expect(unsavedMark()).not.toBeInTheDocument()
    await openChartTab(user)

    await createChart(user)

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(saveButton()).toBeEnabled()
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    expect(mockControl.reportQueries()).toHaveLength(1)
    await user.click(menuLink('Deals'))
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('marks unsaved when the chart is changed and clears the mark when it is changed back', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)

    await user.type(panelField('차트 제목'), 'x')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    await user.type(panelField('차트 제목'), '{Backspace}')

    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('marks unsaved when the saved chart is deleted', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)

    await user.click(await screen.findByRole('button', { name: '차트 삭제' }))

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(saveButton()).toBeEnabled()
  })

  it('is not unsaved after a chart is made and deleted again', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)

    await user.click(screen.getByRole('button', { name: '차트 삭제' }))

    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기 (AC16)', () => {
  it('restores the saved chart settings', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    await user.click(kindButton('꺾은선'))

    await revert(user)

    await openChartTab(user)
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expectPressed('세로 막대')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('removes a chart that was made after loading', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)

    await revert(user)

    await openChartTab(user)
    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeVisible()
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('덮어쓰기 뒤 기준선 (리뷰 Minor)', () => {
  it('is not unsaved after overwriting a chart title with surrounding spaces and reverting a later change', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.clear(panelField('차트 제목'))
    await user.type(panelField('차트 제목'), '  매출  ')

    await overwrite(user)

    expect((await gateway.reports.get(WITH_CHART_ID)).chart?.title).toBe('매출')
    expect(unsavedMark()).not.toBeInTheDocument()
    await user.selectOptions(panelField('범례'), '아래')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    await revert(user)
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기 분기 (리뷰 Minor, 분기 고정용: 현재 구현에서 green일 수 있음)', () => {
  it('keeps the result table and restores only the chart when only the chart was changed', async () => {
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    await user.click(kindButton('꺾은선'))
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    await revert(user)

    await user.click(screen.getByRole('tab', { name: '결과 표' }))
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    await openChartTab(user)
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expectPressed('세로 막대')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('clears the result and restores the design and the chart when the query design was also changed', async () => {
    const { user } = await openWithChart()
    await user.selectOptions(screen.getByRole('combobox', { name: '정렬' }), '(정렬 없음)')
    await addCountedColumn(user, 'Deal code')
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    expect(chipItems()).toHaveLength(3)

    await revert(user)

    expect(chipItems()).toHaveLength(2)
    expect(screen.getByRole('combobox', { name: '정렬' })).toHaveDisplayValue(/금액 합계/)
    expect(screen.getByRole('combobox', { name: '정렬 방향' })).toHaveDisplayValue(/내림|desc/i)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    await openChartTab(user)
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('깨진 차트로 편집 화면을 열 때 (리뷰 Minor, 메인 세션 결정)', () => {
  it('tells that the stored chart could not be read, like the view page', async () => {
    const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
    const broken = savedReport({ id: 22, name: '깨진 차트', chartProblem: PROBLEM })
    const { user } = await openEditor(broken.id, { savedReports: [...SAVED_SAMPLES, broken] })

    await openChartTab(user)

    expect(screen.getByText(PROBLEM)).toBeVisible()
  })
})
