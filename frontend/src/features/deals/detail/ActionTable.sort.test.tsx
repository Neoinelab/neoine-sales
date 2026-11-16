import { defaultMock } from '../../../test/fake/default'
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

const SORTABLE = ['수행일', '유형', 'Due Date', '상태']
const PLAIN = ['진행사항', 'Next Action']
const DEFAULT: ActionSortState = { sort: 'actedAt', order: 'desc' }

beforeEach(() => resetMock({ now: '2030-06-15T09:00:00+09:00' }))

async function renderTable(sort: ActionSortState, onSort: (key: string) => void = () => undefined) {
  const code = await dealCodeOf(1)
  await defaultMock.signInAs(USER_ID.root)
  const deal = await gateway.deals.get(code)
  const actions = await gateway.actions.list(code, {})
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ActionTable
        actions={actions}
        deal={deal}
        canEdit
        me={null}
        onOpen={() => undefined}
        sort={sort}
        onSort={onSort as never}
      />
    </QueryClientProvider>,
  )
  return screen.getByRole('table', { name: 'Action 목록' })
}

const header = (table: HTMLElement, name: string) => within(table).getByRole('columnheader', { name })

describe('ActionTable 헤더 정렬', () => {
  // 정렬할 수 있는 머리글은 수행일·유형·Due Date·상태 4개(버튼)뿐이다.
  // 테스트 코드: NA-063
  it('makes only the four sortable headers buttons with their column name', async () => {
    // when: Actions 표를 렌더한다.
    const table = await renderTable(DEFAULT)

    // then: 버튼 머리글은 4개이고 나머지 열 머리글은 버튼도 aria-sort도 없다.
    expect(within(table).getAllByRole('button', { name: new RegExp(`^(${SORTABLE.join('|')})$`) })).toHaveLength(4)
    for (const name of SORTABLE) {
      expect(within(header(table, name)).getByRole('button', { name })).toHaveClass('th-sort')
    }
    for (const name of PLAIN) {
      expect(within(header(table, name)).queryByRole('button')).not.toBeInTheDocument()
      expect(header(table, name)).not.toHaveAttribute('aria-sort')
    }
  })

  // 처음 정렬은 수행일 내림차순이며 aria-sort와 방향 표시가 그 열에만 있다.
  // 테스트 코드: NA-063
  it('shows the acted time as sorted descending with the down arrow marker by default', async () => {
    // when: 기본 정렬 상태로 렌더한다.
    const table = await renderTable(DEFAULT)

    // then: 수행일만 descending이고 다른 머리글에는 정렬 표시가 없다.
    expect(header(table, '수행일')).toHaveAttribute('aria-sort', 'descending')
    expect(within(header(table, '수행일')).getByRole('button')).toHaveAttribute('data-dir', 'desc')
    for (const name of SORTABLE.slice(1)) {
      expect(header(table, name)).not.toHaveAttribute('aria-sort')
      expect(within(header(table, name)).getByRole('button')).not.toHaveAttribute('data-dir')
    }
  })

  // 정렬 상태에 맞는 열에만 aria-sort와 방향 표시(data-dir)가 붙는다.
  // 테스트 코드: NA-063
  it.each([
    [{ sort: 'type', order: 'desc' }, '유형', 'descending', 'desc'],
    [{ sort: 'dueDate', order: 'asc' }, 'Due Date', 'ascending', 'asc'],
    [{ sort: 'nextActionStatus', order: 'desc' }, '상태', 'descending', 'desc'],
    [{ sort: 'actedAt', order: 'asc' }, '수행일', 'ascending', 'asc'],
  ] as const)('puts aria-sort and data-dir on %j only (%s)', async (sort, name, aria, dir) => {
    // when: 주어진 정렬 상태로 렌더한다.
    const table = await renderTable(sort)

    // then: 그 열의 머리글에만 aria-sort와 data-dir이 있다.
    expect(within(table).getAllByRole('columnheader').filter((h) => h.hasAttribute('aria-sort'))).toEqual([header(table, name)])
    expect(header(table, name)).toHaveAttribute('aria-sort', aria)
    expect(within(header(table, name)).getByRole('button')).toHaveAttribute('data-dir', dir)
    expect(table.querySelectorAll('[data-dir]')).toHaveLength(1)
  })

  // 머리글을 누르면 그 열의 정렬 키를 알린다.
  // 테스트 코드: NA-063
  it('reports the column key of the clicked header', async () => {
    // given: 정렬 변경을 기록하는 핸들러로 표를 렌더한다.
    const onSort = vi.fn()
    const table = await renderTable(DEFAULT, onSort)
    const keys: [string, string][] = [
      ['수행일', 'actedAt'],
      ['유형', 'type'],
      ['Due Date', 'dueDate'],
      ['상태', 'nextActionStatus'],
    ]

    // when: 정렬 가능한 머리글 4개를 차례로 누른다.
    for (const [name] of keys) await userEvent.click(within(table).getByRole('button', { name }))

    // then: 누른 순서대로 열 키가 전달된다.
    expect(onSort.mock.calls.map((c) => c[0])).toEqual(keys.map(([, key]) => key))
  })
})
