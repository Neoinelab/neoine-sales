/** Action 등록 폼(Status·Forecast·유형 3열) 화면 테스트 도우미. 운영 코드에서 쓰지 않는다. */
import { screen, waitFor, within } from '@testing-library/react'
import { expect } from 'vitest'
import { detailPath } from './detailTestUtils'
import { renderAt } from './mockApp'

type User = Awaited<ReturnType<typeof renderAt>>['user']

export const GROUP_NAME = 'Status · Forecast · 유형'
export const CANCEL_BUTTON = 'Status·Forecast 변경 취소'
export const CONFLICT = '먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요.'
export const REVERTED_FORECAST = 'Forecast 변경도 취소되었습니다. 필요하면 다시 선택하세요.'
export const REVERTED_STATUS = 'Status 변경도 취소되었습니다. 필요하면 다시 선택하세요.'

/** Deal 번호(시드 1: 가격협상/Commit, 16: 가격협상/Lost)의 Action 추가 팝업을 열고 그 안의 등록 폼을 돌려준다. */
export async function openRegisterForm(no: number, title: string) {
  const view = await renderAt(await detailPath(no, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
  const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })
  expect(dialog).toHaveAttribute('aria-modal', 'true')
  const form = within(dialog).getByRole('form', { name: 'Action 추가' })
  return { ...view, dialog, form, table }
}

/** 동기화 팝업이 모두 닫히고 Action 추가 팝업 하나만 남았는지 본다(겹친 팝업 중 맨 위만 닫혀야 한다, AC-14). */
export function expectOnlyActionPopup() {
  const dialogs = screen.getAllByRole('dialog')
  expect(dialogs).toHaveLength(1)
  expect(dialogs[0]).toHaveAccessibleName('Action 추가')
}

export async function waitForOnlyActionPopup() {
  await waitFor(expectOnlyActionPopup)
}

export function statusSelect(form: HTMLElement) {
  return within(form).getByLabelText('Status')
}

export function forecastSelect(form: HTMLElement) {
  return within(form).getByLabelText('Forecast')
}

/** 매출 확정 대화상자를 채우고 확정한다. */
export async function confirmRevenue(user: User) {
  const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
  await user.clear(within(dialog).getByLabelText('매출금액(단위:천원, 실제 값)'))
  await user.type(within(dialog).getByLabelText('매출금액(단위:천원, 실제 값)'), '1850000')
  await user.clear(within(dialog).getByLabelText('매출일(실제 값)'))
  await user.type(within(dialog).getByLabelText('매출일(실제 값)'), '2026-11-20')
  await user.click(within(dialog).getByRole('button', { name: '확정' }))
  await waitForOnlyActionPopup()
}

/** 함께 바꿀 값 선택 대화상자에서 라디오를 고르고 확인한다(choice가 null이면 미리 선택된 값 그대로). */
export async function chooseInDialog(user: User, choice: string | null) {
  const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
  if (choice) await user.click(within(dialog).getByRole('radio', { name: choice }))
  await user.click(within(dialog).getByRole('button', { name: '확인' }))
  await waitForOnlyActionPopup()
}

export async function fillContentAndRegister(user: User, form: HTMLElement) {
  await user.type(within(form).getByLabelText('유형'), '미팅')
  await user.type(within(form).getByLabelText('진행사항'), '두 필드 변경 확인')
  await user.type(within(form).getByLabelText('Next Action'), '후속 연락')
  await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')
  await user.click(within(form).getByRole('button', { name: '등록' }))
}
