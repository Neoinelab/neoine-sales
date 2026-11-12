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

describe('Action 폼의 Due Date 입력', () => {
  // yyyymmdd로 치면 yyyy.mm.dd로 보이고 ISO 날짜로 등록한다.
  // 테스트 코드: AC-076
  it('shows yyyy.mm.dd while yyyymmdd is typed and registers with the ISO date', async () => {
    // given: sales가 추가 팝업을 열고(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    // when: Due Date에 "20261220"을 쳐 입력을 채운다
    await fill(view, '20261220')
    // then: 칸에 "2026.12.20"이 보인다
    expect(within(view.form).getByLabelText('Due Date')).toHaveValue('2026.12.20')
    // when: 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 요청의 dueDate가 ISO 날짜다
    expect(create.mock.calls[0]?.[1]).toMatchObject({ dueDate: '2026-12-20' })
  })

  // 없는 날짜는 문구로 막고 요청하지 않는다.
  // 테스트 코드: AC-076
  it('refuses a non-existing Due Date and shows the message', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    // when: 없는 날짜 "20261340"을 입력하고 등록을 누른다
    await fill(view, '20261340')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    // then: "없는 날짜입니다." 문구와 오류 표시가 있다
    expect(await within(view.form).findByText('없는 날짜입니다.')).toBeVisible()
    expect(within(view.form).getByLabelText('Due Date')).toHaveAttribute('aria-invalid', 'true')
    // then: 요청이 없고 팝업은 열려 있다
    expect(create).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
  })

  // 덜 친 날짜는 막는다.
  // 테스트 코드: AC-076
  it('refuses a partly typed Due Date', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    // when: 덜 친 날짜 "2026.12"를 입력하고 등록을 누른다
    await fill(view, '2026.12')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    // then: yyyymmdd 안내 문구가 보이고 요청이 없다
    expect(await within(view.form).findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  // Next Action이 있는데 Due Date가 비면 필수 문구가 나온다.
  // 테스트 코드: AC-075
  it('keeps the required message when Next Action has no Due Date', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, '한빛은행 ITDR 도입')
    // when: Due 없이 입력을 채우고 등록을 누른다
    await fill(view, '')
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    // then: Due Date 필수 문구가 보이고 요청이 없다
    expect(await within(view.form).findByText('Due Date를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })
})
