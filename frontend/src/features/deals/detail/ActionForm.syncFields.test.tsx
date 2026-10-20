import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import {
  CANCEL_BUTTON,
  chooseInDialog,
  confirmRevenue,
  fillContentAndRegister,
  forecastSelect,
  GROUP_NAME,
  openRegisterForm,
  statusSelect,
} from '../../../test/actionFormUtils'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Action 등록 폼의 Status · Forecast · 유형 한 줄 (AC-13)', () => {
  it('shows_status_forecast_and_type_in_one_row', async () => {
    const { form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    const group = within(form).getByRole('group', { name: GROUP_NAME })
    const status = within(group).getByLabelText('Status')
    const forecast = within(group).getByLabelText('Forecast')
    const type = within(group).getByLabelText('유형')
    expect(status).toHaveDisplayValue('가격협상')
    expect(forecast).toHaveDisplayValue('Commit')
    expect(status.compareDocumentPosition(forecast) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(forecast.compareDocumentPosition(type) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('keeps_the_edit_form_layout_without_status_or_forecast', async () => {
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.click(within(form).getByRole('button', { name: '취소' }))
    const row = within(table).getAllByRole('row')[2]!
    await user.click(within(row).getByRole('button', { name: '수정' }))

    const edit = screen.getByRole('form', { name: 'Action 수정' })
    expect(within(edit).queryByRole('group', { name: GROUP_NAME })).not.toBeInTheDocument()
    expect(within(edit).queryByLabelText('Status')).not.toBeInTheDocument()
    expect(within(edit).queryByLabelText('Forecast')).not.toBeInTheDocument()
    expect(within(edit).getByLabelText('유형')).toBeVisible()
  })
})

describe('Status와 Forecast를 둘 다 바꿔 등록 (AC-14·15·18·20)', () => {
  it('registers_with_both_status_and_forecast_changed_in_the_order_the_user_changed_them', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '기술평가')
    expect(within(form).getByText('현재: Commit')).toBeVisible()
    expect(within(form).getByText('현재: 가격협상')).toBeVisible()
    await fillContentAndRegister(user, form)

    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    const sent = create.mock.calls[0]?.[1].statusChanges
    expect(sent?.map((c) => c.change)).toEqual([
      { field: 'forecastKey', value: 'best' },
      { field: 'statusKey', value: 'technical_evaluation' },
    ])
    expect(screen.getByText("Action이 등록되었습니다. Status가 '기술평가'로, Forecast가 'Best'로 변경되었습니다.")).toBeVisible()
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('기술평가')
  })

  it('judges_the_second_select_after_the_first_and_reports_a_closing_in_the_message', async () => {
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)

    expect(forecastSelect(form)).toHaveDisplayValue('Won')
    expect(within(form).getAllByText(/저장하면 반영됩니다/)).toHaveLength(1)
    expect(within(form).getByText('현재: Commit')).toBeVisible()
    await fillContentAndRegister(user, form)
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    expect(screen.getByText("Action이 등록되었습니다. Status가 '계약완료'로, Forecast가 'Won'으로 변경되었습니다.")).toBeVisible()
  })

  it('allows_the_second_change_to_change_a_field_that_was_changed_along_with_the_first', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(11, '청명대학교 SSO/MFA')

    await user.selectOptions(statusSelect(form), '기술평가')
    await chooseInDialog(user, 'Commit')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    await user.selectOptions(forecastSelect(form), 'Best')

    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Best')
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(within(form).getAllByText(/저장하면 반영됩니다/)).toHaveLength(1)
    await fillContentAndRegister(user, form)
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    expect(create.mock.calls[0]?.[1].statusChanges?.map((c) => c.change)).toEqual([
      { field: 'statusKey', value: 'technical_evaluation' },
      { field: 'forecastKey', value: 'best' },
    ])
  })

  it('sends_no_status_changes_when_nothing_was_changed', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    await fillContentAndRegister(user, form)

    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    expect(create.mock.calls[0]?.[1].statusChanges).toBeUndefined()
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })
})

describe('Status·Forecast 변경 취소 버튼 (AC-19)', () => {
  it('resets_both_changes_with_the_cancel_button', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    expect(within(form).queryByRole('button', { name: CANCEL_BUTTON })).not.toBeInTheDocument()

    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.click(within(form).getByRole('button', { name: CANCEL_BUTTON }))

    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).queryByText(/^현재: /)).not.toBeInTheDocument()
    expect(within(form).queryByRole('button', { name: CANCEL_BUTTON })).not.toBeInTheDocument()
    await fillContentAndRegister(user, form)
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    expect(create.mock.calls[0]?.[1].statusChanges).toBeUndefined()
  })

  it('also_clears_the_sync_notice', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    expect(within(form).getByText(/저장하면 반영됩니다/)).toBeVisible()

    await user.click(within(form).getByRole('button', { name: CANCEL_BUTTON }))

    expect(within(form).queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })
})

describe('접근성 (리뷰 후속)', () => {
  it('links_the_current_value_hint_to_the_changed_select_as_its_description', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    await user.selectOptions(statusSelect(form), '기술평가')

    expect(statusSelect(form)).toHaveAccessibleDescription('현재: 가격협상')
    expect(forecastSelect(form)).not.toHaveAccessibleDescription()
  })

  it('keeps_an_empty_status_live_region_mounted_before_any_revert_message', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    const region = within(form).getByRole('status')
    expect(region).toBeEmptyDOMElement()

    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '가격협상')

    expect(within(form).getByRole('status')).toBe(region)
    expect(region).toHaveTextContent('Forecast 변경도 취소되었습니다.')
  })
})
