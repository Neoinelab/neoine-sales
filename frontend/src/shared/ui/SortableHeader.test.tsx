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

describe('SortableHeader', () => {
  // 테스트 코드: UI-052
  it.each([
    ['asc', 'ascending'],
    ['desc', 'descending'],
  ] as const)('정렬 중인 %s 열은 aria-sort %s와 방향 표시를 가진다', (order, aria) => {
    // given: 정렬 중인 "담당자" 머리글
    // when: 그린다
    renderHeader(<SortableHeader label="담당자" active order={order} onSort={() => undefined} />)
    // then: aria-sort와 버튼 방향·클래스가 있다
    expect(screen.getByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', aria)
    expect(screen.getByRole('button', { name: '담당자' })).toHaveAttribute('data-dir', order)
    expect(screen.getByRole('button', { name: '담당자' })).toHaveClass('th-sort')
  })

  // 테스트 코드: UI-052
  it('정렬 중이 아닌 열은 aria-sort도 방향 표시도 없다', () => {
    // given: 정렬 중이 아닌 "유형" 머리글
    // when: 그린다
    renderHeader(<SortableHeader label="유형" active={false} order="desc" onSort={() => undefined} />)
    // then: aria-sort와 data-dir이 없다
    expect(screen.getByRole('columnheader', { name: '유형' })).not.toHaveAttribute('aria-sort')
    expect(screen.getByRole('button', { name: '유형' })).not.toHaveAttribute('data-dir')
  })

  // 테스트 코드: UI-052
  it('버튼을 누르면 onSort를 부른다', async () => {
    // given: onSort가 연결된 "Due Date" 머리글
    const onSort = vi.fn()
    renderHeader(<SortableHeader label="Due Date" active={false} order="asc" onSort={onSort} />)
    // when: 버튼을 누른다
    await userEvent.click(screen.getByRole('button', { name: 'Due Date' }))
    // then: onSort가 한 번 불린다
    expect(onSort).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-052
  it('onSort가 없으면 버튼 없이 글자만 보인다', () => {
    // given: onSort 없는 "Memo" 머리글
    // when: 그린다
    renderHeader(<SortableHeader label="Memo" active={false} order="asc" />)
    // then: 버튼과 aria-sort가 없다
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Memo' })).not.toHaveAttribute('aria-sort')
  })
})
