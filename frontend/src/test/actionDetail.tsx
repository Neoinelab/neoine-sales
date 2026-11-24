/** Action 상세 팝업 화면 테스트 도우미(운영 코드에서 쓰지 않는다). */
import { screen, waitFor, within } from '@testing-library/react'
import { gateway } from '../gateway'
import type { ActionInput } from '../shared/model/inputs'
import type { DealAction } from '../shared/model/types'
import { dealCodeOf } from './detailTestUtils'
import { defaultMock } from './fake/default'
import { USER_ID } from './fake/seed/ids'
import { renderAt, type TestRole } from './mockApp'

export const DEAL1_TITLE = '한빛은행 ITDR 도입'
export const DETAIL = 'Action 상세'
export const NOTICE_EDIT = '본인 Action 또는 admin만 수정·삭제할 수 있습니다.'
export const NOTICE_DELETE_TITLE = '본인 Action 또는 admin만 삭제할 수 있습니다.'

export type DetailView = Awaited<ReturnType<typeof openActionsTab>>

/** 시드 Deal(번호)의 Actions 탭을 연다. 기본은 김영업(sales). */
export async function openActionsTab(options: { role?: TestRole; userId?: number; no?: number; title?: string } = {}) {
  const { no = 1, title = DEAL1_TITLE, ...who } = options
  const code = await dealCodeOf(no)
  const view = await renderAt(`/deals/${code}?tab=actions`, who)
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table, code }
}

export const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

/** 표에서 그 글(진행사항·Next Action 등)이 든 행. */
export const rowWith = (table: HTMLElement, text: string) => within(table).getByText(text).closest('tr') as HTMLElement

/** 현재 로그인한 사용자(viewer) 대신 다른 사용자가 Action을 만든 뒤 viewer로 돌아오고 목록을 다시 읽는다. */
export async function addAction(
  view: DetailView,
  input: Partial<ActionInput> & { progress?: string },
  by: number = USER_ID.kim,
  viewer: number = USER_ID.kim,
): Promise<DealAction> {
  await defaultMock.signInAs(by)
  const full: ActionInput = { type: { name: '미팅' }, progress: '', nextAction: '', dueDate: null, comment: '', ...input }
  const created = await gateway.actions.create(view.code, full)
  await defaultMock.signInAs(viewer)
  await view.client.invalidateQueries()
  await waitFor(() => expect(view.client.isFetching()).toBe(0))
  return created
}

/** 문서 AC-132의 Action A(김영업, 미팅, 수행일 2026-11-10). */
export const A_INPUT: Partial<ActionInput> = {
  type: { name: '미팅' },
  progress: '킥오프 미팅',
  nextAction: '요구사항 문서 전달',
  dueDate: '2027-01-15',
  actedOn: '2026-11-10',
}

export async function openDetail(view: DetailView, text: string) {
  await view.user.click(within(rowWith(view.table, text)).getByRole('link'))
  return await screen.findByRole('dialog', { name: DETAIL })
}

/** 팝업의 키·값 줄에서 값(dd). 키는 dt 글자와 정확히 같아야 한다. */
export function fieldValue(dialog: HTMLElement, label: string): HTMLElement {
  const dt = Array.from(dialog.querySelectorAll('dt')).find((el) => el.textContent === label)
  const dd = dt?.nextElementSibling
  if (!(dd instanceof HTMLElement)) throw new Error(`${label} 항목이 없습니다.`)
  return dd
}

/** 응답을 기다리게 한 gate. release()를 부르면 풀린다. */
export function makeGate() {
  let release: () => void = () => undefined
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  return { gate, release: () => release() }
}
