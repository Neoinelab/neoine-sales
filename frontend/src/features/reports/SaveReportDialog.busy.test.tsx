// 편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './designer/ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { addCountedColumn, openEditor, openList, runQuery, saveButton, saveDialog, setupReportClock } from '../../test/reportScreen'
import { MINE_PUBLIC } from '../../test/savedReports'

setupReportClock()

type WriteMethod = 'update' | 'create' | 'copy'

/** 저장 요청(update·create·copy)을 `release()`를 부를 때까지 끝나지 않게 붙잡는다. 요청 자체는 release 뒤 Fake가 처리한다. */
function holdWrite(method: WriteMethod): { release: () => void } {
  const reports = gateway.reports as unknown as Record<WriteMethod, (...args: unknown[]) => Promise<unknown>>
  const original = reports[method].bind(reports)
  let release: () => void = () => undefined
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  vi.spyOn(reports, method).mockImplementation(async (...args: unknown[]) => {
    await gate
    return original(...args)
  })
  return { release }
}

const cancelButton = (dialog: HTMLElement) => within(dialog).getByRole('button', { name: '취소' })

async function expectLockedWhileBusy(user: UserEvent, dialog: HTMLElement): Promise<void> {
  await waitFor(() => expect(within(dialog).getByRole('button', { name: '저장' })).toBeDisabled())
  expect(cancelButton(dialog)).toBeDisabled()
  await user.keyboard('{Escape}')
  expect(screen.getByRole('dialog')).toBeVisible()
}

async function openEditedDialog(user: UserEvent, buttonName: '저장' | '다른 이름으로 저장'): Promise<HTMLElement> {
  await addCountedColumn(user, 'Deal code')
  await runQuery(user)
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(screen.getByRole('button', { name: buttonName }))
  return saveDialog()
}

describe('저장 요청이 진행 중일 때 대화상자 닫기 (4단계 재리뷰 Minor)', () => {
  it('keeps the dialog open and cancel disabled while an overwrite is pending, then closes after the response', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '저장')
    const held = holdWrite('update')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await expectLockedWhileBusy(user, dialog)
    held.release()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
  })

  it('keeps the dialog open and cancel disabled while save as is pending, then moves to the new report', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '다른 이름으로 저장')
    const held = holdWrite('create')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await expectLockedWhileBusy(user, dialog)
    held.release()
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('keeps the dialog open and cancel disabled while a copy is pending, then opens the copy', async () => {
    const { user, location } = await openList()
    const row = screen.getByText(MINE_PUBLIC.name).closest('tr') ?? screen.getByText(MINE_PUBLIC.name).closest('li')
    await user.click(within(row as HTMLElement).getByRole('button', { name: `${MINE_PUBLIC.name} 메뉴` }))
    const item = screen.queryByRole('menuitem', { name: '복제' }) ?? screen.getByRole('button', { name: '복제' })
    await user.click(item)
    const dialog = await saveDialog()
    const held = holdWrite('copy')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await expectLockedWhileBusy(user, dialog)
    held.release()
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
  })

  it('lets the user cancel with the button and Esc when no request is pending', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '저장')

    expect(cancelButton(dialog)).toBeEnabled()
    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
