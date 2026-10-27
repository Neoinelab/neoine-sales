import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { resultOf } from '../../../test/reportDesigner'
import { addColumn, openAndRun, openDesigner, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const SQL = 'SELECT d.deal_code FROM deals d ORDER BY 1 LIMIT 100'

describe('생성 SQL (AC14)', () => {
  it('guides before the first run and has no SQL input', async () => {
    const { container } = await openDesigner()

    expect(screen.getByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).toBeInTheDocument()
    expect(container.querySelector('textarea')).toBeNull()
    expect(screen.queryByRole('textbox', { name: /SQL/ })).not.toBeInTheDocument()
  })

  it('shows the generated SQL read only after a run', async () => {
    const { container } = await openAndRun(resultOf({ sql: SQL }), 'Deal code')

    const summary = screen.getByText('생성 SQL 보기(읽기 전용)')
    expect(summary.closest('details')).not.toBeNull()
    const pre = screen.getByText(SQL)
    expect(pre.tagName).toBe('PRE')
    expect(pre).toHaveAttribute('tabindex', '0')
    expect(container.querySelector('textarea')).toBeNull()
    expect(container.querySelector('[contenteditable="true"]')).toBeNull()
    expect(screen.queryByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).not.toBeInTheDocument()
  })

  it('shows the SQL of the latest run', async () => {
    const { user } = await openAndRun(resultOf({ sql: SQL }), 'Deal code')

    await addColumn(user, 'Deal 이름')
    const next = 'SELECT d.deal_code, d.name FROM deals d LIMIT 100'
    mockControl.setReportQueryHandler(() => resultOf({ sql: next }))
    await user.click(screen.getByRole('button', { name: '조회' }))

    expect(await screen.findByText(next)).toBeInTheDocument()
    expect(screen.queryByText(SQL)).not.toBeInTheDocument()
  })
})
