import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  chooseInDialog,
  CONFLICT,
  confirmRevenue,
  forecastSelect,
  openRegisterForm,
  REVERTED_FORECAST,
  REVERTED_STATUS,
  statusSelect,
  expectOnlyActionPopup,
} from '../../../test/actionFormUtils'

describe('두 번째 변경이 첫 변경과 충돌 (AC-16)', () => {
  it('blocks_a_conflicting_second_change_without_a_dialog', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)

    await user.selectOptions(forecastSelect(form), 'Commit')

    expectOnlyActionPopup()
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(statusSelect(form)).toHaveDisplayValue('계약완료')
    expect(forecastSelect(form)).toHaveDisplayValue('Won')
  })

  it('blocks_a_conflicting_choice_after_the_dialog', async () => {
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    await user.selectOptions(forecastSelect(form), 'Commit')
    await chooseInDialog(user, '가격협상')

    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Lost')
  })

  it('accepts_the_choice_that_keeps_the_first_value_and_preselects_it', async () => {
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    await user.selectOptions(forecastSelect(form), 'Commit')

    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    expect(within(dialog).getByRole('radio', { name: '기술평가' })).toBeChecked()
    await chooseInDialog(user, null)
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })

  it('clears_the_conflict_message_on_the_next_successful_change', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    await user.selectOptions(forecastSelect(form), 'Commit')
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)

    await user.selectOptions(statusSelect(form), '가격협상')

    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })
})

describe('대화상자 취소와 되돌리기 (AC-14·17)', () => {
  it('keeps_previous_changes_when_a_dialog_is_cancelled', async () => {
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    await user.selectOptions(forecastSelect(form), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expectOnlyActionPopup())

    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Lost')
    expect(within(form).getByText('현재: 가격협상')).toBeVisible()
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('restores_both_selects_when_the_dialog_of_a_re_chosen_field_is_cancelled', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(forecastSelect(form), 'Best')

    await user.selectOptions(statusSelect(form), '계약완료')
    expectOnlyActionPopup()

    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Best')
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
  })

  it('reverting_a_field_cancels_its_change_and_the_later_ones', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')

    await user.selectOptions(statusSelect(form), '가격협상')

    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).getByRole('status')).toHaveTextContent(REVERTED_FORECAST)
    expect(within(form).queryByText(/^현재: /)).not.toBeInTheDocument()
  })

  it('reverting_the_later_field_keeps_the_earlier_change_and_says_nothing', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')

    await user.selectOptions(forecastSelect(form), 'Commit')

    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).queryByText(REVERTED_FORECAST)).not.toBeInTheDocument()
    expect(within(form).queryByText(REVERTED_STATUS)).not.toBeInTheDocument()
  })

  it('names_the_status_when_a_forecast_revert_cancels_a_later_status_change', async () => {
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '기술평가')

    await user.selectOptions(forecastSelect(form), 'Commit')

    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(within(form).getByRole('status')).toHaveTextContent(REVERTED_STATUS)
  })
})
