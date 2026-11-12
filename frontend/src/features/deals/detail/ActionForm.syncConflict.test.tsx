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

describe('두 번째 변경이 첫 변경과 충돌', () => {
  // 첫 변경과 충돌하는 두 번째 변경은 대화상자 없이 막는다.
  // 테스트 코드: AC-080
  it('blocks_a_conflicting_second_change_without_a_dialog', async () => {
    // given: 계약완료로 바꾸고 매출을 확정한 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)

    // when: Forecast를 Commit으로 바꾼다
    await user.selectOptions(forecastSelect(form), 'Commit')

    // then: 대화상자 없이 충돌 알림이 보이고 두 칸은 계약완료·Won이다
    expectOnlyActionPopup()
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(statusSelect(form)).toHaveDisplayValue('계약완료')
    expect(forecastSelect(form)).toHaveDisplayValue('Won')
  })

  // 대화상자 답이 첫 변경을 뒤집으면 막는다.
  // 테스트 코드: AC-080
  it('blocks_a_conflicting_choice_after_the_dialog', async () => {
    // given: Lost Deal의 추가 팝업에서 Status를 기술평가로 바꿨다
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    // when: Forecast를 Commit으로 바꾸고 대화상자에서 가격협상을 고른다
    await user.selectOptions(forecastSelect(form), 'Commit')
    await chooseInDialog(user, '가격협상')

    // then: 충돌 알림이 보이고 Status는 기술평가, Forecast는 Lost 그대로다
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Lost')
  })

  // 첫 변경 값을 유지하는 답은 받아들이고 미리 선택되어 있다.
  // 테스트 코드: AC-080
  it('accepts_the_choice_that_keeps_the_first_value_and_preselects_it', async () => {
    // given: Lost Deal의 추가 팝업에서 Status를 기술평가로 바꿨다
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    // when: Forecast를 Commit으로 바꾼다
    await user.selectOptions(forecastSelect(form), 'Commit')

    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    // then: 대화상자에서 기술평가가 미리 선택되어 있다
    expect(within(dialog).getByRole('radio', { name: '기술평가' })).toBeChecked()
    // when: 그대로 확인한다
    await chooseInDialog(user, null)
    // then: 충돌 알림이 없고 기술평가·Commit이다
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })

  // 충돌 알림은 다음 성공한 변경에서 사라진다.
  // 테스트 코드: AC-080
  it('clears_the_conflict_message_on_the_next_successful_change', async () => {
    // given: 계약완료로 바꾸고 매출을 확정한 뒤 Forecast 변경이 막혔다
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    await user.selectOptions(forecastSelect(form), 'Commit')
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)

    // when: Status를 가격협상으로 되돌린다
    await user.selectOptions(statusSelect(form), '가격협상')

    // then: 충돌 알림이 없고 가격협상·Commit이다
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })
})

describe('대화상자 취소와 되돌리기', () => {
  // 대화상자를 취소해도 앞선 변경은 유지된다.
  // 테스트 코드: AC-080
  it('keeps_previous_changes_when_a_dialog_is_cancelled', async () => {
    // given: Lost Deal의 추가 팝업에서 Status를 기술평가로 바꿨다
    const { user, form } = await openRegisterForm(16, '새론병원 SSO')
    await user.selectOptions(statusSelect(form), '기술평가')

    // when: Forecast 변경의 대화상자를 취소한다
    await user.selectOptions(forecastSelect(form), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expectOnlyActionPopup())

    // then: Status 기술평가가 유지되고 Forecast는 Lost 그대로이며 알림이 없다
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Lost')
    expect(within(form).getByText('현재: 가격협상')).toBeVisible()
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
  })

  // 이미 바꾼 칸을 다시 바꾸다 대화상자를 취소하면 두 칸이 모두 되돌려진다.
  // 테스트 코드: AC-080
  it('restores_both_selects_when_the_dialog_of_a_re_chosen_field_is_cancelled', async () => {
    // given: Forecast를 Best로 바꾼 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(forecastSelect(form), 'Best')

    // when: Status를 계약완료로 바꾼다
    await user.selectOptions(statusSelect(form), '계약완료')
    expectOnlyActionPopup()

    // then: Status는 원래 값, Forecast는 Best 그대로이고 충돌 알림이 보인다
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Best')
    expect(await within(form).findByRole('alert')).toHaveTextContent(CONFLICT)
  })

  // 앞 칸을 되돌리면 그 변경과 뒤의 변경이 취소되고 안내한다.
  // 테스트 코드: AC-080
  it('reverting_a_field_cancels_its_change_and_the_later_ones', async () => {
    // given: Status를 기술평가로, Forecast를 Best로 바꾼 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')

    // when: Status를 원래 값으로 되돌린다
    await user.selectOptions(statusSelect(form), '가격협상')

    // then: 두 칸이 원래 값이고 Forecast 변경도 취소되었다는 안내가 보인다
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).getByRole('status')).toHaveTextContent(REVERTED_FORECAST)
    expect(within(form).queryByText(/^현재: /)).not.toBeInTheDocument()
  })

  // 뒤 칸을 되돌리면 앞 변경은 유지되고 안내가 없다.
  // 테스트 코드: AC-080
  it('reverting_the_later_field_keeps_the_earlier_change_and_says_nothing', async () => {
    // given: Status를 기술평가로, Forecast를 Best로 바꾼 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')

    // when: Forecast를 원래 값으로 되돌린다
    await user.selectOptions(forecastSelect(form), 'Commit')

    // then: Status 변경은 유지되고 취소 안내가 없다
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).queryByText(REVERTED_FORECAST)).not.toBeInTheDocument()
    expect(within(form).queryByText(REVERTED_STATUS)).not.toBeInTheDocument()
  })

  // Forecast를 되돌려 뒤의 Status 변경이 취소되면 Status를 알린다.
  // 테스트 코드: AC-080
  it('names_the_status_when_a_forecast_revert_cancels_a_later_status_change', async () => {
    // given: Forecast를 Best로, Status를 기술평가로 바꾼 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '기술평가')

    // when: Forecast를 원래 값으로 되돌린다
    await user.selectOptions(forecastSelect(form), 'Commit')

    // then: Status도 원래 값이고 Status 변경 취소 안내가 보인다
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(within(form).getByRole('status')).toHaveTextContent(REVERTED_STATUS)
  })
})
