/** Comment 화면 테스트 도우미(운영 코드에서 쓰지 않는다). Deal 1(한빛은행 ITDR 도입, Owner 김영업)을 기준으로 한다. */
import { screen, waitFor, within } from '@testing-library/react'
import { gateway } from '../gateway'
import type { DealAction } from '../shared/model/types'
import { A_INPUT, DEAL1_TITLE, addAction, openActionsTab, type DetailView } from './actionDetail'
import { dealCodeOf } from './detailTestUtils'
import { defaultMock, mockControl } from './fake/default'
import type { CommentSeed } from './fake/types'
import { USER_ID } from './fake/seed/ids'
import { renderAt, type RenderAtOptions } from './mockApp'

/** 서버 시계(Fake)를 고정하는 시각. 시드 Comment의 작성 시각은 이 이전이어야 읽음 시각(`readAt`)이 앞서지 않는다. */
export const COMMENT_NOW = '2026-11-17T10:00:00+09:00'
export const COMMENTS_TAB = { name: /^Comments/ } as const

export type CommentView = Awaited<ReturnType<typeof openDealTab>>

/** Deal 1의 탭을 `tab` 파라미터로 연다(`comments`·`actions`·`info`). 제목이 보일 때까지 기다린다. */
export async function openDealTab(tab: 'comments' | 'actions' | 'info', options: RenderAtOptions & { query?: string } = {}) {
  const { query = '', ...who } = options
  const code = await dealCodeOf(1)
  const params = new URLSearchParams(query)
  if (tab !== 'info') params.set('tab', tab)
  const search = params.toString()
  const view = await renderAt(`/deals/${code}${search === '' ? '' : `?${search}`}`, who)
  await screen.findByRole('heading', { level: 1, name: DEAL1_TITLE })
  return { ...view, code }
}

/** Comment를 직접 넣고 화면 캐시를 새로 읽게 한다. 작성 시각은 서버 시계 이전이어야 한다. */
export async function seedComments(view: { client: DetailView['client'] }, rows: readonly CommentSeed[]) {
  const added = mockControl.addComments(rows)
  await view.client.invalidateQueries()
  await waitFor(() => expect(view.client.isFetching()).toBe(0))
  return added
}

/** 현재 로그인 사용자를 바꿔 같은 화면에서 게이트웨이로 Comment를 만든 뒤 원래 사용자로 돌아온다. */
export async function writeAs(view: { client: DetailView['client'] }, authorId: number, viewerId: number, code: string, body: string, actionId?: number) {
  await defaultMock.signInAs(authorId)
  const created = await gateway.comments.create(code, { body, ...(actionId === undefined ? {} : { actionId }) })
  await defaultMock.signInAs(viewerId)
  await view.client.invalidateQueries()
  await waitFor(() => expect(view.client.isFetching()).toBe(0))
  return created
}

/** Comment 목록(`ul[aria-label="Comment 목록"]`)의 항목 글. */
export const commentList = (scope: HTMLElement | Document = document.body) => within(scope as HTMLElement).getByRole('list', { name: 'Comment 목록' })
export const commentItems = (scope?: HTMLElement) => within(commentList(scope)).getAllByRole('listitem')

/** 문서 CM-060의 두 Comment: KIM의 Deal Comment, 퇴사자(강퇴사)의 Comment(Action 연결은 `actionId`로). */
export function twoComments(code: string, actionId?: number): CommentSeed[] {
  return [
    { dealCode: code, authorId: USER_ID.kim, body: '예산 회의 예정', createdAt: '2026-11-12T09:30:00+09:00', readAt: '2026-11-12T09:30:00+09:00' },
    { dealCode: code, authorId: USER_ID.old, body: '자료 전달\n2차 예정', createdAt: '2026-11-13T14:05:00+09:00', readAt: '2026-11-13T14:05:00+09:00', ...(actionId === undefined ? {} : { actionId }) },
  ]
}

/** Actions 탭에서 Action A(김영업, 수행일 2026-11-10)를 만들고 돌려준다. */
export async function openWithAction(options: { role?: 'sales' | 'admin' | 'user'; userId?: number } = {}): Promise<{ view: DetailView; action: DealAction }> {
  const view = await openActionsTab(options)
  // Action A는 Owner(김영업)가 만든다. 로그인 사용자와 무관하게 만들고 보는 사람으로 돌아온다.
  const viewer = options.userId ?? (options.role === 'admin' ? USER_ID.root : options.role === 'user' ? USER_ID.han : USER_ID.kim)
  const action = await addAction(view, A_INPUT, USER_ID.kim, viewer)
  return { view, action }
}
