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

describe('저장 요청이 진행 중일 때 대화상자 닫기', () => {
  // 테스트 코드: RS-068
  it('덮어쓰기 요청 중에는 창이 열린 채 취소가 꺼지고 응답 뒤 닫힌다', async () => {
    // given: 편집 화면에서 설계를 바꿔 조회하고 저장 창을 연다, 덮어쓰기 응답을 붙잡는다
    const { user } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '저장')
    const held = holdWrite('update')

    // when: 저장을 누른다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 저장·취소가 꺼지고 Esc로 닫히지 않는다
    await expectLockedWhileBusy(user, dialog)
    // when: 응답을 푼다
    held.release()
    // then: 창이 닫히고 리포트가 revision 2가 된다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
  })

  // 테스트 코드: RS-068
  it('다른 이름으로 저장 요청 중에는 잠기고 응답 뒤 새 리포트로 간다', async () => {
    // given: 다른 이름으로 저장 창을 연다, 만들기 응답을 붙잡는다
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '다른 이름으로 저장')
    const held = holdWrite('create')

    // when: 저장을 누른다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 저장·취소가 꺼지고 Esc로 닫히지 않는다
    await expectLockedWhileBusy(user, dialog)
    // when: 응답을 푼다
    held.release()
    // then: 새 리포트 편집 화면으로 가고 창이 닫힌다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  // 테스트 코드: RS-068
  it('복제 요청 중에는 잠기고 응답 뒤 복제본이 열린다', async () => {
    // given: 목록에서 복제 창을 연다, 복제 응답을 붙잡는다
    const { user, location } = await openList()
    const row = screen.getByText(MINE_PUBLIC.name).closest('tr') ?? screen.getByText(MINE_PUBLIC.name).closest('li')
    await user.click(within(row as HTMLElement).getByRole('button', { name: `${MINE_PUBLIC.name} 메뉴` }))
    const item = screen.queryByRole('menuitem', { name: '복제' }) ?? screen.getByRole('button', { name: '복제' })
    await user.click(item)
    const dialog = await saveDialog()
    const held = holdWrite('copy')

    // when: 저장을 누른다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 저장·취소가 꺼지고 Esc로 닫히지 않는다
    await expectLockedWhileBusy(user, dialog)
    // when: 응답을 푼다
    held.release()
    // then: 복제본 편집 화면으로 간다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
  })

  // 테스트 코드: RS-068
  it('요청이 없을 때는 버튼과 Esc로 취소할 수 있다', async () => {
    // when: 저장 창을 연다
    const { user } = await openEditor(MINE_PUBLIC.id)
    const dialog = await openEditedDialog(user, '저장')

    // then: 취소가 켜져 있다
    expect(cancelButton(dialog)).toBeEnabled()
    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 창이 닫힌다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
