import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, openActionsTab, openDetail, rowWith } from '../../../test/actionDetail'
import { COMMENT_NOW, commentItems, seedComments } from '../../../test/commentScreen'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Action 상세 팝업의 Comment 영역(CM-R41)과 Owner 읽음 처리. Deal 1의 Owner·Action 작성자는 김영업이다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })

async function openWithAP(who: { role?: 'sales' | 'admin' | 'user'; userId?: number }) {
  const view = await openActionsTab(who)
  const viewer = who.userId ?? (who.role === 'user' ? USER_ID.han : who.role === 'admin' ? USER_ID.root : USER_ID.kim)
  const a = await addAction(view, A_INPUT, USER_ID.kim, viewer)
  const p = await addAction(view, { progress: '현장 점검', type: { name: '방문' }, actedOn: '2026-11-11' }, USER_ID.kim, viewer)
  return { view, a, p }
}

describe('상세 팝업의 Comment 영역', () => {
  // 맨 아래에 그 Action의 Comment만 최근순으로 보이고 그 아래 입력 칸이 있으며 Memo 줄이 없다.
  // 테스트 코드: CM-075
  it('shows only the comments of that action recent first with the input below and no Memo row', async () => {
    // given: A에 Comment 2건, P에 1건, Deal Comment 1건
    const { view, a, p } = await openWithAP({ role: 'admin' })
    await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.kim, body: 'A 먼저', createdAt: '2026-11-12T09:00:00+09:00', readAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.park, body: 'A 나중', createdAt: '2026-11-13T09:00:00+09:00' },
      { dealCode: view.code, actionId: p.id, authorId: USER_ID.park, body: 'P 글', createdAt: '2026-11-13T10:00:00+09:00' },
      { dealCode: view.code, authorId: USER_ID.park, body: 'Deal 글', createdAt: '2026-11-13T11:00:00+09:00' },
    ])

    // when: ROOT가 A 행을 누른다
    const dialog = await openDetail(view, '킥오프 미팅')

    // then: 키·값 줄에 "Memo"가 없고 맨 아래 "Comment (2)"에 A Comment만 최근순으로 있다
    expect(Array.from(dialog.querySelectorAll('dt')).map((el) => el.textContent)).not.toContain('Memo')
    expect(await within(dialog).findByRole('heading', { name: 'Comment (2)' })).toBeVisible()
    const items = commentItems(dialog)
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('A 나중')
    expect(items[1]).toHaveTextContent('A 먼저')
    expect(within(dialog).queryByRole('group', { name: '연결된 Action' })).not.toBeInTheDocument()
    // then: 목록 아래에 "Comment 입력"과 "저장"이 있다
    const box = within(dialog).getByLabelText('Comment 입력')
    expect(within(dialog).getByRole('list', { name: 'Comment 목록' }).compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeVisible()
  })

  // Comment가 없는 Action은 "Comment (0)"과 안내 문구다.
  // 테스트 코드: CM-075
  it('shows Comment (0) and the empty notice for an action without comments', async () => {
    // given: Comment가 없는 Action P
    const { view } = await openWithAP({ role: 'admin' })

    // when: P 행을 누른다
    const dialog = await openDetail(view, '현장 점검')

    // then: "Comment (0)"과 "등록된 Comment가 없습니다."가 보인다
    expect(await within(dialog).findByRole('heading', { name: 'Comment (0)' })).toBeVisible()
    expect(within(dialog).getByText('등록된 Comment가 없습니다.')).toBeVisible()
  })

  // 다른 sales가 남의 Action에 쓰면 읽지 않음으로 생겨 팝업·행·탭 배지가 늘고 Comments 탭에 연결 Action과 함께 보인다.
  // 테스트 코드: CM-076
  it('creates an unread comment on another sales action, raises the badges and shows it with its action in the Comments tab', async () => {
    // given: A에 읽지 않은 Comment 1건이 이미 있고 박영업이 A 팝업을 연다(작성 요청 감시)
    const create = vi.spyOn(gateway.comments, 'create')
    const { view, a } = await openWithAP({ userId: USER_ID.park })
    await seedComments(view, [{ dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: '기존 글', createdAt: '2026-11-12T09:00:00+09:00' }])
    const dialog = await openDetail(view, '킥오프 미팅')
    await within(dialog).findByRole('heading', { name: 'Comment (1)' })

    // when: 박영업이 입력 칸에 "견적서 초안 공유함"을 쓰고 Enter를 누른다
    await view.user.type(within(dialog).getByLabelText('Comment 입력'), '견적서 초안 공유함{Enter}')

    // then: 요청 본문은 {body, actionId}이고 팝업 목록 맨 위에 "읽지 않음"과 함께 보이며 "Comment (2)"가 된다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toEqual({ body: '견적서 초안 공유함', actionId: a.id })
    await within(dialog).findByRole('heading', { name: 'Comment (2)' })
    expect(commentItems(dialog)[0]).toHaveTextContent('견적서 초안 공유함')
    expect(commentItems(dialog)[0]).toHaveTextContent('읽지 않음')

    // when: 팝업을 닫고 Comments 탭을 연다
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))
    // then: A 행 배지와 탭 배지가 1에서 2로 늘어 있다
    expect(within(rowWith(view.table, '킥오프 미팅')).getByText('2')).toBeVisible()
    expect(within(screen.getByRole('tab', { name: /^Comments/ })).getByText('2')).toBeVisible()
    await view.user.click(screen.getByRole('tab', { name: /^Comments/ }))
    // then: 그 항목 상자에 A의 수행일·진행사항·Next Action이 있다
    const mine = commentItems().find((li) => li.textContent?.includes('견적서 초안 공유함')) as HTMLElement
    const box = within(mine).getByRole('group', { name: '연결된 Action' })
    expect(box).toHaveTextContent('2026-11-10')
    expect(box).toHaveTextContent('킥오프 미팅')
    expect(box).toHaveTextContent('요구사항 문서 전달')
  })
})

describe('Owner가 상세 팝업을 열 때', () => {
  // Owner가 팝업을 열면 그 Action의 Comment만 읽음 처리되어 그 행 배지와 탭 배지가 줄고 다른 Action 배지는 그대로다.
  // 테스트 코드: CM-077
  it('marks only the comments of that action read, lowering its row badge and the tab badge while the other action keeps its badge', async () => {
    // given: A에 읽지 않은 Comment 2건, P에 1건이 있고 Owner(김영업)가 Actions 탭을 연다
    const markRead = vi.spyOn(gateway.comments, 'markRead')
    const { view, a, p } = await openWithAP({ userId: USER_ID.kim })
    const added = await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.park, body: 'A 1', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.park, body: 'A 2', createdAt: '2026-11-12T09:10:00+09:00' },
      { dealCode: view.code, actionId: p.id, authorId: USER_ID.park, body: 'P 1', createdAt: '2026-11-12T09:20:00+09:00' },
    ])
    const tabBadge = () => within(screen.getByRole('tab', { name: /^Comments/ }))
    await waitFor(() => expect(tabBadge().getByText('3')).toBeVisible())

    // when: A 상세 팝업을 열었다가 닫는다
    const dialog = await openDetail(view, '킥오프 미팅')
    await within(dialog).findByRole('heading', { name: 'Comment (2)' })
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))

    // then: 읽음 처리 요청의 comment_ids는 A Comment 2건이다
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(1))
    expect([...(markRead.mock.calls[0]?.[1] ?? [])].sort()).toEqual([added[0]!.id, added[1]!.id].sort())
    // then: A 행 배지는 사라지고 탭 배지는 "3"에서 "1"로 바뀌며 P 행 배지 "1"은 그대로다
    await waitFor(() => expect(tabBadge().getByText('1')).toBeVisible())
    expect(within(rowWith(view.table, '킥오프 미팅')).queryByText(/^\d+\+?$/)).not.toBeInTheDocument()
    expect(within(rowWith(view.table, '현장 점검')).getByText('1')).toBeVisible()
  })

  // Owner가 아닌 사람이 팝업을 열면 읽음 처리 요청이 없고 "읽지 않음"이 그대로다.
  // 테스트 코드: CM-071
  it.each([
    ['다른 sales', { userId: USER_ID.park }],
    ['admin', { role: 'admin' as const }],
    ['user', { role: 'user' as const }],
  ])('sends no mark-read request when %s opens the action popup', async (_who, who) => {
    // given: A에 읽지 않은 Comment 2건
    const markRead = vi.spyOn(gateway.comments, 'markRead')
    const { view, a } = await openWithAP(who)
    await seedComments(view, [
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: 'A 1', createdAt: '2026-11-12T09:00:00+09:00' },
      { dealCode: view.code, actionId: a.id, authorId: USER_ID.root, body: 'A 2', createdAt: '2026-11-12T09:10:00+09:00' },
    ])

    // when: A 상세 팝업을 연다
    const dialog = await openDetail(view, '킥오프 미팅')
    await within(dialog).findByRole('heading', { name: 'Comment (2)' })

    // then: 요청이 없고 두 항목이 "읽지 않음"이다
    expect(markRead).not.toHaveBeenCalled()
    expect(commentItems(dialog).filter((li) => within(li).queryByText('읽지 않음') !== null)).toHaveLength(2)
    expect(detail()).toBeVisible()
  })
})

describe('상세 팝업의 Comment 저장·삭제 중', () => {
  // 저장 중에는 팝업의 닫기가 꺼지고 Esc를 무시하며 입력 칸과 저장 버튼도 꺼지고 입력 칸에 placeholder가 있다.
  // 테스트 코드: CM-075
  it('disables close, Escape and the input while a comment is being saved and shows the placeholder', async () => {
    // given: 응답이 늦은 Comment 저장과 열린 A 팝업
    let release: () => void = () => undefined
    const real = gateway.comments.create.bind(gateway.comments)
    vi.spyOn(gateway.comments, 'create').mockImplementation(
      (...args) => new Promise((resolve) => { release = () => resolve(real(...args)) }),
    )
    const { view } = await openWithAP({ userId: USER_ID.kim })
    const dialog = await openDetail(view, '킥오프 미팅')
    const box = within(dialog).getByPlaceholderText('Comment를 입력하세요')
    expect(box).toHaveAccessibleName('Comment 입력')

    // when: 글을 쓰고 저장을 누른다(응답 전)
    await view.user.type(box, '저장 중 글')
    await view.user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 닫기·저장 버튼과 입력 칸이 꺼지고 Esc로 닫히지 않는다
    await waitFor(() => expect(box).toBeDisabled())
    expect(within(dialog).getByRole('button', { name: '닫기' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeDisabled()
    await view.user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: DETAIL })).toBeVisible()

    // when: 응답이 오면
    release()
    // then: 입력 칸이 켜지고 비며 닫기가 다시 켜진다
    await waitFor(() => expect(box).toBeEnabled())
    expect(box).toHaveValue('')
    expect(within(dialog).getByRole('button', { name: '닫기' })).toBeEnabled()
  })

  // 삭제 요청 중에는 팝업의 닫기가 꺼지고 Esc를 무시한다.
  // 테스트 코드: CM-075
  it('disables close and ignores Escape on the detail popup while a comment is being deleted', async () => {
    // given: 본인 Comment가 있고 삭제 응답이 늦다
    let release: () => void = () => undefined
    const real = gateway.comments.remove.bind(gateway.comments)
    vi.spyOn(gateway.comments, 'remove').mockImplementation(
      (...args) => new Promise((resolve) => { release = () => resolve(real(...args)) }),
    )
    const { view, a } = await openWithAP({ userId: USER_ID.kim })
    await seedComments(view, [{ dealCode: view.code, actionId: a.id, authorId: USER_ID.kim, body: '지울 글', createdAt: '2026-11-12T09:00:00+09:00', readAt: '2026-11-12T09:00:00+09:00' }])
    const dialog = await openDetail(view, '킥오프 미팅')
    await within(dialog).findByRole('heading', { name: 'Comment (1)' })

    // when: Comment 삭제를 확인한다(응답 전)
    await view.user.click(within(dialog).getByRole('button', { name: 'Comment 삭제' }))
    await view.user.click(within(screen.getByRole('dialog', { name: 'Comment 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 확인 대화상자가 닫히고 상세 팝업의 닫기가 꺼지며 Esc를 무시한다
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '닫기' })).toBeDisabled())
    await view.user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: DETAIL })).toBeVisible()
    release()
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '닫기' })).toBeEnabled())
  })
})
