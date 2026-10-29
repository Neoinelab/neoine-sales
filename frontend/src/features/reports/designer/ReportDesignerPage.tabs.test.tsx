import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../../shared/api/problem'
import type { ReportIssue } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { invalidReport, REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import { groupedAmountResult, resultOf } from '../../../test/reportDesigner'
import {
  chooseView,
  designTab,
  dragTile,
  expectTab,
  NO_RESULT_NOTE,
  panelOf,
  queryTile,
  resultTab,
  showTab,
  STALE_NOTE,
  tile,
  tileOrder,
  viewGroup,
} from '../../../test/reportLayout'
import {
  addColumn,
  addCondition,
  chipItems,
  openAndRun,
  openDesigner,
  rerun,
  runQuery,
  setupReportClock,
  tableTexts,
} from '../../../test/reportScreen'

setupReportClock()

const failWith = (...issues: ReportIssue[]): void =>
  mockControl.setReportQueryHandler(() => {
    throw invalidReport(issues)
  })
const issue = (location: (string | number)[], message: string): ReportIssue => ({ location, code: 'x', message })
const runBar = (): HTMLElement => screen.getByRole('region', { name: '최대 행과 조회' })

describe('작성 탭과 결과 탭 (AC1)', () => {
  it('has the design and result tabs in a tablist named after the designer and opens on the design tab', async () => {
    await openDesigner()

    const tablist = screen.getByRole('tablist', { name: '리포트 디자이너' })
    expect(within(tablist).getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
    expectTab('design')
    expect(screen.getByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
  })

  it('puts the field list, scope, columns, conditions, row limit and run button on the design tab', async () => {
    await openDesigner()
    const design = within(panelOf('design'))

    expect(design.getByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
    expect(design.getByRole('combobox', { name: '최대 행' })).toBeVisible()
    expect(design.getByRole('button', { name: '조회' })).toBeVisible()
    expect(design.getByRole('region', { name: '최대 행과 조회' })).toBeVisible()
    expect(design.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()
    expect(design.queryByRole('radiogroup', { name: '보기', hidden: true })).not.toBeInTheDocument()
  })

  it('puts the view choice, the tiles and the SQL viewer on the result tab', async () => {
    const { user } = await openDesigner()
    await showTab(user, 'result')
    const result = within(panelOf('result'))

    expect(result.getByRole('radiogroup', { name: '보기' })).toBeVisible()
    expect(result.getByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).toBeVisible()
    expect(result.queryByRole('button', { name: '조회', hidden: true })).not.toBeInTheDocument()
  })

  it('keeps the inactive panel in the DOM, hidden', async () => {
    await openDesigner()

    const result = panelOf('result')

    expect(result).toHaveAttribute('hidden')
    expect(within(result).getByRole('radiogroup', { name: '보기', hidden: true })).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: '보기' })).not.toBeInTheDocument() // 접근성 트리에서는 빠진다
  })

  it('switches the panels with the tab buttons', async () => {
    const { user } = await openDesigner()

    await user.click(resultTab())
    expectTab('result')
    expect(screen.queryByRole('button', { name: '조회' })).not.toBeInTheDocument()

    await user.click(designTab())
    expectTab('design')
    expect(screen.getByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
  })

  it('keeps the design when going to the result tab and back', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')

    await showTab(user, 'result')
    await showTab(user, 'design')

    expect(chipItems()).toHaveLength(1)
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toBeVisible()
  })
})

describe('조회 성공 (AC2)', () => {
  it('moves to the result tab and shows the result table and the chart tile', async () => {
    await openAndRun(resultOf({ rows: [['A'], ['B']] }), 'Deal code')

    expectTab('result')
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(tableTexts()).toEqual([['A'], ['B']])
    expect(screen.queryByRole('button', { name: '조회' })).not.toBeInTheDocument()
  })

  it('moves to the result tab again after a second run', async () => {
    const { user } = await openAndRun(resultOf({ rows: [['A']] }), 'Deal code')
    await showTab(user, 'design')

    mockControl.setReportQueryHandler(() => resultOf({ rows: [['새']] }))
    await runQuery(user)

    expect(await screen.findByText('새')).toBeVisible()
    expectTab('result')
  })

  it('shows the table only when the view is table only', async () => {
    const { user } = await openAndRun(resultOf({ rows: [['A']] }), 'Deal code')

    await chooseView(user, '표만')
    await showTab(user, 'design')
    mockControl.setReportQueryHandler(() => resultOf({ rows: [['B']] }))
    await runQuery(user)

    expect(await screen.findByText('B')).toBeVisible()
    expect(queryTile('차트')).toBeNull()
  })
})

describe('조회 실패 (AC3)', () => {
  it('stays on the design tab with the violations right below the run bar', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, '금액')
    failWith(issue(['columns', 0], '첫 컬럼 문구'), issue(['columns', 1, 'aggregate'], '집계 문구'))

    await runQuery(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('고칠 곳 2개')
    expect(alert).toHaveTextContent('컬럼 1(Deal code)')
    expect(alert).toHaveTextContent('집계 문구')
    expectTab('design')
    expect(panelOf('design')).toContainElement(alert)
    expect(runBar().compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })

  it('stays on the design tab for a timeout, with the server message below the run bar', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    await runQuery(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')
    expect(runBar().compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('stays on the design tab for another server error', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })

    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 내부 오류입니다')
    expectTab('design')
  })

  it('stays on the design tab when the input cannot be read and sends nothing', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Users count')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '1.5')

    await runQuery(user)

    expect(mockControl.reportQueries()).toHaveLength(0)
    expectTab('design')
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveAttribute('aria-invalid', 'true')
  })

  it('keeps the previous result on the result tab after a failed run', async () => {
    const { user } = await openAndRun(resultOf({ rows: [['이전 결과']] }), 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    await rerun(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')
    await showTab(user, 'result')
    expect(tableTexts()).toEqual([['이전 결과']])
  })
})

describe('결과가 아직 없을 때 (AC4)', () => {
  it('tells to run from the design tab in the table tile and still lets the user change the view and the layout', async () => {
    const { user } = await openDesigner()

    await showTab(user, 'result')

    expect(within(tile('표')).getByText(NO_RESULT_NOTE)).toBeVisible()
    expect(viewGroup()).toBeVisible()

    dragTile('표', '차트', 'right')
    expect(tileOrder()).toEqual(['차트', '표'])

    await chooseView(user, '차트만')
    expect(queryTile('표')).toBeNull()
    expect(tile('차트')).toBeVisible()
  })

  it('lets the user choose table only without a result', async () => {
    const { user } = await openDesigner()
    await showTab(user, 'result')

    await chooseView(user, '표만')

    expect(queryTile('차트')).toBeNull()
    expect(within(tile('표')).getByText(NO_RESULT_NOTE)).toBeVisible()
  })
})

describe('설계 변경 안내 (AC5)', () => {
  it('is not raised by a view or layout change', async () => {
    const { user } = await openAndRun(null, 'Deal code')

    await chooseView(user, '표만')
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'right')

    expect(screen.queryByText(STALE_NOTE)).not.toBeInTheDocument()
  })

  it('is raised by a change of the row limit after a run', async () => {
    const { user } = await openAndRun(null, 'Deal code')
    await showTab(user, 'design')

    await user.selectOptions(screen.getByRole('combobox', { name: '최대 행' }), '100')
    await showTab(user, 'result')

    expect(screen.getByText(STALE_NOTE)).toBeVisible()
  })
})

describe('탭 이름의 고칠 곳 수 (AC6)', () => {
  it('adds the number of violations to the design tab name and removes it as they are fixed', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 0], '코드 컬럼 문구'), issue(['columns', 1, 'label'], '이름 컬럼 문구'))

    await runQuery(user)

    expect(await screen.findByRole('tab', { name: '작성 (고칠 곳 2)' })).toBeVisible()
    expect(resultTab()).toHaveTextContent(/^결과$/)

    await user.type(within(screen.getByRole('region', { name: '컬럼 설정: Deal 이름' })).getByRole('textbox', { name: '표시 이름' }), '이름')

    expect(screen.getByRole('tab', { name: '작성 (고칠 곳 1)' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    expect(designTab()).toHaveTextContent(/^작성$/)
  })

  it('has no number on either tab without violations', async () => {
    await openAndRun(null, 'Deal code')

    expect(designTab()).toHaveTextContent(/^작성$/)
    expect(resultTab()).toHaveTextContent(/^결과$/)
  })
})

describe('탭을 옮겨도 결과 화면 상태가 남는다 (AC1)', () => {
  const rowsOf = (n: number) => Array.from({ length: n }, (_, i) => [`행 ${i + 1}`])

  it('keeps the table page', async () => {
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300), totalCount: 300 }), 'Deal code')
    await user.click(screen.getByRole('button', { name: '다음' }))
    expect(tableTexts()[0]).toEqual(['행 101'])

    await showTab(user, 'design')
    await showTab(user, 'result')

    expect(tableTexts()[0]).toEqual(['행 101'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('2 페이지')
  })

  it('keeps the totals row choice', async () => {
    const result = groupedAmountResult([['A', 1_000_000]], [null, 1_000_000])
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    await showTab(user, 'design')
    await showTab(user, 'result')

    expect(screen.getByRole('checkbox', { name: '합계 행' })).toBeChecked()
    expect(tableTexts().at(-1)?.[0]).toBe('합계')
  })

  it('keeps the chosen view and layout while switching tabs', async () => {
    const { user } = await openAndRun(null, 'Deal code')
    dragTile('표', '차트', 'right')
    await chooseView(user, '표+차트')

    await showTab(user, 'design')
    await showTab(user, 'result')

    expect(tileOrder()).toEqual(['차트', '표'])
  })
})
