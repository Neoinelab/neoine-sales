import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { COMMENT_NOW, commentItems, seedComments } from '../../../test/commentScreen'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import type { CommentSeed } from '../../../test/fake/types'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

/** Deals 목록의 읽지 않은 Comment 배지(CM-R48, DL-R28). Deal 1(한빛은행 ITDR 도입)의 Owner는 김영업이다. */
beforeEach(() => resetMock({ now: COMMENT_NOW }))
afterEach(() => resetMock({ now: null }))

const unread = (dealCode: string, count: number, authorId: number = USER_ID.root): CommentSeed[] =>
  Array.from({ length: count }, (_, i) => ({ dealCode, authorId, body: `읽지 않은 ${i + 1}`, createdAt: `2026-11-12T09:${String(i % 60).padStart(2, '0')}:00+09:00` }))

/** 목록이 떠 있는 동안 Fake 저장소에 Comment를 넣고 목록을 다시 읽게 한다. */
async function seedUnread(client: Parameters<typeof seedComments>[0]['client'], rows: readonly CommentSeed[]) {
  return seedComments({ client }, rows)
}

describe('Deals 목록 읽지 않은 Comment 배지', () => {
  // 읽지 않은 Comment가 있는 행은 이름 링크 바로 뒤·경고 배지 앞에 배지를 보이고 0이면 없으며 100 이상은 99+다.
  // 테스트 코드: DL-109
  it.each([
    ['admin', { role: 'admin' as const }],
    ['sales(김영업)', { userId: USER_ID.kim }],
    ['user(한조회)', { role: 'user' as const }],
  ])('shows the unread badge right after the deal name link and before the risk badge for %s, hiding it at zero and capping at 99+', async (_who, who) => {
    // given: Deal 3(기한초과)에 3건, Deal 6에 150건, Deal 10에는 읽은 Comment만 있다
    const overdue = await dealCodeOf(3)
    const many = await dealCodeOf(6)
    const readOnly = await dealCodeOf(10)
    const { client } = await renderAt(ALL_DEALS, who)
    await rowOf(/미래전자 EDR 교체/)
    await seedUnread(client, [
      ...unread(overdue, 3),
      ...unread(many, 150),
      { dealCode: readOnly, authorId: USER_ID.root, body: '읽은 글', createdAt: '2026-11-12T09:00:00+09:00', readAt: '2026-11-12T10:00:00+09:00' },
    ])

    // when: 목록을 본다(이미 열려 있다)
    const row = await rowOf(/미래전자 EDR 교체/)

    // then: 이름 링크, 배지 "3", "기한초과" 배지 순서이고 배지의 접근 이름·title이 "읽지 않은 Comment 3건"이다
    const link = within(row).getByRole('link', { name: '미래전자 EDR 교체' })
    const badge = await within(row).findByLabelText('읽지 않은 Comment 3건')
    expect(badge).toHaveTextContent('3')
    expect(badge).toHaveAttribute('title', '읽지 않은 Comment 3건')
    const risk = within(row).getByText('기한초과')
    expect(link.compareDocumentPosition(badge) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(badge.compareDocumentPosition(risk) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // then: 배지는 링크·버튼이 아니고 링크 안에 있지 않다
    expect(badge.closest('a, button')).toBeNull()
    // then: 읽은 Comment만 있는 행에는 배지가 없다
    expect(within(await rowOf(/우주항공연구원 ZTNA/)).queryByLabelText(/읽지 않은 Comment/)).not.toBeInTheDocument()
    // then: 150건은 글자 "99+"이고 접근 이름은 실제 수다
    const capped = within(await rowOf(/푸른물류 SSO 도입/)).getByLabelText('읽지 않은 Comment 150건')
    expect(capped).toHaveTextContent('99+')
  })

  // 상세에서 Comment를 쓰고 목록으로 돌아오면 배지가 새 값이다(목록 캐시 무효화, CM-R44).
  // 테스트 코드: DL-110
  it('shows the new unread count after the user writes a comment on the detail and returns to the list', async () => {
    // given: Deal 1에 읽지 않은 Comment 1건, 박영업이 목록을 연다
    const code = await dealCodeOf(1)
    const { client, user } = await renderAt(ALL_DEALS, { userId: USER_ID.park })
    await rowOf(/한빛은행 ITDR 도입/)
    await seedUnread(client, unread(code, 1))
    expect(await within(await rowOf(/한빛은행 ITDR 도입/)).findByLabelText('읽지 않은 Comment 1건')).toHaveTextContent('1')

    // when: 상세의 Comments 탭에서 Comment를 저장하고 상단 메뉴 Deals로 돌아온다
    await user.click(within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('link', { name: '한빛은행 ITDR 도입' }))
    await user.click(await screen.findByRole('tab', { name: /^Comments/ }))
    await user.type(await screen.findByLabelText('Comment 입력'), '새 Comment')
    await user.click(screen.getByRole('button', { name: '저장' }))
    await waitFor(() => expect(commentItems()).toHaveLength(2))
    // then: 저장 직후 Deal 목록 캐시는 모두 무효화되어 있다(CM-R44)
    await waitFor(() => {
      const lists = client.getQueryCache().findAll({ queryKey: ['deals', 'list'] })
      expect(lists.length).toBeGreaterThan(0)
      expect(lists.every((q) => q.state.isInvalidated)).toBe(true)
    })
    await user.click(screen.getByRole('link', { name: 'Deals' }))

    // then: 돌아온 목록 배지는 "2"다
    expect(await within(await rowOf(/한빛은행 ITDR 도입/)).findByLabelText('읽지 않은 Comment 2건')).toHaveTextContent('2')
  })

  // Owner가 Comments 탭을 열어 읽음 처리하면 돌아온 목록에서 그 배지가 사라진다.
  // 테스트 코드: DL-110
  it('removes the badge on the returned list after the owner opens the Comments tab', async () => {
    // given: Deal 1에 읽지 않은 Comment 1건, Owner 김영업이 목록을 연다
    const code = await dealCodeOf(1)
    const { client, user } = await renderAt(ALL_DEALS, { userId: USER_ID.kim })
    await rowOf(/한빛은행 ITDR 도입/)
    await seedUnread(client, unread(code, 1))
    expect(await within(await rowOf(/한빛은행 ITDR 도입/)).findByLabelText('읽지 않은 Comment 1건')).toBeVisible()

    // when: 상세의 Comments 탭을 열고(읽음 처리) 상단 메뉴 Deals로 돌아온다
    await user.click(within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('link', { name: '한빛은행 ITDR 도입' }))
    await user.click(await screen.findByRole('tab', { name: /^Comments/ }))
    await screen.findByRole('list', { name: 'Comment 목록' })
    await waitFor(() => {
      const lists = client.getQueryCache().findAll({ queryKey: ['deals', 'list'] })
      expect(lists.length).toBeGreaterThan(0)
      expect(lists.every((q) => q.state.isInvalidated)).toBe(true)
    })
    await user.click(screen.getByRole('link', { name: 'Deals' }))

    // then: 돌아온 목록의 그 행에는 배지가 없다
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await waitFor(() => expect(within(row).queryByLabelText(/읽지 않은 Comment/)).not.toBeInTheDocument())
  })
})
