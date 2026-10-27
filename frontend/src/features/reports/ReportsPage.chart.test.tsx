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
    expect(cellOf(WITH_CHART.name)).toBe('세로 막대')
    expect(cellOf(stacked.name)).toBe('누적 막대')
    expect(cellOf('Vendor별 파이프라인')).toBe('—')
  })

  it.each([
    ['bar', '세로 막대'],
    ['horizontal_bar', '가로 막대'],
    ['stacked_bar', '누적 막대'],
    ['stacked_100_bar', '100% 누적'],
    ['line', '꺾은선'],
    ['area', '영역'],
    ['pie', '원'],
    ['doughnut', '도넛'],
    ['scatter', '분산형'],
    ['combo', '콤보'],
  ] as const)('names the kind %s as %s', async (kind, label) => {
    const one = savedReport({ id: 22, name: '종류 확인', chart: { ...VENDOR_CHART, kind } })
    await openList({ savedReports: [one] })

    const column = screen.getAllByRole('columnheader').map((h) => h.textContent).indexOf('차트')

    expect(within(rowOf('종류 확인')).getAllByRole('cell')[column]).toHaveTextContent(label)
  })
})
