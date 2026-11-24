import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { USER_ID } from '../../../test/fake/seed/ids'
import { ALL_DEALS, rowOf } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

async function setup() {
  const view = await renderAt(ALL_DEALS, { role: 'admin' })
  const row = await rowOf(/한빛은행 ITDR 도입/)
  const deal = (await gateway.deals.list({ keyword: '한빛은행 ITDR' })).items.find((item) => item.name === '한빛은행 ITDR 도입')
  if (!deal?.nextAction) throw new Error('Next Action fixture is missing')
  const action = (await gateway.actions.list(deal.code, {})).find((item) => item.id === deal.nextAction?.actionId)
  if (!action) throw new Error('Action fixture is missing')
  return { ...view, row, deal, action }
}

describe('Deals 목록 Due Date', () => {
  it('shows the Due Date header and saves only the date using the latest action content', async () => {
    const { user, row, deal, action } = await setup()
    expect(screen.getByRole('columnheader', { name: 'Due Date' })).toBeVisible()
    await gateway.actions.update(action.id, { type: { id: action.typeId }, progress: '다른 화면에서 수정한 진행사항', nextAction: action.nextAction ?? '', dueDate: action.dueDate })
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.type(within(row).getByLabelText('Due Date'), '20271225')
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Due Date 수정' })).toHaveTextContent('2027-12-25'))
    const stored = (await gateway.actions.list(deal.code, {})).find((item) => item.id === action.id)
    expect(stored).toMatchObject({ dueDate: '2027-12-25', progress: '다른 화면에서 수정한 진행사항', nextAction: action.nextAction, typeId: action.typeId })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('rejects an empty due date and retains the stored value after cancellation', async () => {
    const { user, row, deal, action } = await setup()
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    expect(await within(row).findByRole('alert')).toHaveTextContent('Due Date를 입력하세요.')
    await user.click(within(row).getByRole('button', { name: 'Due Date 취소' }))
    expect(within(row).getByRole('button', { name: 'Due Date 수정' })).toHaveTextContent(action.dueDate ?? '')
    expect((await gateway.actions.list(deal.code, {})).find((item) => item.id === action.id)?.dueDate).toBe(action.dueDate)
  })

  it('keeps the editor open when the server rejects the update', async () => {
    const { user, row } = await setup()
    vi.spyOn(gateway.actions, 'update').mockRejectedValue(new ApiError(403, { type: 'forbidden', title: 'Forbidden', status: 403, detail: '본인 Action 또는 admin만 수정할 수 있습니다.' }))
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.type(within(row).getByLabelText('Due Date'), '20271225')
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    expect(await within(row).findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 수정할 수 있습니다.')
    expect(within(row).getByLabelText('Due Date')).toHaveValue('2027.12.25')
  })

  it('does not offer due date editing without a Next Action', async () => {
    await renderAt(ALL_DEALS, { role: 'admin', adjustSeed: (data) => ({ ...data, actions: [] }) })
    const deal = (await gateway.deals.list({ limit: 200 })).items.find((item) => item.nextAction === null)
    if (!deal) throw new Error('No-action fixture is missing')
    const row = await rowOf(new RegExp(deal.name))
    expect(within(row).queryByRole('button', { name: 'Due Date 수정' })).not.toBeInTheDocument()
  })

  it('shows a read-only date to users with read-only access', async () => {
    await renderAt(ALL_DEALS, { role: 'user' })
    const row = await rowOf(/한빛은행 ITDR 도입/)
    expect(within(row).queryByRole('button', { name: 'Due Date 수정' })).not.toBeInTheDocument()
  })

  it('cannot change another sales user’s action', async () => {
    const { user } = await renderAt(ALL_DEALS, { role: 'sales', adjustSeed: (data) => ({ ...data, actions: data.actions.map((action) => ({ ...action, actorId: USER_ID.park })) }) })
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const deal = (await gateway.deals.list({ keyword: '한빛은행 ITDR' })).items.find((item) => item.name === '한빛은행 ITDR 도입')
    if (!deal?.nextAction) throw new Error('Next Action fixture is missing')
    const originalDate = deal.nextAction.dueDate
    const actionId = deal.nextAction.actionId
    await user.click(within(row).getByRole('button', { name: 'Due Date 수정' }))
    await user.clear(within(row).getByLabelText('Due Date'))
    await user.type(within(row).getByLabelText('Due Date'), '20271225')
    await user.click(within(row).getByRole('button', { name: 'Due Date 저장' }))
    expect(await within(row).findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 수정할 수 있습니다.')
    expect((await gateway.actions.list(deal.code, {})).find((action) => action.id === actionId)?.dueDate).toBe(originalDate)
  })
})
