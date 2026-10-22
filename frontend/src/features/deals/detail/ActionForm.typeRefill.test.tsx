import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { seedActionTypeId } from '../../../test/fake/seed/actionTypes'
import { renderAt } from '../../../test/mockApp'

/**
 * 수정 폼을 연 사이 admin이 유형 이름을 바꿔 목록이 재조회될 때(재리뷰 Nit):
 * 건드리지 않은 유형 입력은 현재 이름으로 다시 채워지고 "새 유형" 안내가 없으며, 사용자가 고친 텍스트는 덮어쓰지 않는다.
 */
afterEach(() => vi.restoreAllMocks())

const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

async function openEditForm() {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'admin' }) // 이름 변경은 admin만
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
  const form = screen.getByRole('form', { name: 'Action 수정' })
  expect(within(form).getByLabelText('유형')).toHaveDisplayValue('협상')
  return { ...view, form }
}

async function renameAndRefetch(view: Awaited<ReturnType<typeof openEditForm>>) {
  await gateway.actionTypes.rename(seedActionTypeId('협상'), '가격 협상')
  await view.client.invalidateQueries()
  await waitFor(() => expect(view.client.isFetching()).toBe(0))
}

describe('유형 이름이 바뀐 뒤 목록이 재조회될 때의 수정 폼', () => {
  it('refills an untouched type with the current name', async () => {
    const view = await openEditForm()

    await renameAndRefetch(view)

    await waitFor(() => expect(within(view.form).getByLabelText('유형')).toHaveDisplayValue('가격 협상'))
  })

  it('shows no new-type hint for an untouched type once the list is re-fetched', async () => {
    const view = await openEditForm()

    await renameAndRefetch(view)

    expect(screen.queryByText(HINT)).not.toBeInTheDocument()
  })

  it('still sends the original id and creates no type after the refill', async () => {
    const update = vi.spyOn(gateway.actions, 'update')
    const view = await openEditForm()
    const typesBefore = await gateway.actionTypes.list()
    await renameAndRefetch(view)
    await waitFor(() => expect(within(view.form).getByLabelText('유형')).toHaveDisplayValue('가격 협상'))

    await view.user.type(within(view.form).getByLabelText('진행사항'), ' 추가')
    await view.user.click(within(view.form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 수정' })).not.toBeInTheDocument())
    expect(update.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('협상') })
    expect(await gateway.actionTypes.list()).toHaveLength(typesBefore.length)
  })

  it('keeps text the user already edited instead of overwriting it', async () => {
    const view = await openEditForm()
    const input = within(view.form).getByLabelText('유형')
    await view.user.clear(input)
    await view.user.type(input, '현장 방문')

    await renameAndRefetch(view)

    expect(within(view.form).getByLabelText('유형')).toHaveDisplayValue('현장 방문')
  })
})
