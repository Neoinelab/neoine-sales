import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SortableHeader } from './SortableHeader'

function renderHeader(node: React.ReactNode) {
  render(
    <table>
      <thead>
        <tr>{node}</tr>
      </thead>
    </table>,
  )
}

describe('SortableHeader (AC13)', () => {
  it.each([
    ['asc', 'ascending'],
    ['desc', 'descending'],
  ] as const)('marks the active %s column with aria-sort %s and data-dir', (order, aria) => {
    renderHeader(<SortableHeader label="담당자" active order={order} onSort={() => undefined} />)

    expect(screen.getByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', aria)
    expect(screen.getByRole('button', { name: '담당자' })).toHaveAttribute('data-dir', order)
    expect(screen.getByRole('button', { name: '담당자' })).toHaveClass('th-sort')
  })

  it('has neither aria-sort nor data-dir when it is not the sorted column', () => {
    renderHeader(<SortableHeader label="유형" active={false} order="desc" onSort={() => undefined} />)

    expect(screen.getByRole('columnheader', { name: '유형' })).not.toHaveAttribute('aria-sort')
    expect(screen.getByRole('button', { name: '유형' })).not.toHaveAttribute('data-dir')
  })

  it('calls onSort when the button is clicked', async () => {
    const onSort = vi.fn()
    renderHeader(<SortableHeader label="Due Date" active={false} order="asc" onSort={onSort} />)

    await userEvent.click(screen.getByRole('button', { name: 'Due Date' }))

    expect(onSort).toHaveBeenCalledTimes(1)
  })

  it('renders only the label, without a button or aria-sort, when there is no onSort', () => {
    renderHeader(<SortableHeader label="Memo" active={false} order="asc" />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Memo' })).not.toHaveAttribute('aria-sort')
  })
})
