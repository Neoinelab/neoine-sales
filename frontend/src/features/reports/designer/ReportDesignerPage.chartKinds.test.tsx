import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { lastChart } from '../../../test/chartMock'
import {
  AMOUNT_HEADER,
  chartDatasets,
  chartLabels,
  chooseKind,
  createChart,
  expectPressed,
  familyRadio,
  openChartTab,
  openGroupedDesigner,
  optionAt,
  panelField,
  USERS_HEADER,
  valueGroup,
} from '../../../test/reportChart'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { addColumn, answerWith, openDesigner, runQuery, saveButton, saveDialog, setupReportClock, typeName } from '../../../test/reportScreen'

setupReportClock()

/** 그룹핑 없는 결과: 0 = Deal code(텍스트), 1 = Users count(숫자 필드, 집계 없음). 값 0..10. */
const UNGROUPED = resultOf({
  columns: [
    resultColumn({ index: 0, field: 'deal.code', label: 'Deal code', type: 'text', valueType: 'text', format: null }),
    resultColumn({ index: 1, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: null }),
  ],
  rows: Array.from({ length: 11 }, (_, i) => [`D-${i}`, i]),
})

async function openUngrouped() {
  const rendered = await openDesigner()
  answerWith(UNGROUPED)
  await addColumn(rendered.user, 'Deal code')
  await addColumn(rendered.user, 'Users count')
  await runQuery(rendered.user)
  await screen.findByRole('table', { name: '조회 결과' })
  await openChartTab(rendered.user)
  return rendered
}

describe('그룹핑 없는 리포트의 히스토그램 (Excel 확장 AC10)', () => {
  it('lets the chart be made as a histogram and says that only the histogram is possible without grouping', async () => {
    await openUngrouped()

    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.getByText('그룹핑이 없으면 히스토그램만 만들 수 있습니다')).toBeVisible()
  })

  it('starts a histogram of the number column with the bins as categories', async () => {
    const { user } = await openUngrouped()

    await createChart(user)

    expectPressed('히스토그램')
    expect(familyRadio('히스토그램')).toBeChecked()
    expect(lastChart().type).toBe('bar')
    expect((chartDatasets()[0]?.data as number[]).reduce((a, b) => a + b, 0)).toBe(11)
  })

  it('saves a histogram without grouping and returns it when opened again', async () => {
    const { user } = await openUngrouped()
    await createChart(user)

    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '히스토그램 리포트')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(async () => expect((await gateway.reports.list()).some((r) => r.name === '히스토그램 리포트')).toBe(true))
    const saved = (await gateway.reports.list()).find((r) => r.name === '히스토그램 리포트')
    expect(saved?.chartKind).toBe('histogram')
    expect((await gateway.reports.get(saved?.id ?? 0)).chart).toMatchObject({ kind: 'histogram', category: null })
  })

  it('disables the category field with the reason', async () => {
    const { user } = await openUngrouped()

    await createChart(user)

    expect(panelField('범주')).toBeDisabled()
    expect(screen.getByText('이 차트는 범주 열을 쓰지 않습니다')).toBeVisible()
  })

  it('redraws with the bins of the chosen count', async () => {
    const { user } = await openUngrouped()
    await createChart(user)

    await user.selectOptions(panelField('구간 방식'), '구간 수')
    await user.type(panelField('구간 수'), '5')

    expect(chartLabels()).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(chartDatasets()[0]?.data).toEqual([3, 2, 2, 2, 2])
  })

  it('shows the count and width fields disabled in the automatic mode', async () => {
    const { user } = await openUngrouped()
    await createChart(user)

    expect(panelField('구간 방식')).toHaveDisplayValue('자동')
    expect(panelField('구간 수')).toBeDisabled()
    expect(panelField('구간 너비')).toBeDisabled()
  })

  it('shows the issue of an invalid bin count next to the field', async () => {
    const { user } = await openUngrouped()
    await createChart(user)

    await user.selectOptions(panelField('구간 방식'), '구간 수')
    await user.type(panelField('구간 수'), '0')

    expect(screen.getByText('구간 수는 1~100의 정수입니다')).toBeVisible()
    expect(panelField('구간 수')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('종류별 옵션 (Excel 확장 AC12, AC14)', () => {
  async function ready(groups: 1 | 2 = 1) {
    const rendered = await openGroupedDesigner(groups)
    await openChartTab(rendered.user)
    await createChart(rendered.user)
    return rendered
  }

  it('shows the total option only for the waterfall and draws the total bar when it is on', async () => {
    const { user } = await ready()
    await chooseKind(user, '폭포')
    expect(chartDatasets().map((d) => d.label)).toEqual(['증가', '감소'])

    await user.click(screen.getByRole('checkbox', { name: '마지막에 합계 막대' }))

    expect(chartDatasets().map((d) => d.label)).toEqual(['증가', '감소', '합계'])
    expect(chartLabels()).toEqual(['Silverfort', 'Okta', '(없음)', '합계'])
  })

  it('has no total option for other kinds', async () => {
    await ready()

    expect(screen.queryByRole('checkbox', { name: '마지막에 합계 막대' })).not.toBeInTheDocument()
  })

  it('fills the series table of a combo chart with the first preset and applies another preset', async () => {
    const { user } = await ready()
    await chooseKind(user, '콤보')
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    expect(panelField('콤보 프리셋')).toHaveDisplayValue('묶은 세로 막대 - 꺾은선')

    await user.selectOptions(panelField('콤보 프리셋'), '묶은 세로 막대 - 보조 축의 꺾은선')

    expect((chartDatasets()[1] as Record<string, unknown>).yAxisID).toBe('y1')
    expect(optionAt('scales', 'y1', 'position')).toBe('right')
  })

  it('refuses a combo chart with every series on the secondary axis with the server message', async () => {
    const { user } = await ready()
    await chooseKind(user, '콤보')
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    await user.click(screen.getByRole('checkbox', { name: `${AMOUNT_HEADER} 보조 축` }))
    await user.click(screen.getByRole('checkbox', { name: `${USERS_HEADER} 보조 축` }))

    expect(screen.getByText('모든 계열을 보조 축에 둘 수 없습니다')).toBeVisible()
  })
})
