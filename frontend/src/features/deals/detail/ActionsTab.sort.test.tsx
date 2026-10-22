import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { defaultMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'

const TITLE = '한빛은행 ITDR 도입'

async function openActions(no = 1, title = TITLE) {
  const view = await renderAt(await detailPath(no, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

const rows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)
const cells = (table: HTMLElement, column: number) => rows(table).map((r) => within(r).getAllByRole('cell')[column]?.textContent ?? '')
const sortedHeader = (table: HTMLElement) =>
  within(table)
    .getAllByRole('columnheader')
    .filter((h) => h.hasAttribute('aria-sort'))
    .map((h) => [h.textContent, h.getAttribute('aria-sort')])
const click = (user: Awaited<ReturnType<typeof openActions>>['user'], table: HTMLElement, name: string) =>
  user.click(within(table).getByRole('button', { name }))

/** 로그인한 채 박영업이 같은 Deal에 Action을 하나 더 남긴다(시계가 지나 가장 최근 수행이 된다). */
async function parkActs(no: number, progress: string) {
  const code = await dealCodeOf(no)
  defaultMock.clock.advance(60_000)
  await gateway.auth.quickLogin(USER_ID.park)
  await gateway.actions.create(code, { type: { name: '미팅' }, progress, nextAction: '', dueDate: '', memo: '' })
  await gateway.auth.quickLogin(USER_ID.kim)
}

describe('Actions 탭 정렬 상태 (AC3·AC4)', () => {
  it('starts newest first on the acted time header', async () => {
    const { table } = await openActions()

    expect(sortedHeader(table)).toEqual([['수행일시', 'descending']])
    expect(rows(table)[0]).toHaveTextContent('최종 가격 협의')
  })

  it('sorts a new column in its natural order, then reverses it on the second click', async () => {
    const { user, table } = await openActions()

    await click(user, table, '유형')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'ascending']]))
    const asc = cells(table, 3)
    expect([...asc].sort()).toEqual(asc)
    expect(new Set(asc).size).toBeGreaterThan(1)

    await click(user, table, '유형')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'descending']]))
    expect(cells(table, 3)).toEqual([...asc].sort().reverse())
  })

  it('starts Due Date ascending and the acted time descending again after another column', async () => {
    const { user, table } = await openActions()

    await click(user, table, 'Due Date')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['Due Date', 'ascending']]))
    const dues = cells(table, 6).map((c) => /\d{4}-\d{2}-\d{2}/.exec(c)?.[0] ?? '')
    expect([...dues].sort()).toEqual(dues)

    await click(user, table, '수행일시')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['수행일시', 'descending']]))
    expect(rows(table)[0]).toHaveTextContent('최종 가격 협의')
  })

  it('shows the order the server returns for the chosen sort, without sorting again on the screen', async () => {
    const { user, table } = await openActions()
    const code = await dealCodeOf(1)
    await gateway.auth.quickLogin(USER_ID.kim)

    await click(user, table, '담당자')

    const expected = (await gateway.actions.list(code, { sort: 'actor', order: 'asc' })).map((a) => a.progress)
    await waitFor(() => expect(cells(table, 4).map((c) => c.trim())).toEqual(expected.map((p) => p ?? '—')))
  })

  it('orders by actor name, ascending then descending, with the newest first among the same actor', async () => {
    const { user, table } = await openActions()
    await parkActs(1, '박영업의 진행')
    await click(user, table, '담당자')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['담당자', 'ascending']]))

    await waitFor(() => expect(cells(table, 1).at(-1)).toContain('박영업'))
    expect(cells(table, 1)[0]).toContain('김영업')
    expect(cells(table, 4)[0]).toBe('최종 가격 협의')

    await click(user, table, '담당자')
    await waitFor(() => expect(cells(table, 1)[0]).toContain('박영업'))
    expect(cells(table, 4)[1]).toBe('최종 가격 협의')
  })
})

describe('Actions 탭 정렬과 검색 (AC1·AC11)', () => {
  it('has no sort input in the search bar', async () => {
    await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })

    expect(within(form).queryByLabelText('정렬')).not.toBeInTheDocument()
    for (const label of ['유형', '담당자', '키워드', '수행일', '기한']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
    expect(within(form).getByRole('button', { name: '검색' })).toBeVisible()
    expect(within(form).getByRole('button', { name: '초기화' })).toBeVisible()
  })

  it('keeps the applied condition when the sort changes', async () => {
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(rows(table)).toHaveLength(1))

    await click(user, table, 'Due Date')

    await waitFor(() => expect(sortedHeader(table)).toEqual([['Due Date', 'ascending']]))
    expect(rows(table)).toHaveLength(1)
    expect(rows(table)[0]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  it('keeps the sort when searching again', async () => {
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    await click(user, table, '유형')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'ascending']]))

    await user.type(within(form).getByLabelText('키워드'), '가격')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(rows(table).length).toBeGreaterThan(0))
    expect(sortedHeader(table)).toEqual([['유형', 'ascending']])
  })

  it('clears the condition on reset but keeps the sort', async () => {
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    const total = rows(table).length
    await click(user, table, '담당자')
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(rows(table)).toHaveLength(1))

    await user.click(within(form).getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(rows(table)).toHaveLength(total))
    expect(within(form).getByLabelText('키워드')).toHaveValue('')
    expect(sortedHeader(table)).toEqual([['담당자', 'ascending']])
  })
})

describe('Actions 탭 빈 목록 문구 (AC12)', () => {
  it('says there are no registered actions, not that no condition matched, when only the sort is not the default', async () => {
    const { user, table } = await openActions()
    await click(user, table, '담당자')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['담당자', 'ascending']]))
    const code = await dealCodeOf(1)
    await gateway.auth.quickLogin(USER_ID.root)
    for (const action of await gateway.actions.list(code, {})) await gateway.actions.remove(action.id)
    await gateway.auth.quickLogin(USER_ID.kim)

    await click(user, table, '담당자')

    expect(await screen.findByText('등록된 Action이 없습니다.')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Action이 없습니다.')).not.toBeInTheDocument()
  })
})
