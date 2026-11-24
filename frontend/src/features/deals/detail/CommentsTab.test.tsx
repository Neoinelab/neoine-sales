import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { A_INPUT, addAction, DETAIL, makeGate, openActionsTab } from '../../../test/actionDetail'
import { COMMENT_NOW, commentItems, commentList, openDealTab, seedComments, twoComments } from '../../../test/commentScreen'
import { defaultMock, resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Comments 탭(CM-R32~R37). 서버 시계는 2026-11-17로 고정하고 Deal 1(Owner 김영업)을 쓴다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const notFound = (detail: string) => new ApiError(404, { type: 'https://sales.neoine.test/problems/not-found', title: 'x', status: 404, detail })

describe('Comments 탭의 목록', () => {
  // 맨 오른쪽 Comments 탭이 모든 Comment를 최근순으로 작성자·시각·본문과 함께 보이고 입력 칸은 목록 아래에 있으며 수정 버튼은 없다.
  // 테스트 코드: CM-060
  it('shows every comment recent first with author, time and body under the rightmost Comments tab', async () => {
    // given: KIM의 Deal Comment와 퇴사자의 Comment가 있는 Deal(최고 관리자가 연다)
    const view = await openDealTab('info', { role: 'admin' })
    await seedComments(view, twoComments(view.code))

    // when: "Comments" 탭을 누른다
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))

    // then: 맨 오른쪽 탭이 Comments이고 주소는 ?tab=comments다
    const tabs = within(screen.getByRole('tablist', { name: '상세 탭' })).getAllByRole('tab')
    expect(tabs.at(-1)).toHaveTextContent('Comments')
    expect(view.location()).toContain('tab=comments')
    // then: "Comment 목록"에 최근 것이 위에 있고 작성자·시각·본문(줄바꿈 포함)이 보인다
    const items = await waitFor(() => {
      const found = commentItems()
      expect(found).toHaveLength(2)
      return found
    })
    expect(items[0]).toHaveTextContent('강퇴사(퇴사) · 2026-11-13 14:05')
    expect(items[0]?.textContent).toContain('자료 전달\n2차 예정')
    expect(items[1]).toHaveTextContent('김영업 · 2026-11-12 09:30')
    expect(items[1]).toHaveTextContent('예산 회의 예정')
    // then: 입력 칸은 목록 아래에 있고 "수정" 버튼은 없다
    const composer = screen.getByLabelText('Comment 입력')
    expect(commentList().compareDocumentPosition(composer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
  })

  // 테스트 코드: CM-061
  it('shows the user comment before the action button and hides action content', async () => {
    // given: Action A(수행일 2026-11-10)에 연결된 Comment, 진행사항만 있는 Action P에 연결된 Comment, Deal Comment
    const view = await openActionsTab({ role: 'admin' })
    const a = await addAction(view, A_INPUT, USER_ID.kim, USER_ID.root)
    const p = await addAction(view, { progress: '현장 점검', type: { name: '방문' }, actedOn: '2026-11-11' }, USER_ID.kim, USER_ID.root)
    await seedComments(view, [
      ...twoComments(view.code, a.id),
      { dealCode: view.code, actionId: p.id, authorId: USER_ID.park, body: '점검 결과 공유', createdAt: '2026-11-14T10:00:00+09:00' },
    ])

    // when: Comments 탭을 연다
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))
    await screen.findByRole('list', { name: 'Comment 목록' })

    const items = commentItems()
    const byBody = (text: string) => items.find((li) => li.textContent?.includes(text)) as HTMLElement
    for (const body of ['자료 전달', '점검 결과 공유']) {
      const item = byBody(body)
      const button = within(item).getByRole('button', { name: 'Action 보기' })
      const comment = within(item).getByText(new RegExp(body))
      expect(button).toBeVisible()
      expect(comment.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
    expect(commentList()).not.toHaveTextContent('수행일 2026-11-10')
    expect(commentList()).not.toHaveTextContent('킥오프 미팅')
    expect(commentList()).not.toHaveTextContent('요구사항 문서 전달')
    expect(commentList()).not.toHaveTextContent('현장 점검')
    // then: Deal Comment에는 "Deal Comment" 표시가 있고 상자가 없다
    const dealItem = byBody('예산 회의 예정')
    expect(within(dealItem).getByText('Deal Comment')).toBeVisible()
    expect(within(dealItem).queryByRole('button', { name: 'Action 보기' })).not.toBeInTheDocument()
    expect(within(dealItem).queryByRole('group', { name: '연결된 Action' })).not.toBeInTheDocument()
  })

  // "Action 보기"를 누르면 Actions 탭에서 그 Action 상세 팝업이 열리고 주소의 action이 지워진다. 없는 action id는 오류 배너다.
  // 테스트 코드: CM-062
  it('opens the action detail popup from "Action 보기" and shows a banner for an unknown action id', async () => {
    // given: Action A에 연결된 Comment와 Actions 검색 조건이 걸린 화면
    const view = await openActionsTab({ role: 'admin' })
    const a = await addAction(view, A_INPUT, USER_ID.kim, USER_ID.root)
    await seedComments(view, twoComments(view.code, a.id))
    await view.user.type(screen.getByLabelText('키워드'), '일치하지않음')
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))
    await screen.findByRole('list', { name: 'Comment 목록' })

    // when: A Comment의 "Action 보기"를 누른다
    const linked = commentItems().find((li) => li.textContent?.includes('자료 전달')) as HTMLElement
    await view.user.click(within(linked).getByRole('button', { name: 'Action 보기' }))

    // then: Actions 탭으로 바뀌고 A의 "Action 상세" 팝업이 열리며 주소의 action은 지워진다
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    expect(dialog).toHaveTextContent('킥오프 미팅')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
    expect(view.location()).toContain('tab=actions')
    expect(view.location()).not.toContain('action=')

    // when: 없는 action id의 주소로 이동한다
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))
    view.goTo(`/deals/${view.code}?tab=actions&action=999999`)

    // then: 팝업 없이 "Action을 찾을 수 없습니다." 배너가 보이고 주소에서 action이 지워진다
    expect(await screen.findByText('Action을 찾을 수 없습니다.')).toBeVisible()
    expect(screen.queryByRole('dialog', { name: DETAIL })).not.toBeInTheDocument()
    await waitFor(() => expect(view.location()).not.toContain('action='))
  })

  // Comment가 없으면 안내 문구가 보이고, 재조회 때는 "불러오는 중…"이 다시 나타나지 않으며, 읽기 오류는 서버 문구 배너다.
  // 테스트 코드: CM-063
  it('says there are no comments, does not show loading again on refetch and finally the server message of a failed read', async () => {
    // given: Comment가 없는 Deal
    const view = await openDealTab('comments', { role: 'admin' })

    // when·then: 비어 있으면 안내 문구다
    expect(await screen.findByText('등록된 Comment가 없습니다.')).toBeVisible()

    // given: 목록 응답을 늦춘다
    const { gate, release } = makeGate()
    vi.spyOn(gateway.comments, 'list').mockImplementation(async () => {
      await gate
      return []
    })
    // when: 다시 읽게 한다
    void view.client.invalidateQueries()
    await waitFor(() => expect(view.client.isFetching()).toBeGreaterThan(0))
    // then: 재조회 중에도 안내 문구가 남고 "불러오는 중…"은 보이지 않는다(처음 읽을 때만 보인다, CM-R33)
    expect(screen.getByText('등록된 Comment가 없습니다.')).toBeVisible()
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()
    release()
    await waitFor(() => expect(view.client.isFetching()).toBe(0))

    // given: 목록이 404로 실패하게 한다
    vi.spyOn(gateway.comments, 'list').mockRejectedValue(notFound('Deal을 찾을 수 없습니다.'))
    // when: 다시 읽는다
    void view.client.invalidateQueries()
    // then: 서버 문구 오류 배너가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
  })
})

describe('Comments 탭의 입력 칸', () => {
  // Enter로 저장하면 Deal Comment가 목록 맨 위에 읽지 않음으로 보이고 칸이 비며 포커스가 칸에 있다. Shift+Enter는 줄을 바꾼다.
  // 테스트 코드: CM-064
  it('saves a deal comment with Enter at the top of the list, empties the box and keeps focus; Shift+Enter breaks the line', async () => {
    // given: 이미 Comment가 하나 있는 Comments 탭을 박영업이 연다(요청 감시)
    const create = vi.spyOn(gateway.comments, 'create')
    const view = await openDealTab('comments', { userId: USER_ID.park })
    await seedComments(view, twoComments(view.code))
    await screen.findByRole('list', { name: 'Comment 목록' })
    const box = screen.getByLabelText('Comment 입력')

    // when: "1줄", Shift+Enter, "2줄"을 치고 Enter를 누른다
    await view.user.type(box, '1줄{Shift>}{Enter}{/Shift}2줄{Enter}')

    // then: 요청은 한 번이고 본문은 두 줄이며 action_id가 없다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toEqual({ body: '1줄\n2줄' })
    // then: 목록 맨 위에 박영업 이름과 "읽지 않음"으로 보이고 칸이 비며 포커스가 칸에 있다
    await waitFor(() => expect(commentItems()).toHaveLength(3))
    expect(commentItems()[0]).toHaveTextContent('박영업')
    expect(commentItems()[0]).toHaveTextContent('읽지 않음')
    expect(commentItems()[0]?.textContent).toContain('1줄\n2줄')
    expect(screen.getByLabelText('Comment 입력')).toHaveValue('')
    await waitFor(() => expect(screen.getByLabelText('Comment 입력')).toHaveFocus())

    // then: "저장" 버튼은 없다(Enter로만 저장)
    expect(screen.queryByRole('button', { name: '저장' })).toBeNull()
  })

  // 빈 입력은 화면에서 막고, 서버가 거절하면 서버 문구와 입력을 남긴다.
  // 테스트 코드: CM-065
  it('blocks a blank input on the screen and keeps the input with the server message when the server refuses', async () => {
    // given: 박영업의 Comments 탭(요청 감시)
    const create = vi.spyOn(gateway.comments, 'create')
    const view = await openDealTab('comments', { userId: USER_ID.park })
    await screen.findByText('등록된 Comment가 없습니다.')

    // when: 공백만 치고 Enter를 누른다
    await view.user.type(screen.getByLabelText('Comment 입력'), '   {Enter}')
    // then: "Comment를 입력하세요."가 보이고 요청이 없다
    expect(await screen.findByText('Comment를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()

    // when: 다시 치면(문구가 사라지고) NUL이 든 글을 저장한다
    await view.user.clear(screen.getByLabelText('Comment 입력'))
    fireEvent.change(screen.getByLabelText('Comment 입력'), { target: { value: '가\u0000나' } })
    expect(screen.queryByText('Comment를 입력하세요.')).not.toBeInTheDocument()
    await view.user.type(screen.getByLabelText('Comment 입력'), '{Enter}')

    // then: 서버 문구가 칸 아래에 보이고 입력이 남는다
    expect(await screen.findByText('Comment에는 NUL 문자를 쓸 수 없습니다')).toBeVisible()
    expect(screen.getByLabelText('Comment 입력')).toHaveValue('가\u0000나')
  })

  // user는 목록만 보고 입력 칸·삭제 버튼이 없으며 누구에게도 수정 버튼이 없다.
  // 테스트 코드: CM-066
  it('gives a read-only user the list only, and nobody an edit button', async () => {
    // given: 김영업의 Comment와 Action A
    const view = await openActionsTab({ role: 'user' })
    const a = await addAction(view, A_INPUT, USER_ID.kim, USER_ID.han)
    await seedComments(view, twoComments(view.code, a.id))

    // when: user(한조회)가 Comments 탭을 연다
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))
    await screen.findByRole('list', { name: 'Comment 목록' })

    // then: 목록만 있고 입력 칸·저장·삭제 버튼이 없다
    expect(commentItems()).toHaveLength(2)
    expect(screen.queryByLabelText('Comment 입력')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Comment 삭제' })).not.toBeInTheDocument()

    // when: A 상세 팝업을 연다
    await view.user.click(screen.getAllByRole('button', { name: 'Action 보기' })[0]!)
    const dialog = await screen.findByRole('dialog', { name: DETAIL })
    // then: 팝업에도 목록만 있다
    expect(within(dialog).queryByLabelText('Comment 입력')).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Comment 삭제' })).not.toBeInTheDocument()
  })

  // 수정 버튼은 admin에게도 없다.
  // 테스트 코드: CM-066
  it('shows no edit button to admin either', async () => {
    // given: Comment가 있는 Deal을 admin이 연다
    const view = await openDealTab('comments', { role: 'admin' })
    await seedComments(view, twoComments(view.code))
    await screen.findByRole('list', { name: 'Comment 목록' })

    // when·then: 입력 칸은 있지만 어느 항목에도 수정 버튼이 없다
    expect(screen.getByLabelText('Comment 입력')).toBeVisible()
    expect(screen.queryByRole('button', { name: /수정/ })).not.toBeInTheDocument()
  })
})

describe('Comments 탭의 삭제', () => {
  // 삭제 버튼은 본인 Comment의 sales와 admin에게만 있고 확인 뒤에만 지운다.
  // 테스트 코드: CM-067
  it('shows a delete button only for the own comment of a sales, asks first and deletes only after confirming', async () => {
    // given: 박영업의 p1과 최관리(admin)의 r1이 있는 Comments 탭을 박영업이 연다
    const view = await openDealTab('comments', { userId: USER_ID.park })
    await seedComments(view, [
      { dealCode: view.code, authorId: USER_ID.park, body: 'p1 글', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, authorId: USER_ID.root, body: 'r1 글', createdAt: '2026-11-13T09:00:00+09:00' },
    ])
    await screen.findByRole('list', { name: 'Comment 목록' })

    // then: 박영업에게는 p1에만 "Comment 삭제"가 있다
    const own = commentItems().find((li) => li.textContent?.includes('p1 글')) as HTMLElement
    const other = commentItems().find((li) => li.textContent?.includes('r1 글')) as HTMLElement
    expect(within(own).getByRole('button', { name: 'Comment 삭제' })).toBeVisible()
    expect(within(other).queryByRole('button', { name: 'Comment 삭제' })).not.toBeInTheDocument()

    // when: p1 삭제를 눌러 "취소"한다
    await view.user.click(within(own).getByRole('button', { name: 'Comment 삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Comment 삭제' })
    expect(confirm).toHaveTextContent('이 Comment를 삭제합니다. 삭제는 Deal History에 기록됩니다.')
    await view.user.click(within(confirm).getByRole('button', { name: '취소' }))
    // then: 대화상자만 닫히고 p1이 남는다
    expect(screen.queryByRole('dialog', { name: 'Comment 삭제' })).not.toBeInTheDocument()
    expect(commentItems()).toHaveLength(2)

    // when: 다시 눌러 "삭제"한다
    await view.user.click(within(commentItems().find((li) => li.textContent?.includes('p1 글')) as HTMLElement).getByRole('button', { name: 'Comment 삭제' }))
    await view.user.click(within(await screen.findByRole('dialog', { name: 'Comment 삭제' })).getByRole('button', { name: '삭제' }))
    // then: p1이 사라진다
    await waitFor(() => expect(commentItems()).toHaveLength(1))
    expect(commentItems()[0]).toHaveTextContent('r1 글')
  })

  // admin에게는 모든 항목에 삭제 버튼이 있고, Deal Owner라도 남의 Comment는 못 지운다.
  // 테스트 코드: CM-067
  it('shows delete buttons on every item to admin but none on another sales comment to the deal owner', async () => {
    // given: 박영업·최관리의 Comment가 있는 Deal
    const view = await openDealTab('comments', { role: 'admin' })
    await seedComments(view, [
      { dealCode: view.code, authorId: USER_ID.park, body: 'p1 글', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, authorId: USER_ID.root, body: 'r1 글', createdAt: '2026-11-13T09:00:00+09:00' },
    ])
    await screen.findByRole('list', { name: 'Comment 목록' })
    // then: admin에게는 모든 항목에 삭제 버튼이 있다
    for (const item of commentItems()) expect(within(item).getByRole('button', { name: 'Comment 삭제' })).toBeVisible()

    // when: Deal Owner(김영업)로 바꿔 다시 연다
    await defaultMock.signInAs(USER_ID.kim)
    void view.client.invalidateQueries()
    await waitFor(() => expect(view.client.isFetching()).toBe(0))
    // then: 김영업에게는 남이 쓴 어느 항목에도 삭제 버튼이 없다
    expect(screen.queryByRole('button', { name: 'Comment 삭제' })).not.toBeInTheDocument()
  })

  // 서버가 삭제를 거절하면 대화상자를 닫고 목록 위에 서버 문구를 보인다.
  // 테스트 코드: CM-067
  it('closes the confirm dialog and shows the server message above the list when the server refuses', async () => {
    // given: 서버가 삭제를 거절한다
    vi.spyOn(gateway.comments, 'remove').mockRejectedValue(new ApiError(403, { type: 'https://sales.neoine.test/problems/forbidden', title: 'x', status: 403, detail: '본인 Comment 또는 admin만 삭제할 수 있습니다.' }))
    const view = await openDealTab('comments', { userId: USER_ID.park })
    await seedComments(view, [{ dealCode: view.code, authorId: USER_ID.park, body: 'p1 글', createdAt: '2026-11-12T09:00:00+09:00' }])
    await screen.findByRole('list', { name: 'Comment 목록' })

    // when: 삭제를 눌러 확인한다
    await view.user.click(screen.getByRole('button', { name: 'Comment 삭제' }))
    await view.user.click(within(await screen.findByRole('dialog', { name: 'Comment 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 대화상자가 닫히고 서버 문구가 보이며 항목이 남는다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Comment 삭제' })).not.toBeInTheDocument())
    expect(await screen.findByRole('alert')).toHaveTextContent('본인 Comment 또는 admin만 삭제할 수 있습니다.')
    expect(commentItems()).toHaveLength(1)
  })

  // Comment 작성·삭제가 Deal History 탭에 구분 Comment로 보인다.
  // 테스트 코드: CM-068
  it('shows the written and the deleted comment in the Deal History tab under the Comment target', async () => {
    // given: 박영업의 Comments 탭
    const view = await openDealTab('comments', { userId: USER_ID.park })
    await screen.findByText('등록된 Comment가 없습니다.')

    // when: Comment를 쓰고 지운 뒤 Deal History 탭에서 "변경 대상" Comment를 고른다
    await view.user.type(screen.getByLabelText('Comment 입력'), '이력 글{Enter}')
    await waitFor(() => expect(commentItems()).toHaveLength(1))
    await view.user.click(screen.getByRole('button', { name: 'Comment 삭제' }))
    await view.user.click(within(await screen.findByRole('dialog', { name: 'Comment 삭제' })).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(screen.getByText('등록된 Comment가 없습니다.')).toBeVisible())
    await view.user.click(screen.getByRole('tab', { name: 'Deal History' }))
    await view.user.selectOptions(await screen.findByLabelText('변경 대상'), 'Comment')

    // then: 최신순으로 삭제 행, 등록 행 두 줄이 대상 Comment로 보인다
    const table = await screen.findByRole('table', { name: 'Deal History' })
    await waitFor(() => expect(within(table).getAllByRole('row').slice(1)).toHaveLength(2))
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('삭제')
    expect(rows[1]).toHaveTextContent('등록: 이력 글')
    for (const row of rows) expect(within(row).getByRole('cell', { name: 'Comment' })).toBeVisible()
  })
})

describe('Comments 탭의 읽는 상태와 입력 칸', () => {
  // "불러오는 중…"은 처음 읽을 때만 보이고 재조회 때는 목록이 보이는 채로 보이지 않는다.
  // 테스트 코드: CM-063
  it('shows the loading notice only on the first read and not on a refetch', async () => {
    // given: 응답이 늦은 첫 조회
    let release: () => void = () => undefined
    const real = gateway.comments.list.bind(gateway.comments)
    const list = vi.spyOn(gateway.comments, 'list').mockImplementationOnce(
      (...args) => new Promise((resolve) => { release = () => resolve(real(...args)) }),
    )
    const view = await openDealTab('comments', { role: 'admin' })
    await screen.findByRole('status')
    // then: 처음 읽는 동안은 "불러오는 중…"이 보인다
    expect(screen.getByText('불러오는 중…')).toBeVisible()
    release()
    await screen.findByText('등록된 Comment가 없습니다.')
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()

    // given: 다음 재조회가 늦다
    list.mockImplementationOnce((...args) => new Promise((resolve) => { release = () => resolve(real(...args)) }))
    // when: 캐시를 무효화해 재조회한다
    void view.client.invalidateQueries()
    await waitFor(() => expect(view.client.isFetching()).toBeGreaterThan(0))

    // then: 목록이 보이는 채로 "불러오는 중…"은 나타나지 않는다
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()
    release()
    await waitFor(() => expect(view.client.isFetching()).toBe(0))
  })

  // 입력 칸에는 placeholder "Comment를 입력하세요"가 있다.
  // 테스트 코드: CM-064
  it('gives the input box the placeholder "Comment를 입력하세요"', async () => {
    // given: sales가 연 Comments 탭
    await openDealTab('comments', { userId: USER_ID.kim })

    // when·then: 입력 칸을 찾으면 placeholder가 있고 접근 이름은 "Comment 입력"이다
    const box = await screen.findByPlaceholderText('Comment를 입력하세요')
    expect(box).toHaveAccessibleName('Comment 입력')
  })
})
