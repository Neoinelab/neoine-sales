import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { groupedAmountResult, resultColumn, resultOf } from '../../../test/reportDesigner'
import {
  addColumn,
  addCondition,
  chipButton,
  chipTexts,
  lastQuery,
  openAndRun,
  openDesigner,
  resultTable,
  runButton,
  runQuery,
  settingsOf,
  tableTexts,
  setupReportClock,
} from '../../../test/reportScreen'

setupReportClock()

describe('앞 N자 입력 검사 (AC15)', () => {
  it('makes no request and tells the user to fix N when it is empty', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))
    await user.clear(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N'))

    await runQuery(user)

    expect(mockControl.reportQueries()).toEqual([])
    expect(within(settingsOf('Deal 이름')).getByText('1~200 사이 정수를 입력하세요')).toBeVisible()
    expect(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')).toBeInvalid()
  })

  it('sends the prefix length without any format key once N is valid', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))

    await runQuery(user)

    expect(mockControl.reportQueries()).toEqual([
      { columns: [{ field: 'deal.name', prefixLength: 20, group: false }], conditions: [], combine: 'and', rowLimit: 1000 },
    ])
  })
})

describe('조회 요청 (AC11)', () => {
  it('sends the designed request and shows the result table', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    await addCondition(user, 'Vendor')
    await user.click(screen.getByRole('button', { name: /^조건 1 값/ }))
    await user.click(within(screen.getByRole('group', { name: '조건 1 값' })).getByRole('checkbox', { name: 'Silverfort' }))
    await user.click(chipButton(1))
    await user.selectOptions(within(settingsOf('금액')).getByRole('combobox', { name: '정렬' }), 'desc')

    await runQuery(user)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toEqual([
      {
        columns: [
          { field: 'deal.vendor', group: true },
          { field: 'deal.amount', group: false, aggregate: 'sum', sort: 'desc' },
        ],
        conditions: [{ field: 'deal.vendor', operator: 'in', value: [seedVendorId('Silverfort')] }],
        combine: 'and',
        rowLimit: 1000,
      },
    ])
    expect(tableTexts()).toEqual([
      ['Vendor 1', '1'],
      ['Vendor 2', '2'],
      ['Vendor 3', '3'],
    ])
  })

  it('offers the sort in the column settings with no sort first and leaves it out of the run bar', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    const select = within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' })

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['정렬 없음', '오름차순', '내림차순'])
    expect(select).toHaveDisplayValue('정렬 없음')
    expect(screen.getAllByRole('combobox', { name: '정렬' })).toHaveLength(1)
    expect(screen.queryByRole('combobox', { name: '정렬 방향' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '최대 행' })).toBeVisible()
    expect(runButton()).toBeVisible()
    await user.selectOptions(select, 'desc')
    expect(chipTexts()[0]).toContain('▼ 내림')
    expect(chipTexts()[0]).not.toMatch(/내림 \d/)
  })

  it('shows a badge only on the sorted chip and numbers the badges when two columns are sorted', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await addColumn(user, 'Solution')
    await user.selectOptions(within(settingsOf('Solution')).getByRole('combobox', { name: '정렬' }), 'asc')
    expect(chipTexts()[2]).toContain('▲ 오름')
    expect(chipTexts()[2]).not.toMatch(/오름 \d/)

    await user.click(chipButton(0))
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'desc')

    expect(chipTexts()[0]).toContain('▼ 내림 1')
    expect(chipTexts()[1]).not.toMatch(/[▲▼]/)
    expect(chipTexts()[2]).toContain('▲ 오름 2')
  })

  it('sends the column sorts in column order', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'asc')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'desc')

    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    expect(mockControl.reportQueries()).toEqual([
      {
        columns: [
          { field: 'deal.code', group: false, sort: 'asc' },
          { field: 'deal.name', group: false, sort: 'desc' },
        ],
        conditions: [],
        combine: 'and',
        rowLimit: 1000,
      },
    ])
  })

  it('removes the sort and its badge together with the sorted column', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'asc')

    await user.click(screen.getByRole('button', { name: 'Deal 이름 빼기' }))
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    expect(chipTexts()[0]).not.toMatch(/[▲▼]/)
    expect(lastQuery().columns).toEqual([{ field: 'deal.code', group: false }])
  })

  it('offers the row limits with 1,000 as the default and sends the chosen one', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    const select = screen.getByRole('combobox', { name: '최대 행' })

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['100', '1,000', '10,000'])
    expect(select).toHaveDisplayValue('1,000')

    await user.selectOptions(select, '100')
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    expect(mockControl.reportQueries()[0]?.rowLimit).toBe(100)
  })

  it('does not send a request when an input cannot be read', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Users')
    const input = screen.getByRole('textbox', { name: '조건 1 값' })
    await user.type(input, '1.5')

    await runQuery(user)

    expect(mockControl.reportQueries()).toHaveLength(0)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription(/정수로 입력하세요/)

    await user.clear(input)
    await user.type(input, '15')
    await runQuery(user)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(1)
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).not.toHaveAttribute('aria-invalid', 'true')
  })

  it('names the thousand won unit and the empty list in the input messages', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, '금액')
    await addCondition(user, 'Vendor')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), 'abc')

    await runQuery(user)

    expect(screen.getByText('천원 단위 정수로 입력하세요')).toBeVisible()
    expect(screen.getByText('하나 이상 선택하세요')).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(0)
  })

  it('shows the running state and blocks a second run', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    let release: (result: ReportResult) => void = () => undefined
    mockControl.setReportQueryHandler(() => new Promise<ReportResult>((resolve) => (release = resolve)))

    await runQuery(user)

    const running = await screen.findByRole('button', { name: '조회 중…' })
    expect(running).toBeDisabled()

    release(resultOf())

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(runButton()).toBeEnabled()
  })
})

describe('결과 표 (AC12)', () => {
  it('shows the total rows and the elapsed time', async () => {
    await openAndRun(resultOf({ rows: [['A'], ['B'], ['C']], elapsedMs: 210 }), 'Deal code')

    expect(screen.getByText(/총 3행 · 조회 0\.21초/)).toBeVisible()
  })

  it('formats amounts in thousand won with a unit in the header and aligns numbers to the right', async () => {
    await openAndRun(groupedAmountResult([['Silverfort', 1_234_500], ['Okta', 999_999], ['Zscaler', null]], null), 'Vendor')

    expect(within(resultTable()).getByRole('columnheader', { name: /^금액 합계\s?\(천원\)$/ })).toBeVisible()
    expect(within(resultTable()).getByRole('columnheader', { name: 'Vendor' })).toBeVisible()
    expect(tableTexts()).toEqual([
      ['Silverfort', '1,235'],
      ['Okta', '1,000'],
      ['Zscaler', '—'],
    ])
    const [firstRow] = within(resultTable()).getAllByRole('row').slice(1)
    const cells = within(firstRow as HTMLElement).getAllByRole('cell')
    expect(cells[1]).toHaveClass('report-num')
    expect(cells[0]).not.toHaveClass('report-num')
    expect(within(resultTable()).getByRole('columnheader', { name: /금액 합계/ })).toHaveClass('report-num')
  })

  it('shows dates and times with the server offset and the app clock', async () => {
    await openAndRun(
      resultOf({
        today: '2026-10-15',
        columns: [
          resultColumn({ index: 0, field: 'deal.created_at', label: '등록', type: 'datetime', valueType: 'datetime', format: 'ymd_hm' }),
          resultColumn({ index: 1, field: 'deal.expected_close', label: '마감', type: 'date', valueType: 'date', format: 'relative' }),
        ],
        rows: [['2026-04-01T00:30:00+09:00', '2026-10-24']],
      }),
      'Deal code',
    )

    expect(tableTexts()).toEqual([['2026-04-01 00:30', '3일 전']])
  })

  it('toggles the totals row only for grouped results and shows amounts in thousand won (AC-6)', async () => {
    const result = groupedAmountResult(
      [
        ['A', 1_000_000],
        ['B', 3_000_000],
      ],
      [null, 4_000_000],
    )
    const { user } = await openAndRun(result, 'Vendor')

    expect(tableTexts()).toEqual([
      ['A', '1,000'],
      ['B', '3,000'],
    ])
    const toggle = screen.getByRole('checkbox', { name: '합계 행' })
    expect(toggle).not.toBeChecked()

    await user.click(toggle)

    expect(tableTexts()).toEqual([
      ['A', '1,000'],
      ['B', '3,000'],
      ['합계', '4,000'],
    ])
    expect(within(resultTable()).getAllByRole('row').at(-1)?.closest('tfoot')).not.toBeNull()

    await user.click(toggle)

    expect(tableTexts()).toHaveLength(2)
  })

  it('shows the thousand won unit in the header of an amount column only', async () => {
    await openAndRun(groupedAmountResult([['A', 1_000_000]], [null, 1_000_000]), 'Vendor')

    const headers = within(resultTable()).getAllByRole('columnheader').map((h) => h.textContent)

    expect(headers[0]).toContain('Vendor')
    expect(headers[1]).toMatch(/금액 합계\s?\(천원\)/)
  })

  it('rounds an amount total to thousand won and keeps no share or decimal formats', async () => {
    const result = groupedAmountResult([['A', 123_456_789]], [null, 123_456_789])
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    expect(tableTexts()).toEqual([
      ['A', '123,457'],
      ['합계', '123,457'],
    ])
  })

  it('has no totals checkbox when the result has no totals', async () => {
    await openAndRun(resultOf({ rows: [['A']], totals: null }), 'Deal code')

    expect(screen.queryByRole('checkbox', { name: '합계 행' })).not.toBeInTheDocument()
  })

  it('warns that group values may add up to more than the totals row when Deal numbers are counted once', async () => {
    const { user } = await openAndRun(
      { ...groupedAmountResult([['A', 1000]], [null, 1000]), rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true },
      'Vendor',
    )
    expect(screen.queryByText(/그룹 값의 합이 합계 행보다 클 수 있습니다/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    expect(screen.getByText(/한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다/)).toBeVisible()
  })

  it('cuts data cells to the prefix length, keeps the whole value in the title and never cuts the totals row', async () => {
    const result = resultOf({
      columns: [
        resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', group: true, prefixLength: 3 }),
        resultColumn({ index: 1, field: 'deal.users', label: 'Users 합계', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum', prefixLength: 3 }),
      ],
      rows: [['ABCDEF', 1_234_567]],
      totals: [null, 1_234_567],
    })
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    const [dataRow, totalRow] = within(resultTable()).getAllByRole('row').slice(1) as [HTMLElement, HTMLElement]
    const [textCell, numberCell] = within(dataRow).getAllByRole('cell')

    expect(tableTexts()).toEqual([
      ['ABC…', '1,2…'],
      ['합계', '1,234,567'],
    ])
    expect(textCell).toHaveAttribute('title', 'ABCDEF')
    expect(numberCell).toHaveAttribute('title', '1,234,567')
    expect(within(totalRow).getAllByRole('cell')[1]).toHaveTextContent('1,234,567')
  })

  it('does not cut an empty dash or a value of exactly N characters', async () => {
    const result = resultOf({
      columns: [resultColumn({ index: 0, label: 'Deal code', prefixLength: 3 })],
      rows: [['ABC'], [null]],
    })
    await openAndRun(result, 'Deal code')

    expect(tableTexts()).toEqual([['ABC'], ['—']])
  })

  it('shows truncation and pages over 100 rows', async () => {
    const rows = Array.from({ length: 1000 }, (_, i) => [`행 ${i + 1}`])
    const { user } = await openAndRun(resultOf({ rows, totalCount: 12_345, truncated: true, rowLimit: 1000 }), 'Deal code')

    expect(screen.getByText(/총 12,345행 중 1,000행 표시\(최대 행 수 제한\)/)).toBeVisible()
    expect(tableTexts()).toHaveLength(100)
    expect(tableTexts()[0]).toEqual(['행 1'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('1 페이지')

    await user.click(screen.getByRole('button', { name: '다음' }))

    expect(tableTexts()).toHaveLength(100)
    expect(tableTexts()[0]).toEqual(['행 101'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('2 페이지')
  })

  it('shows no pager for 100 rows or fewer', async () => {
    await openAndRun(resultOf({ rows: Array.from({ length: 100 }, (_, i) => [`행 ${i + 1}`]), totalCount: 100 }), 'Deal code')

    expect(tableTexts()).toHaveLength(100)
    expect(screen.queryByRole('navigation', { name: '페이지' })).not.toBeInTheDocument()
    expect(screen.queryByText(/최대 행 수 제한/)).not.toBeInTheDocument()
  })

  it('scrolls the table sideways inside its own container', async () => {
    await openAndRun(null, 'Deal code')

    expect(resultTable().parentElement).toHaveClass('report-scroll')
  })
})

describe('다시 조회 (리뷰 후속)', () => {
  const rowsOf = (n: number, prefix: string) => Array.from({ length: n }, (_, i) => [`${prefix} ${i + 1}`])

  it('shows the first page again when a new result has fewer rows than the page we were on', async () => {
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300, '행'), totalCount: 300 }), 'Deal code')
    await user.click(screen.getByRole('button', { name: '다음' }))
    await user.click(screen.getByRole('button', { name: '다음' }))
    expect(tableTexts()[0]).toEqual(['행 201'])

    mockControl.setReportQueryHandler(() => resultOf({ rows: rowsOf(3, '새'), totalCount: 3 }))
    await runQuery(user)

    await screen.findByText('새 1')
    expect(tableTexts()).toEqual([['새 1'], ['새 2'], ['새 3']])
    expect(screen.queryByRole('navigation', { name: '페이지' })).not.toBeInTheDocument()
  })

  it('starts at the first page again even when the new result is long too', async () => {
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300, '행'), totalCount: 300 }), 'Deal code')
    await user.click(screen.getByRole('button', { name: '다음' }))

    mockControl.setReportQueryHandler(() => resultOf({ rows: rowsOf(250, '새'), totalCount: 250 }))
    await runQuery(user)

    await screen.findByText('새 1')
    expect(tableTexts()[0]).toEqual(['새 1'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('1 페이지')
  })

  it('turns the totals row off when a new result arrives', async () => {
    const grouped = groupedAmountResult([['A', 1000]], [null, 1000])
    const { user } = await openAndRun(grouped, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))
    expect(tableTexts()).toHaveLength(2)

    mockControl.setReportQueryHandler(() => groupedAmountResult([['B', 2000]], [null, 2000]))
    await runQuery(user)

    await screen.findByText('B')
    expect(screen.getByRole('checkbox', { name: '합계 행' })).not.toBeChecked()
    expect(tableTexts()).toHaveLength(1)
  })
})

describe('설계 변경 안내 (AC15)', () => {
  it('marks the result as outdated after a change and clears the note on the next run', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()

    await addColumn(user, 'Deal 이름')

    expect(screen.getByText("설계가 바뀌었습니다. '조회'를 눌러 다시 조회하세요")).toBeVisible()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()

    await runQuery(user)

    await screen.findByRole('columnheader', { name: 'Deal 이름' })
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })

  it('marks the result as outdated when a column sort is changed after a run', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'desc')

    expect(screen.getByText("설계가 바뀌었습니다. '조회'를 눌러 다시 조회하세요")).toBeVisible()

    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'asc')
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })

  it('shows no outdated note before the first run', async () => {
    const { user } = await openDesigner()

    await addColumn(user, 'Deal code')

    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })
})
