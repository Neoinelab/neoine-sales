import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { dealCodeOf } from '../../../test/detailTestUtils'
import type { ActionSortState } from './actionSort'
import { ActionTable } from './ActionTable'

const SORTABLE = ['수행일시', '담당자', '유형', 'Due Date', '상태']
const PLAIN = ['등록 시점 Status·Forecast', '진행사항', 'Next Action', 'Memo', '관리']
const DEFAULT: ActionSortState = { sort: 'actedAt', order: 'desc' }

beforeEach(() => resetMock({ now: '2030-06-15T09:00:00+09:00' }))

async function renderTable(sort: ActionSortState, onSort: (key: string) => void = () => undefined) {
  const code = await dealCodeOf(1)
  await gateway.auth.quickLogin(USER_ID.root)
  const deal = await gateway.deals.get(code)
  const actions = await gateway.actions.list(code, {})
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ActionTable
        actions={actions}
        deal={deal}
        canEdit
        me={null}
        onEdit={() => undefined}
        onDelete={() => undefined}
        sort={sort}
        onSort={onSort as never}
      />
    </QueryClientProvider>,
  )
  return screen.getByRole('table', { name: 'Action 목록' })
}

const header = (table: HTMLElement, name: string) => within(table).getByRole('columnheader', { name })

describe('ActionTable 헤더 정렬 (AC2·AC3)', () => {
  it('makes only the five sortable headers buttons with their column name', async () => {
    const table = await renderTable(DEFAULT)

    expect(within(table).getAllByRole('button', { name: new RegExp(`^(${SORTABLE.join('|')})$`) })).toHaveLength(5)
    for (const name of SORTABLE) {
      expect(within(header(table, name)).getByRole('button', { name })).toHaveClass('th-sort')
    }
    for (const name of PLAIN) {
      expect(within(header(table, name)).queryByRole('button')).not.toBeInTheDocument()
      expect(header(table, name)).not.toHaveAttribute('aria-sort')
    }
  })

  it('shows the acted time as sorted descending with the down arrow marker by default', async () => {
    const table = await renderTable(DEFAULT)

    expect(header(table, '수행일시')).toHaveAttribute('aria-sort', 'descending')
    expect(within(header(table, '수행일시')).getByRole('button')).toHaveAttribute('data-dir', 'desc')
    for (const name of SORTABLE.slice(1)) {
      expect(header(table, name)).not.toHaveAttribute('aria-sort')
      expect(within(header(table, name)).getByRole('button')).not.toHaveAttribute('data-dir')
    }
  })

  it.each([
    [{ sort: 'actor', order: 'asc' }, '담당자', 'ascending', 'asc'],
    [{ sort: 'type', order: 'desc' }, '유형', 'descending', 'desc'],
    [{ sort: 'dueDate', order: 'asc' }, 'Due Date', 'ascending', 'asc'],
    [{ sort: 'nextActionStatus', order: 'desc' }, '상태', 'descending', 'desc'],
    [{ sort: 'actedAt', order: 'asc' }, '수행일시', 'ascending', 'asc'],
  ] as const)('puts aria-sort and data-dir on %j only (%s)', async (sort, name, aria, dir) => {
    const table = await renderTable(sort)

    expect(within(table).getAllByRole('columnheader').filter((h) => h.hasAttribute('aria-sort'))).toEqual([header(table, name)])
    expect(header(table, name)).toHaveAttribute('aria-sort', aria)
    expect(within(header(table, name)).getByRole('button')).toHaveAttribute('data-dir', dir)
    expect(table.querySelectorAll('[data-dir]')).toHaveLength(1)
  })

  it('reports the column key of the clicked header', async () => {
    const onSort = vi.fn()
    const table = await renderTable(DEFAULT, onSort)
    const keys: [string, string][] = [
      ['수행일시', 'actedAt'],
      ['담당자', 'actor'],
      ['유형', 'type'],
      ['Due Date', 'dueDate'],
      ['상태', 'nextActionStatus'],
    ]

    for (const [name] of keys) await userEvent.click(within(table).getByRole('button', { name }))

    expect(onSort.mock.calls.map((c) => c[0])).toEqual(keys.map(([, key]) => key))
  })
})
