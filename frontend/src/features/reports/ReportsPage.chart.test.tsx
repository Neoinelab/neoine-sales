import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { openList, setupReportClock } from '../../test/reportScreen'
import { SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../test/savedReports'

setupReportClock()

const rowOf = (name: string): HTMLElement => {
  const row = screen.getByRole('link', { name }).closest('tr')
  if (!row) throw new Error(`행 없음: ${name}`)
  return row
}

describe('Reports 목록의 차트 열 (AC8)', () => {
  it('puts the chart column between data and owner', async () => {
    await openList()

    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers.indexOf('차트')).toBeGreaterThan(-1)
    expect(headers.indexOf('차트')).toBe(headers.indexOf('데이터') + 1)
    expect(headers.indexOf('만든 사람')).toBe(headers.indexOf('차트') + 1)
  })

  it('shows the kind name for a report with a chart and a dash for the others', async () => {
    const stacked = savedReport({ id: 22, name: '누적 차트 리포트', chart: { ...VENDOR_CHART, kind: 'stacked_bar' } })
    await openList({ savedReports: [...SAVED_SAMPLES, WITH_CHART, stacked] })

    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    const column = headers.indexOf('차트')
    const cellOf = (name: string) => within(rowOf(name)).getAllByRole('cell')[column]?.textContent
    expect(cellOf(WITH_CHART.name)).toBe('묶은 세로 막대')
    expect(cellOf(stacked.name)).toBe('누적 세로 막대')
    expect(cellOf('Vendor별 파이프라인')).toBe('—')
  })

  it.each([
    ['bar', '묶은 세로 막대'],
    ['horizontal_bar', '묶은 가로 막대'],
    ['stacked_bar', '누적 세로 막대'],
    ['stacked_100_bar', '100% 누적 세로 막대'],
    ['line', '꺾은선'],
    ['area', '영역'],
    ['pie', '원형'],
    ['doughnut', '도넛형'],
    ['scatter', '분산형(표식만)'],
    ['combo', '콤보'],
    ['stacked_horizontal_bar', '누적 가로 막대'],
    ['stacked_100_horizontal_bar', '100% 누적 가로 막대'],
    ['line_markers', '표식이 있는 꺾은선'],
    ['stacked_line', '누적 꺾은선'],
    ['stacked_line_markers', '표식이 있는 누적 꺾은선'],
    ['stacked_100_line', '100% 누적 꺾은선'],
    ['stacked_100_line_markers', '표식이 있는 100% 누적 꺾은선'],
    ['stacked_area', '누적 영역'],
    ['stacked_100_area', '100% 누적 영역'],
    ['scatter_smooth_markers', '곡선 및 표식이 있는 분산형'],
    ['scatter_smooth', '곡선이 있는 분산형'],
    ['scatter_line_markers', '직선 및 표식이 있는 분산형'],
    ['scatter_line', '직선이 있는 분산형'],
    ['bubble', '거품형'],
    ['radar', '방사형'],
    ['radar_markers', '표식이 있는 방사형'],
    ['radar_filled', '채워진 방사형'],
    ['treemap', '트리맵'],
    ['sunburst', '선버스트'],
    ['histogram', '히스토그램'],
    ['pareto', '파레토'],
    ['waterfall', '폭포'],
    ['funnel', '깔때기'],
  ] as const)('names the kind %s as %s', async (kind, label) => {
    const one = savedReport({ id: 22, name: '종류 확인', chart: { ...VENDOR_CHART, kind } })
    await openList({ savedReports: [one] })

    const column = screen.getAllByRole('columnheader').map((h) => h.textContent).indexOf('차트')

    expect(within(rowOf('종류 확인')).getAllByRole('cell')[column]).toHaveTextContent(label)
  })
})
