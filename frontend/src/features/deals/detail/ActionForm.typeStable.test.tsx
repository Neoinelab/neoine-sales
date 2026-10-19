import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { detailPath } from '../../../test/detailTestUtils'
import { seedActionTypeId } from '../../../test/fake/seed/actionTypes'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 폼 유형 입력의 안정성(리뷰 후속): 건드리지 않은 유형은 처음 {id}로 전송되고,
 * 유형 목록이 로딩 중이거나 실패했을 때는 "새 유형" 안내 대신 상태에 맞는 표시만 보인다.
 */
afterEach(() => vi.restoreAllMocks())

const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'
const LOAD_ERROR = '유형 목록을 불러오지 못했습니다.'

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

async function openAddForm() {
  const view = await renderAt(await detailPath(1), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
  const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
  return { ...view, form, type: within(form).getByLabelText('유형') }
}

describe('수정 폼에서 건드리지 않은 유형', () => {
  it('is sent as the original id and creates no type when an admin renamed it after the form was opened', async () => {
    const update = vi.spyOn(gateway.actions, 'update')
    const view = await renderAt(await detailPath(1), { role: 'admin' }) // 이름 변경은 admin만
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await view.user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    expect(within(form).getByLabelText('유형')).toHaveDisplayValue('협상')
    const typesBefore = await gateway.actionTypes.list()
    await gateway.actionTypes.rename(seedActionTypeId('협상'), '가격 협상')
    await view.client.invalidateQueries()
    await waitFor(() => expect(view.client.isFetching()).toBe(0))

    await view.user.type(within(form).getByLabelText('진행사항'), ' 추가')
    await view.user.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('form', { name: 'Action 수정' })).not.toBeInTheDocument())
    expect(update.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('협상') })
    const typesAfter = await gateway.actionTypes.list()
    expect(typesAfter).toHaveLength(typesBefore.length)
    expect(typesAfter.map((t) => t.name)).not.toContain('협상')
  })
})

describe('유형 목록이 로딩 중이거나 실패했을 때', () => {
  it('does not hint that a typed type is new while the list is still loading', async () => {
    vi.spyOn(gateway.actionTypes, 'list').mockImplementation(() => new Promise(() => undefined))
    const { user, type } = await openAddForm()

    await user.type(type, '미팅')

    expect(screen.queryByText(HINT)).not.toBeInTheDocument()
  })

  it('shows an error alert instead of the new-type hint when the list cannot be read', async () => {
    vi.spyOn(gateway.actionTypes, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: LOAD_ERROR }),
    )
    const { user, form, type } = await openAddForm()

    await user.type(type, '미팅')

    await waitFor(() => expect(within(form).getByText(LOAD_ERROR).closest('[role="alert"]')).not.toBeNull())
    expect(screen.queryByText(HINT)).not.toBeInTheDocument()
  })
})
