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
  await defaultMock.signInAs(USER_ID.park)
  await gateway.actions.create(code, { type: { name: '미팅' }, progress, nextAction: '', dueDate: '', memo: '' })
  await defaultMock.signInAs(USER_ID.kim)
}

describe('Actions 탭 정렬 상태', () => {
  // 처음에는 수행일 머리글이 내림차순(최신순)으로 표시된다.
  // 테스트 코드: NA-063
  it('starts newest first on the acted time header', async () => {
    // when: Actions 표를 연다.
    const { table } = await openActions()

    // then: 수행일가 descending으로 표시되고 최신 행이 맨 위다.
    expect(sortedHeader(table)).toEqual([['수행일', 'descending']])
    expect(rows(table)[0]).toHaveTextContent('최종 가격 협의')
  })

  // 다른 열은 자연 방향(오름차순)으로 시작하고 같은 열을 다시 누르면 방향이 바뀐다.
  // 테스트 코드: NA-063
  it('sorts a new column in its natural order, then reverses it on the second click', async () => {
    // given: Actions 표가 기본 정렬이다.
    const { user, table } = await openActions()

    // when: 유형 머리글을 누른다.
    await click(user, table, '유형')
    // then: 유형 오름차순으로 보인다.
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'ascending']]))
    const asc = cells(table, 3)
    expect([...asc].sort()).toEqual(asc)
    expect(new Set(asc).size).toBeGreaterThan(1)

    // when: 유형 머리글을 다시 누른다.
    await click(user, table, '유형')
    // then: 유형 내림차순으로 바뀐다.
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'descending']]))
    expect(cells(table, 3)).toEqual([...asc].sort().reverse())
  })

  // Due Date는 오름차순으로 시작하고 다른 열 뒤 수행일는 다시 내림차순으로 시작한다.
  // 테스트 코드: NA-063
  it('starts Due Date ascending and the acted time descending again after another column', async () => {
    // given: Actions 표가 기본 정렬이다.
    const { user, table } = await openActions()

    // when: Due Date 머리글을 누른다.
    await click(user, table, 'Due Date')
    // then: Due Date 오름차순으로 보인다.
    await waitFor(() => expect(sortedHeader(table)).toEqual([['Due Date', 'ascending']]))
    const dues = cells(table, 6).map((c) => /\d{4}-\d{2}-\d{2}/.exec(c)?.[0] ?? '')
    expect([...dues].sort()).toEqual(dues)

    // when: 수행일 머리글을 누른다.
    await click(user, table, '수행일')
    // then: 수행일 내림차순으로 시작한다.
    await waitFor(() => expect(sortedHeader(table)).toEqual([['수행일', 'descending']]))
    expect(rows(table)[0]).toHaveTextContent('최종 가격 협의')
  })

  // 화면은 서버가 준 순서를 그대로 보인다(다시 정렬하지 않는다).
  // 테스트 코드: NA-064
  it('shows the order the server returns for the chosen sort, without sorting again on the screen', async () => {
    // given: Actions 표가 기본 정렬이다.
    const { user, table } = await openActions()
    const code = await dealCodeOf(1)
    await defaultMock.signInAs(USER_ID.kim)

    // when: 담당자 머리글을 누른다.
    await click(user, table, '담당자')

    // then: 행 순서가 서버(Fake 게이트웨이)가 준 담당자 오름차순과 같다.
    const expected = (await gateway.actions.list(code, { sort: 'actor', order: 'asc' })).map((a) => a.progress)
    await waitFor(() => expect(cells(table, 4).map((c) => c.trim())).toEqual(expected.map((p) => p ?? '—')))
  })

  // 담당자 정렬은 오름차순·내림차순 모두 같은 담당자 안에서 최신 수행이 먼저다.
  // 테스트 코드: NA-064
  it('orders by actor name, ascending then descending, with the newest first among the same actor', async () => {
    // given: 박영업이 같은 Deal에 Action을 하나 더 남겼다.
    const { user, table } = await openActions()
    await parkActs(1, '박영업의 진행')
    // when: 담당자 머리글을 누른다.
    await click(user, table, '담당자')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['담당자', 'ascending']]))

    // then: 김영업 행이 앞, 박영업 행이 뒤이고 김영업 안에서는 최신이 먼저다.
    await waitFor(() => expect(cells(table, 1).at(-1)).toContain('박영업'))
    expect(cells(table, 1)[0]).toContain('김영업')
    expect(cells(table, 4)[0]).toBe('최종 가격 협의')

    // when: 담당자 머리글을 다시 누른다.
    await click(user, table, '담당자')
    // then: 박영업 행이 앞으로 온다.
    await waitFor(() => expect(cells(table, 1)[0]).toContain('박영업'))
    expect(cells(table, 4)[1]).toBe('최종 가격 협의')
  })
})

describe('Actions 탭 정렬과 검색', () => {
  // 검색 바에는 정렬 입력이 없고 검색·초기화 버튼이 있다.
  // 테스트 코드: NA-052
  it('has no sort input in the search bar', async () => {
    // when: Actions 탭을 연다.
    await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })

    // then: 정렬 칸은 없고 조건 칸과 "검색"·"초기화" 버튼이 있다.
    expect(within(form).queryByLabelText('정렬')).not.toBeInTheDocument()
    for (const label of ['유형', '담당자', '키워드', '수행일', '기한']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
    expect(within(form).getByRole('button', { name: '검색' })).toBeVisible()
    expect(within(form).getByRole('button', { name: '초기화' })).toBeVisible()
  })

  // 정렬을 바꿔도 적용된 검색 조건이 남는다.
  // 테스트 코드: NA-065
  it('keeps the applied condition when the sort changes', async () => {
    // given: 키워드 "ROI"로 검색해 1행이 보인다.
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(rows(table)).toHaveLength(1))

    // when: Due Date 머리글을 누른다.
    await click(user, table, 'Due Date')

    // then: 정렬이 바뀌어도 여전히 1행이다.
    await waitFor(() => expect(sortedHeader(table)).toEqual([['Due Date', 'ascending']]))
    expect(rows(table)).toHaveLength(1)
    expect(rows(table)[0]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  // 다시 검색해도 정렬이 남는다.
  // 테스트 코드: NA-065
  it('keeps the sort when searching again', async () => {
    // given: 유형 오름차순으로 정렬한 상태다.
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    await click(user, table, '유형')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['유형', 'ascending']]))

    // when: 키워드 "가격"으로 다시 검색한다.
    await user.type(within(form).getByLabelText('키워드'), '가격')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 유형 오름차순 표시가 남는다.
    await waitFor(() => expect(rows(table).length).toBeGreaterThan(0))
    expect(sortedHeader(table)).toEqual([['유형', 'ascending']])
  })

  // 초기화하면 조건은 비워지지만 정렬은 남는다.
  // 테스트 코드: NA-059
  it('clears the condition on reset but keeps the sort', async () => {
    // given: 담당자로 정렬하고 키워드 "ROI"로 검색해 1행이 보인다.
    const { user, table } = await openActions()
    const form = screen.getByRole('search', { name: 'Action 검색' })
    const total = rows(table).length
    await click(user, table, '담당자')
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(rows(table)).toHaveLength(1))

    // when: "초기화"를 누른다.
    await user.click(within(form).getByRole('button', { name: '초기화' }))

    // then: 모든 Action이 다시 보이고 키워드 칸이 비며 담당자 정렬은 그대로다.
    await waitFor(() => expect(rows(table)).toHaveLength(total))
    expect(within(form).getByLabelText('키워드')).toHaveValue('')
    expect(sortedHeader(table)).toEqual([['담당자', 'ascending']])
  })
})

describe('Actions 탭 빈 목록 문구', () => {
  // 조건 없이 정렬만 기본이 아니면 Action이 모두 지워졌을 때 "등록된 Action이 없습니다."를 보인다.
  // 테스트 코드: NA-061
  it('says there are no registered actions, not that no condition matched, when only the sort is not the default', async () => {
    // given: 정렬만 담당자로 바꾼 상태에서 그 Deal의 Action이 모두 지워졌다.
    const { user, table } = await openActions()
    await click(user, table, '담당자')
    await waitFor(() => expect(sortedHeader(table)).toEqual([['담당자', 'ascending']]))
    const code = await dealCodeOf(1)
    await defaultMock.signInAs(USER_ID.root)
    for (const action of await gateway.actions.list(code, {})) await gateway.actions.remove(action.id)
    await defaultMock.signInAs(USER_ID.kim)

    // when: 목록을 다시 읽는다(담당자 머리글을 다시 누른다).
    await click(user, table, '담당자')

    // then: "등록된 Action이 없습니다."가 보이고 "조건에 맞는 Action이 없습니다."는 없다.
    expect(await screen.findByText('등록된 Action이 없습니다.')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Action이 없습니다.')).not.toBeInTheDocument()
  })
})
