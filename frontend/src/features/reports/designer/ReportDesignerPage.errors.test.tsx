import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../../shared/api/problem'
import type { ReportIssue } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { invalidReport, REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import {
  addColumn,
  addCondition,
  chipButton,
  chipItems,
  lastQuery,
  openDesigner,
  runQuery,
  settingsOf,
  setupReportClock,
} from '../../../test/reportScreen'

setupReportClock()

const failWith = (...issues: ReportIssue[]): void =>
  mockControl.setReportQueryHandler(() => {
    throw invalidReport(issues)
  })

const issue = (location: (string | number)[], message: string, code = 'x'): ReportIssue => ({ location, code, message })

describe('정의 위반 표시 (AC13)', () => {
  it('shows invalid report issues next to the chip, setting, condition, combine and row limit', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, '금액(원)')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')
    failWith(
      issue(['columns', 0], '첫 컬럼 문구'),
      issue(['columns', 1, 'aggregate'], '집계 문구'),
      issue(['conditions', 0, 'value'], '조건 값 문구'),
      issue(['combine'], '결합 문구'),
      issue(['row_limit'], '최대 행 문구'),
    )

    await runQuery(user)

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 5개')
    expect(summary).toHaveTextContent('컬럼 1(Deal code)')
    expect(summary).toHaveTextContent('컬럼 2(금액(원))')
    expect(summary).toHaveTextContent('조건 1(Deal 이름)')
    expect(summary).toHaveTextContent('조건 결합')
    expect(summary).toHaveTextContent('최대 행')
    for (const message of ['첫 컬럼 문구', '집계 문구', '조건 값 문구', '결합 문구', '최대 행 문구']) {
      expect(summary).toHaveTextContent(message)
    }
    expect(chipItems()[0]).toHaveClass('is-invalid')
    expect(chipButton(0)).toHaveAccessibleDescription(/첫 컬럼 문구/)
    expect(chipItems()[1]).toHaveClass('is-invalid')
    const aggregate = within(settingsOf('금액(원)')).getByRole('combobox', { name: '집계' })
    expect(aggregate).toHaveAttribute('aria-invalid', 'true')
    expect(aggregate).toHaveAccessibleDescription(/집계 문구/)
    const value = screen.getByRole('textbox', { name: '조건 1 값' })
    expect(value).toHaveAttribute('aria-invalid', 'true')
    expect(value).toHaveAccessibleDescription(/조건 값 문구/)
    expect(screen.getByRole('group', { name: '조건 결합' })).toHaveAccessibleDescription(/결합 문구/)
    expect(screen.getByRole('combobox', { name: '최대 행' })).toHaveAccessibleDescription(/최대 행 문구/)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
  })

  it('shows a column sort issue at the sort select of that column and clears it when the sort is changed', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'desc')
    failWith(issue(['columns', 1, 'sort'], '정렬 문구', 'sort-invalid'))

    await runQuery(user)

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('컬럼 2(Deal 이름)')
    expect(summary).toHaveTextContent('정렬 문구')
    expect(chipItems()[1]).toHaveClass('is-invalid')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
    const select = within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' })
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(select).toHaveAccessibleDescription(/정렬 문구/)

    await user.selectOptions(select, 'asc')

    expect(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' })).not.toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText('정렬 문구')).not.toBeInTheDocument()
  })

  it('puts an old top-level sort location in the summary only', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    failWith(issue(['sort', 'column'], '예전 정렬 위치 문구'))

    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('예전 정렬 위치 문구')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
  })

  it('lists an issue it cannot place in the summary only', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    failWith(issue(['nowhere'], '어디에도 없는 위치 문구'))

    await runQuery(user)

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('어디에도 없는 위치 문구')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
  })

  it('shows an aggregate-required issue the server returns next to the chip and setting', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Deal code')
    failWith(issue(['columns', 1, 'aggregate'], '집계를 골라야 합니다 서버 문구', 'aggregate-required'))

    await runQuery(user)

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('집계를 골라야 합니다 서버 문구')
    expect(chipItems()[1]).toHaveClass('is-invalid')
  })

  it('sends count for a text column when grouping and runs without an aggregate-required issue', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Deal code')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    await runQuery(user)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(lastQuery().columns).toEqual([
      { field: 'deal.vendor', group: true },
      { field: 'deal.code', group: false, aggregate: 'count' },
    ])
  })

  it('shows the server issue of a count column without grouping', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Action 건수')

    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요')
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })
})

describe('위반 표시 해제 (AC13)', () => {
  it('clears an issue after the column is edited', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 0], '코드 컬럼 문구'), issue(['columns', 1, 'label'], '이름 컬럼 문구'))
    await runQuery(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('고칠 곳 2개')

    await user.type(within(settingsOf('Deal 이름')).getByRole('textbox', { name: '표시 이름' }), '이름')

    const summary = screen.getByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('코드 컬럼 문구')
    expect(summary).not.toHaveTextContent('이름 컬럼 문구')
    expect(chipItems()[1]).not.toHaveClass('is-invalid')
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })

  it('drops the issue of a column that is removed and the summary when none is left', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 1, 'field'], '이름 컬럼 문구'))
    await runQuery(user)
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: 'Deal 이름 빼기' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(1)
  })

  it('clears the issue of a condition after its value is edited', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')
    failWith(issue(['conditions', 0, 'value'], '조건 값 문구'))
    await runQuery(user)
    await screen.findByRole('alert')

    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '권')

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).not.toHaveAttribute('aria-invalid', 'true')
  })
})

describe('그 밖의 실패 (AC13)', () => {
  it('shows the timeout and network messages and clears the old result', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()

    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()

    mockControl.setReportQueryHandler(() => {
      throw new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })
    })
    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('서버에 연결할 수 없습니다.')
    expect(screen.getByRole('alert')).not.toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
  })

  it('shows the message of another server error', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })

    await runQuery(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 내부 오류입니다')
  })

  it('removes the failure message after a successful run', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    await runQuery(user)
    await screen.findByRole('alert')

    mockControl.setReportQueryHandler(null)
    await runQuery(user)

    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
