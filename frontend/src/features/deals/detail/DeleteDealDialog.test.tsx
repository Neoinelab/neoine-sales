import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'

async function openDialog(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
  const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
  return { ...view, dialog }
}

describe('Deal 삭제 팝업 (T-DELETE-01~06)', () => {
  it('states what is deleted together, with the counts, and asks for the deal code', async () => {
    const code = await dealCodeOf(1)
    const { dialog } = await openDialog(1, '한빛은행 ITDR 도입')
    await waitFor(() => expect(dialog).toHaveTextContent(/Deal History \d+건, Action 4건, 파트너 미팅 1건, 첨부 파일 3개/))
    expect(dialog).toHaveTextContent('복구할 수 없습니다')
    expect(dialog).toHaveTextContent(`Deal code ${code}`)
  })

  it('keeps 삭제 disabled until the exact code is typed and explains a mismatch', async () => {
    const code = await dealCodeOf(11)
    const { user, dialog } = await openDialog(11, '청명대학교 SSO/MFA')
    const confirm = within(dialog).getByRole('button', { name: '삭제' })
    expect(confirm).toBeDisabled()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
    const input = within(dialog).getByLabelText('Deal code 확인')
    await user.type(input, code.slice(0, -1))
    expect(confirm).toBeDisabled()
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Deal code가 일치하지 않습니다.')
    await user.type(input, code.slice(-1))
    expect(confirm).toBeEnabled()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not accept the code in lower case', async () => {
    const code = await dealCodeOf(11)
    const { user, dialog } = await openDialog(11, '청명대학교 SSO/MFA')
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code.toLowerCase())
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeDisabled()
  })

  it('deletes the deal with its history, actions and attachments and goes back to the list', async () => {
    const code = await dealCodeOf(1)
    const { user, dialog, location } = await openDialog(1, '한빛은행 ITDR 도입')
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))
    await expect(gateway.deals.get(code)).rejects.toMatchObject({ status: 404 })
    await expect(gateway.actions.list(code, {})).rejects.toMatchObject({ status: 404 })
  })

  it('deletes the partner meetings of the deal with it and keeps the others', async () => {
    const code = await dealCodeOf(1)
    const { user, dialog } = await openDialog(1, '한빛은행 ITDR 도입')
    const before = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)
    expect(before.items.filter((m) => m.deal.code === code)).toHaveLength(1)
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(gateway.deals.get(code)).rejects.toMatchObject({ status: 404 }))
    const after = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)
    expect(after.total).toBe(before.total - 1)
    expect(after.items.some((m) => m.deal.code === code)).toBe(false)
  })

  it('leaves the detail screen right after deleting so no stale deal is shown', async () => {
    const code = await dealCodeOf(11)
    const { user, dialog } = await openDialog(11, '청명대학교 SSO/MFA')
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(screen.queryByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })).not.toBeInTheDocument())
    expect(screen.queryByText('Deal을 찾을 수 없습니다.')).not.toBeInTheDocument()
  })

  it('closes with cancel or Escape without deleting', async () => {
    const code = await dealCodeOf(11)
    const { user, dialog } = await openDialog(11, '청명대학교 SSO/MFA')
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await expect(gateway.deals.get(code)).resolves.toMatchObject({ code })
  })

  it('lets admin delete a deal owned by someone else', async () => {
    const code = await dealCodeOf(3)
    const { user, dialog, location } = await openDialog(3, '미래전자 EDR 교체', 'admin')
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))
  })

  it('rejects a sales user deleting someone else s deal directly through the gateway (403)', async () => {
    const code = await dealCodeOf(3)
    await renderAt(await detailPath(3))
    await expect(gateway.deals.remove(code, code)).rejects.toMatchObject({ status: 403 })
  })
})
