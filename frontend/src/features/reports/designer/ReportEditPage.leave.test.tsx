// 저장 뒤 이동하는 편집 화면은 React.lazy 청크이므로 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addCountedColumn, openDesigner, openEditor, runQuery, saveButton, saveDialog, setupReportClock, typeName, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES } from '../../../test/savedReports'

setupReportClock()

const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const LEAVE_TITLE = '저장하지 않은 변경이 있습니다'
const LEAVE_MESSAGE = '저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?'

function unloadIsBlocked(): boolean {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

/** 저장 대화상자를 열어 그대로 저장한다(이름은 바꾸지 않는다). */
async function overwrite(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await runQuery(user)
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(saveButton())
  await user.click(within(await saveDialog()).getByRole('button', { name: '저장' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

describe('편집 화면에서 떠날 때 확인 (AC18, S19)', () => {
  it('asks with the unsaved changes message on the edit page and stays on cancel', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')

    await user.click(menuLink('Deals'))

    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent(LEAVE_MESSAGE)
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11/edit')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('leaves the edit page after the leave button', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(menuLink('Deals'))

    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
  })

  it('asks on the new page with the same message', async () => {
    const { user } = await openDesigner()
    await addCountedColumn(user, 'Deal code')

    await user.click(menuLink('Reports'))

    expect(await screen.findByRole('dialog', { name: LEAVE_TITLE })).toHaveTextContent(LEAVE_MESSAGE)
  })

  it('leaves without asking when nothing changed', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('leaves without asking after the change was undone', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('blocks the unload only while the edit page has unsaved changes', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    expect(unloadIsBlocked()).toBe(false)

    await addCountedColumn(user, 'Deal code')
    expect(unloadIsBlocked()).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))
    expect(unloadIsBlocked()).toBe(false)
  })

  it('does not ask right after an overwrite', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await overwrite(user)
    expect(unloadIsBlocked()).toBe(false)

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not ask right after a revert', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))
    expect(unloadIsBlocked()).toBe(false)

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not ask right after the first save of a new report', async () => {
    const { user, location } = await openDesigner({ savedReports: SAVED_SAMPLES })
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '떠나기 시험')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await screen.findByRole('heading', { level: 1, name: '떠나기 시험' })
    expect(unloadIsBlocked()).toBe(false)

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
