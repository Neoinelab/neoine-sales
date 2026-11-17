import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { COMMENT_NOW, commentItems, openDealTab, seedComments } from '../../../test/commentScreen'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import type { CommentSeed } from '../../../test/fake/types'

/** Comments 탭의 읽지 않은 수 배지와 Owner 읽음 처리(CM-R38·R39). Deal 1의 Owner는 김영업이다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const unreadBy = (code: string, count: number, authorId: number = USER_ID.park): CommentSeed[] =>
  Array.from({ length: count }, (_, i) => ({ dealCode: code, authorId, body: `읽지 않은 ${i + 1}`, createdAt: `2026-11-12T09:${String(i % 60).padStart(2, '0')}:00+09:00` }))

const tab = () => screen.getByRole('tab', { name: /^Comments/ })

describe('Comments 탭 배지', () => {
  // 배지는 Deal의 읽지 않은 수이고 누구에게나 같으며 100건 이상은 99+다.
  // 테스트 코드: CM-069
  it('shows the unread count of the deal to everyone, caps it at 99+ and hides it at zero', async () => {
    // given: 읽지 않은 Comment 3건(Owner 김영업 것은 제외)이 있다
    const view = await openDealTab('info', { userId: USER_ID.park })
    await seedComments(view, [...unreadBy(view.code, 3), { dealCode: view.code, authorId: USER_ID.kim, body: 'Owner 글', createdAt: '2026-11-12T10:00:00+09:00', readAt: '2026-11-12T10:00:00+09:00' }])

    // when·then: 박영업이 보는 탭에 배지 "3"과 접근 이름이 있다
    await waitFor(() => expect(tab()).toHaveAccessibleName('Comments 읽지 않은 Comment 3건'))
    expect(within(tab()).getByText('3')).toBeVisible()
    view.unmount()

    // when·then: 김영업(Owner)이 보아도 같고(Deal 상세 탭에서는 읽음 처리하지 않는다), 한조회(user)도 같다
    for (const userId of [USER_ID.kim, USER_ID.han]) {
      const other = await openDealTab('info', { userId })
      await seedComments(other, unreadBy(other.code, 3))
      await waitFor(() => expect(within(tab()).getByText('3')).toBeVisible())
      other.unmount()
    }

    // given: 120건이면
    const many = await openDealTab('info', { userId: USER_ID.park })
    await seedComments(many, unreadBy(many.code, 120))
    // then: "99+"다
    await waitFor(() => expect(within(tab()).getByText('99+')).toBeVisible())
    many.unmount()

    // given: 읽지 않은 Comment가 없으면
    await openDealTab('info', { userId: USER_ID.park })
    // then: 배지가 없고 접근 이름은 "Comments"뿐이다
    await screen.findByRole('tab', { name: 'Comments' })
    expect(within(tab()).queryByText(/^\d+\+?$/)).not.toBeInTheDocument()
  })
})

describe('Owner의 읽음 처리', () => {
  // Owner가 Comments 탭을 열면 읽지 않은 Comment만 한 번 읽음 처리되고 NEW 표시가 남은 채 배지가 사라진다.
  // 테스트 코드: CM-070
  it('marks only the unread comments read once for the owner, keeps a NEW mark and clears the badge', async () => {
    // given: 읽지 않은 Comment 3건과 읽은 Comment 2건이 있는 Deal을 Owner(김영업)가 Deal 상세 탭에서 연다
    const markRead = vi.spyOn(gateway.comments, 'markRead')
    const view = await openDealTab('info', { userId: USER_ID.kim })
    const read = { readAt: '2026-11-11T12:00:00+09:00' }
    const added = await seedComments(view, [
      { dealCode: view.code, authorId: USER_ID.kim, body: '읽은 1', createdAt: '2026-11-11T09:00:00+09:00', ...read },
      { dealCode: view.code, authorId: USER_ID.kim, body: '읽은 2', createdAt: '2026-11-11T09:10:00+09:00', ...read },
      ...unreadBy(view.code, 3),
    ])
    await waitFor(() => expect(within(tab()).getByText('3')).toBeVisible())
    expect(markRead).not.toHaveBeenCalled()

    // when: Comments 탭을 연다
    await view.user.click(tab())

    // then: 읽음 처리 요청은 한 번이고 comment_ids는 읽지 않던 3건뿐이다
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(1))
    expect(markRead.mock.calls[0]?.[0]).toBe(view.code)
    expect([...(markRead.mock.calls[0]?.[1] ?? [])].sort()).toEqual(added.slice(2).map((c) => c.id).sort())
    // then: 세 항목에 "NEW"가 보이고 탭 배지가 사라진다
    await waitFor(() => expect(within(tab()).queryByText('3')).not.toBeInTheDocument())
    expect(commentItems().filter((li) => within(li).queryByText('NEW') !== null)).toHaveLength(3)

    // when: 다른 탭에 갔다가 다시 Comments 탭을 연다
    await view.user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    await view.user.click(tab())
    // then: "NEW"가 없고 요청도 더 없다
    await screen.findByRole('list', { name: 'Comment 목록' })
    expect(screen.queryByText('NEW')).not.toBeInTheDocument()
    expect(markRead).toHaveBeenCalledTimes(1)
  })

  // Owner가 아닌 sales·admin·user가 열면 읽음 처리 요청이 없고 "읽지 않음" 표시와 배지가 그대로다.
  // 테스트 코드: CM-071
  it.each([
    ['다른 sales', { userId: USER_ID.park }],
    ['admin', { role: 'admin' as const }],
    ['user', { role: 'user' as const }],
  ])('sends no mark-read request when %s opens the tab and keeps the unread mark and badge', async (_who, options) => {
    // given: 읽지 않은 Comment 2건
    const markRead = vi.spyOn(gateway.comments, 'markRead')
    const view = await openDealTab('info', options)
    await seedComments(view, unreadBy(view.code, 2, USER_ID.root))

    // when: Comments 탭을 연다
    await view.user.click(tab())
    await screen.findByRole('list', { name: 'Comment 목록' })

    // then: 요청이 없고 두 항목이 "읽지 않음"이며 탭 배지 "2"가 그대로다
    expect(markRead).not.toHaveBeenCalled()
    expect(commentItems().filter((li) => within(li).queryByText('읽지 않음') !== null)).toHaveLength(2)
    expect(within(tab()).getByText('2')).toBeVisible()
  })

  // 읽음 처리가 실패하면 오류 없이 배지가 그대로이고 다음 열람에서 같은 id로 다시 보낸다.
  // 테스트 코드: CM-072
  it('shows no error when the mark-read fails and sends the same ids again on the next opening', async () => {
    // given: 읽지 않은 Comment 1건과 한 번만 실패하는 읽음 처리
    const real = gateway.comments.markRead.bind(gateway.comments)
    const markRead = vi
      .spyOn(gateway.comments, 'markRead')
      .mockRejectedValueOnce(new ApiError(503, { type: 'https://sales.neoine.test/problems/storage-unavailable', title: 'x', status: 503, detail: '잠시 후 다시 시도하세요.' }))
      .mockImplementation(real)
    const view = await openDealTab('info', { userId: USER_ID.kim })
    const [one] = await seedComments(view, unreadBy(view.code, 1))

    // when: Comments 탭을 연다
    await view.user.click(tab())
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(1))
    await screen.findByRole('list', { name: 'Comment 목록' })

    // then: 오류 배너가 없고 배지 "1"이 남는다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(within(tab()).getByText('1')).toBeVisible()

    // when: Deal 상세 탭으로 갔다가 다시 Comments 탭을 연다
    await view.user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    await view.user.click(tab())

    // then: 같은 id로 다시 요청하고 배지가 사라진다
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(2))
    expect(markRead.mock.calls[1]?.[1]).toEqual([one!.id])
    await waitFor(() => expect(within(tab()).queryByText('1')).not.toBeInTheDocument())
  })
})

describe('읽음 처리 묶음', () => {
  // 읽지 않은 Comment가 501건이면 500건씩 두 번 나눠 보낸다.
  // 테스트 코드: CM-070
  it('sends 501 unread comments in two requests of 500 and 1', async () => {
    // given: 읽지 않은 Comment 501건을 Owner가 Comments 탭에서 연다
    const markRead = vi.spyOn(gateway.comments, 'markRead')
    const view = await openDealTab('info', { userId: USER_ID.kim })
    await seedComments(view, unreadBy(view.code, 501))

    // when: Comments 탭을 연다
    await view.user.click(tab())

    // then: 요청은 두 번이고 묶음 크기는 500, 1이며 id는 겹치지 않는다
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(2))
    const [first, second] = markRead.mock.calls.map((call) => call[1] ?? [])
    expect([first?.length, second?.length]).toEqual([500, 1])
    expect(new Set([...(first ?? []), ...(second ?? [])]).size).toBe(501)
  })

  // 둘째 묶음이 실패해도 목록과 배지를 다시 읽어 첫 묶음의 읽음이 반영된다.
  // 테스트 코드: CM-072
  it('refetches the list and badge even when the second chunk fails', async () => {
    // given: 둘째 묶음에서 실패하는 읽음 처리와 읽지 않은 501건
    const real = gateway.comments.markRead.bind(gateway.comments)
    const markRead = vi
      .spyOn(gateway.comments, 'markRead')
      .mockImplementationOnce(real)
      .mockRejectedValueOnce(new ApiError(503, { type: 'https://sales.neoine.test/problems/storage-unavailable', title: 'x', status: 503, detail: '잠시 후 다시 시도하세요.' }))
    const view = await openDealTab('info', { userId: USER_ID.kim })
    await seedComments(view, unreadBy(view.code, 501))
    await waitFor(() => expect(tab()).toHaveAccessibleName('Comments 읽지 않은 Comment 501건'))

    // when: Comments 탭을 연다
    await view.user.click(tab())
    await waitFor(() => expect(markRead).toHaveBeenCalledTimes(2))

    // then: 오류 배너 없이 배지가 첫 묶음만큼 줄어 1건이 남는다
    await waitFor(() => expect(tab()).toHaveAccessibleName('Comments 읽지 않은 Comment 1건'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
