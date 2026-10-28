// 차트 탭은 React.lazy 청크이므로 reportChart 도구가 미리 읽어 둔다.
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DATALABELS_MOCK_ID, lastChart, renderedCharts } from '../../../test/chartMock'
import { mockControl } from '../../../test/fake/default'
import {
  AMOUNT_HEADER,
  amountCol,
  chartDatasets,
  chartLabels,
  createChart,
  expectPressed,
  kindButton,
  openChartTab,
  openGroupedDesigner,
  optionAt,
  panelField,
  STATUS_COL,
  chartToggle,
  USERS_HEADER,
  usersCol,
  VENDOR_COL,
  valueGroup,
} from '../../../test/reportChart'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { expectTab, resultTab, showTab, tile } from '../../../test/reportLayout'
import {
  addColumn,
  answerWith,
  chipButton,
  openDesigner,
  rerun,
  runQuery,
  saveButton,
  saveDialog,
  settingsOf,
  setupReportClock,
  typeName,
} from '../../../test/reportScreen'

setupReportClock()

const NEEDS_GROUPING = '그룹핑한 결과로 차트를 만들 수 있습니다'
const TOO_MANY_GROUPS = '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다'
const ALL_KINDS = ['세로 막대', '가로 막대', '누적 막대', '100% 누적', '꺾은선', '영역', '원', '도넛', '분산형', '콤보']

describe('결과 탭의 차트 타일 (작성/결과 탭 분리 AC9, AC10, AC16)', () => {
  it('has no chart tab: the chart is a tile next to the table tile on the result tab', async () => {
    await openGroupedDesigner(1)

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
    expectTab('result')
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(renderedCharts()).toHaveLength(0)
  })

  it('shows the make-chart empty state in the chart tile before a chart exists', async () => {
    await openGroupedDesigner(1)

    expect(await within(tile('차트')).findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(chartToggle()).toBeNull()
  })

  it('opens the settings panel when a chart is made and toggles it with the chart settings button', async () => {
    const { user } = await openGroupedDesigner(1)
    await createChart(user)

    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(kindButton('세로 막대')).toBeVisible()

    await user.click(chartToggle() as HTMLElement)

    expect(chartToggle()).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: '세로 막대' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 삭제' })).not.toBeInTheDocument()
    expect(screen.getByRole('img')).toBeVisible() // 그림은 설정 패널과 무관하게 남는다

    await user.click(chartToggle() as HTMLElement)

    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(kindButton('세로 막대')).toBeVisible()
  })

  it('keeps the chart, the open settings and the result tab after running again', async () => {
    const { user } = await openGroupedDesigner(1)
    await createChart(user)

    await rerun(user)

    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    expectTab('result')
    expect(await screen.findByRole('img')).toBeVisible()
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
  })

  it('removes the chart tile and its drawing for the table-only view', async () => {
    const { user } = await openGroupedDesigner(1)
    await createChart(user)

    await user.click(screen.getByRole('radio', { name: '표만' }))

    expect(screen.queryByRole('region', { name: '차트 타일' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('그룹핑 없는 결과 안내 (AC11)', () => {
  it('guides to grouping and disables creating a chart when the result has no group column', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    await openChartTab(user)

    expect(screen.getByText(NEEDS_GROUPING)).toBeVisible()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeDisabled()
  })

  it('tells that three or more group columns cannot make a chart', async () => {
    const { user } = await openDesigner()
    for (const label of ['Vendor', 'Status', 'Forecast']) {
      await addColumn(user, label)
      await user.click(chipButton(['Vendor', 'Status', 'Forecast'].indexOf(label)))
      await user.click(within(settingsOf(label)).getByRole('checkbox', { name: '그룹핑' }))
    }
    await addColumn(user, '금액')
    answerWith(
      resultOf({
        columns: [
          VENDOR_COL,
          STATUS_COL,
          resultColumn({ index: 2, field: 'deal.forecast', label: 'Forecast', type: 'code', valueType: 'text', format: null, group: true }),
          amountCol(3),
        ],
        rows: [['Silverfort', 'Won', '90', 1_000_000]],
      }),
    )
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    await openChartTab(user)

    expect(screen.getByText(TOO_MANY_GROUPS)).toBeVisible()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeDisabled()
  })
})

describe('차트 만들기와 종류 (AC12, AC13)', () => {
  it('starts a vertical bar chart for one group column from the first value', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    await createChart(user)

    expect(lastChart().type).toBe('bar')
    expect(chartLabels()).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(chartDatasets()).toHaveLength(1)
    expect(chartDatasets()[0]?.data).toEqual([3000, 1500, 500])
    expectPressed('세로 막대')
    expect(screen.getByRole('button', { name: '차트 삭제' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
  })

  it('fills the panel with the defaults: axis titles from the headers, no title, legend on top', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    await createChart(user)

    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('가로축 제목')).toHaveValue('Vendor')
    expect(panelField('세로축 제목')).toHaveValue(AMOUNT_HEADER)
    expect(panelField('차트 제목')).toHaveValue('')
    expect(panelField('범례')).toHaveDisplayValue('위')
    expect(within(valueGroup()).getByRole('checkbox', { name: AMOUNT_HEADER })).toBeChecked()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).not.toBeChecked()
  })

  it('starts a stacked bar chart for two group columns with the second one as series', async () => {
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)

    await createChart(user)

    expectPressed('누적 막대')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('계열')).toHaveDisplayValue('Status')
    expect(chartLabels()).toEqual(['Silverfort', 'Okta'])
    expect(chartDatasets().map((d) => d.label)).toEqual(['Won', 'Open'])
    expect(optionAt('scales', 'x', 'stacked')).toBe(true)
  })

  it('returns to no chart with the delete button', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    await user.click(screen.getByRole('button', { name: '차트 삭제' }))

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: '세로 막대' })).not.toBeInTheDocument()
  })

  it('has the ten kind buttons and marks only the chosen one pressed', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    for (const name of ALL_KINDS) expect(kindButton(name)).toHaveAttribute('aria-pressed', name === '세로 막대' ? 'true' : 'false')

    await user.click(kindButton('도넛'))

    expect(kindButton('도넛')).toHaveAttribute('aria-pressed', 'true')
    expect(kindButton('세로 막대')).toHaveAttribute('aria-pressed', 'false')
  })

  it.each([
    ['가로 막대', 'bar'],
    ['누적 막대', 'bar'],
    ['100% 누적', 'bar'],
    ['꺾은선', 'line'],
    ['영역', 'line'],
    ['원', 'pie'],
    ['도넛', 'doughnut'],
  ])('redraws the preview as %s right after the click', async (name, type) => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    await user.click(kindButton(name))

    expect(lastChart().type).toBe(type)
  })

  it('draws a horizontal bar chart with the index axis on y', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    await user.click(kindButton('가로 막대'))

    expect(optionAt('indexAxis')).toBe('y')
    expect(panelField('세로축 제목(범주)')).toHaveValue('Vendor')
    expect(panelField('가로축 제목(값)')).toHaveValue(AMOUNT_HEADER)
  })

  it('tidies the settings for a pie: no series, one value, no swap and a disabled series select', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))
    expect(chartDatasets()).toHaveLength(2)

    await user.click(kindButton('원'))

    expect(chartDatasets()).toHaveLength(1)
    expect(panelField('계열')).toBeDisabled()
    expect(panelField('행/열 전환')).toBeDisabled()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).not.toBeChecked()
  })

  it('disables the kinds that need exactly one group column when there are two', async () => {
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)

    for (const name of ['원', '도넛', '분산형', '콤보']) expect(kindButton(name)).toBeDisabled()
    for (const name of ['세로 막대', '가로 막대', '누적 막대', '100% 누적', '꺾은선', '영역']) expect(kindButton(name)).toBeEnabled()
  })
})

describe('설정이 차트 옵션에 바로 반영됨 (AC14)', () => {
  async function ready(groups: 1 | 2 = 1) {
    const rendered = await openGroupedDesigner(groups)
    await openChartTab(rendered.user)
    await createChart(rendered.user)
    return rendered
  }

  it('offers only group columns as category and series and only aggregate columns as values', async () => {
    await ready(2)

    const category = within(panelField('범주')).getAllByRole('option').map((o) => o.textContent)
    const series = within(panelField('계열')).getAllByRole('option').map((o) => o.textContent)

    expect(category).toEqual(expect.arrayContaining(['Vendor', 'Status']))
    expect(category).not.toContain(AMOUNT_HEADER)
    expect(series).toEqual(expect.arrayContaining(['Vendor', 'Status']))
    expect(series).not.toContain(USERS_HEADER)
    expect(within(valueGroup()).getAllByRole('checkbox')).toHaveLength(2)
    expect(within(valueGroup()).getByRole('checkbox', { name: AMOUNT_HEADER })).toBeVisible()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).toBeVisible()
    expect(within(valueGroup()).queryByRole('checkbox', { name: 'Vendor' })).not.toBeInTheDocument()
  })

  it('swaps category and series when the series column is chosen as category', async () => {
    const { user } = await ready(2)

    await user.selectOptions(panelField('범주'), 'Status')

    expect(panelField('범주')).toHaveDisplayValue('Status')
    expect(panelField('계열')).toHaveDisplayValue('Vendor')
    expect(chartLabels()).toEqual(['Won', 'Open'])
  })

  it('adds a dataset per checked value column named by its header', async () => {
    const { user } = await ready()

    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    expect(chartDatasets().map((d) => d.label)).toEqual([AMOUNT_HEADER, USERS_HEADER])
    expect(chartDatasets()[1]?.data).toEqual([30, 10, 5])
  })

  it('transposes categories and series with the swap checkbox', async () => {
    const { user } = await ready(2)

    await user.click(panelField('행/열 전환'))

    expect(chartLabels()).toEqual(['Won', 'Open'])
    expect(chartDatasets().map((d) => d.label)).toEqual(['Silverfort', 'Okta'])
  })

  it('sets the chart title', async () => {
    const { user } = await ready()

    await user.type(panelField('차트 제목'), 'Vendor별 금액')

    expect(optionAt('plugins', 'title')).toMatchObject({ display: true, text: 'Vendor별 금액' })
  })

  it.each([
    ['오른쪽', 'right'],
    ['아래', 'bottom'],
    ['위', 'top'],
  ])('moves the legend to %s', async (label, position) => {
    const { user } = await ready()
    await user.selectOptions(panelField('범례'), label === '위' ? '아래' : '위')

    await user.selectOptions(panelField('범례'), label)

    expect(optionAt('plugins', 'legend')).toMatchObject({ display: true, position })
  })

  it('hides the legend', async () => {
    const { user } = await ready()

    await user.selectOptions(panelField('범례'), '숨김')

    expect(optionAt('plugins', 'legend', 'display')).toBe(false)
  })

  it('switches the data labels on and passes the plugin to the chart instance', async () => {
    const { user } = await ready()
    expect(optionAt('plugins', 'datalabels', 'display')).toBe(false)

    await user.click(panelField('데이터 레이블'))

    expect(optionAt('plugins', 'datalabels', 'display')).toBe(true)
    expect(lastChart().plugins).toContainEqual(expect.objectContaining({ id: DATALABELS_MOCK_ID }))
  })

  it('changes the axis titles', async () => {
    const { user } = await ready()

    await user.clear(panelField('가로축 제목'))
    await user.type(panelField('세로축 제목'), '!')

    expect(optionAt('scales', 'x', 'title', 'display')).toBeFalsy()
    expect(optionAt('scales', 'y', 'title', 'text')).toBe(`${AMOUNT_HEADER}!`)
  })

  it('sets the minimum and maximum of the value axis and clears them back to automatic', async () => {
    const { user } = await ready()

    await user.type(panelField('세로축 최소'), '0')
    await user.type(panelField('세로축 최대'), '5000')

    expect(optionAt('scales', 'y', 'min')).toBe(0)
    expect(optionAt('scales', 'y', 'max')).toBe(5000)

    await user.clear(panelField('세로축 최대'))

    expect('max' in (optionAt('scales', 'y') as object)).toBe(false)
  })

  it('puts the line datasets of a combo chart on the secondary axis', async () => {
    const { user } = await ready()
    await user.click(kindButton('콤보'))
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    await user.click(panelField('보조 축'))

    expect(lastChart().type).toBe('bar')
    expect(chartDatasets()).toHaveLength(2)
    expect((chartDatasets()[1] as Record<string, unknown>).yAxisID).toBe('y1')
    expect(optionAt('scales', 'y1', 'position')).toBe('right')
  })

  it('disables the settings a kind does not use with a reason', async () => {
    const { user } = await ready()

    await user.click(kindButton('세로 막대'))

    expect(panelField('보조 축')).toBeDisabled()
    expect(panelField('보조 축')).toHaveAttribute('title', expect.stringMatching(/콤보/))
  })

  it('keeps the chart canvas accessible with a label that points to the table', async () => {
    await ready()

    expect(screen.getByRole('img')).toHaveAccessibleName(/같은 값이 결과 표에 있습니다/)
  })
})

describe('숫자 단위 (AC15)', () => {
  it('draws amounts in the unit of the column format', async () => {
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    await createChart(user)

    expect(chartDatasets()[0]?.data).toEqual([3000, 1500, 500])
  })
})

describe('컬럼 편집과 차트 (AC17)', () => {
  it('shows a hint when the category column is removed and keeps the other settings', async () => {
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)
    await user.type(panelField('차트 제목'), '유지할 제목')

    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Vendor 빼기' }))
    await openChartTab(user)

    expect(screen.getByText('범주 열을 고르세요')).toBeVisible()
    expect(panelField('차트 제목')).toHaveValue('유지할 제목')
  })

  it('moves to the result tab and opens the settings when saving an incomplete chart is rejected (AC8)', async () => {
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)
    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Vendor 빼기' }))
    answerWith(resultOf({ columns: [{ ...STATUS_COL, index: 0 }, amountCol(1), usersCol(2)], rows: [['Won', 1_000_000, 10]] }))
    await runQuery(user)
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await showTab(user, 'design') // 저장 전 탭을 작성 탭으로 두고, 위반 위치(차트)를 따라 결과 탭으로 옮겨지는지 본다

    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '차트 있는 새 리포트')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(resultTab()).toHaveAttribute('aria-selected', 'true'))
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(await within(tile('차트')).findByText(/범주 열은 그룹핑한 컬럼이어야 합니다/)).toBeVisible()
    expect(resultTab()).toHaveTextContent('결과 (고칠 곳 1)')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'create')).toHaveLength(1)
  })
})

describe('큰 결과 (AC20)', () => {
  const TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'
  const TRUNCATED = '최대 행 수 제한으로 표시된 행만 차트에 그렸습니다'

  /** Vendor 그룹 + 금액 + Users, 범주 n개. */
  const manyCategories = (n: number) =>
    resultOf({
      columns: [VENDOR_COL, amountCol(1), usersCol(2)],
      rows: Array.from({ length: n }, (_, i) => [`v${i}`, 1_000_000, 1]),
    })

  async function chartOf(result: ReturnType<typeof manyCategories>) {
    const { user } = await openGroupedDesigner(1)
    answerWith(result)
    await rerun(user)
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    await openChartTab(user)
    await user.click(await screen.findByRole('button', { name: '차트 만들기' }))
    return user
  }

  it('does not draw more than 1,000 points and tells to narrow the conditions', async () => {
    await chartOf(manyCategories(1001))

    expect(await screen.findByText(TOO_MANY)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('draws exactly 1,000 points', async () => {
    await chartOf(manyCategories(1000))

    expect(await screen.findByRole('img')).toBeVisible()
    expect(screen.queryByText(TOO_MANY)).not.toBeInTheDocument()
    expect(chartLabels()).toHaveLength(1000)
  })

  it('tells that only the rows shown under the row limit are drawn', async () => {
    await chartOf({ ...manyCategories(3), truncated: true, totalCount: 5000 })

    expect(await screen.findByRole('img')).toBeVisible()
    expect(screen.getByText(TRUNCATED)).toBeVisible()
  })

  it('does not show the truncated notice for a complete result', async () => {
    await chartOf(manyCategories(3))

    await screen.findByRole('img')
    expect(screen.queryByText(TRUNCATED)).not.toBeInTheDocument()
  })
})
