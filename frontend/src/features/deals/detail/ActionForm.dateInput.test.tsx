import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { openRegisterForm } from '../../../test/actionFormUtils'

afterEach(() => vi.restoreAllMocks())

async function fill(view: Awaited<ReturnType<typeof openRegisterForm>>, due: string) {
  const { user, form } = view
  await user.type(within(form).getByLabelText('유형'), '미팅')
  await user.type(within(form).getByLabelText('진행사항'), '날짜 입력 확인')
  await user.type(within(form).getByLabelText('Next Action'), '후속 연락')
  if (due !== '') await user.type(within(form).getByLabelText('Due Date'), due)
}

describe('Action 폼의 Due Date 입력 (AC-D3, AC-D7)', () => {
  it('shows yyyy.mm.dd while yyyymmdd is typed and registers with the ISO date', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await fill(view, '20261220')
    expect(within(view.form).getByLabelText('Due Date')).toHaveValue('2026.12.20')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ dueDate: '2026-12-20' })
  })

  it('refuses a non-existing Due Date and shows the message', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await fill(view, '20261340')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    expect(await within(view.form).findByText('없는 날짜입니다.')).toBeVisible()
    expect(within(view.form).getByLabelText('Due Date')).toHaveAttribute('aria-invalid', 'true')
    expect(create).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
  })

  it('refuses a partly typed Due Date', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await fill(view, '2026.12')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    expect(await within(view.form).findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  it('keeps the required message when Next Action has no Due Date', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await fill(view, '')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    expect(await within(view.form).findByText('Due Date를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })
})
