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

describe('Action 등록 폼의 Status · Forecast · 유형 한 줄', () => {
  // 등록 폼에 Status·Forecast·유형이 한 줄에 순서대로 있다.
  // 테스트 코드: AC-074
  it('shows_status_forecast_and_type_in_one_row', async () => {
    // given: sales가 Deal의 추가 팝업을 연다
    const { form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // when: 한 줄 그룹을 읽는다
    const group = within(form).getByRole('group', { name: GROUP_NAME })
    const status = within(group).getByLabelText('Status')
    const forecast = within(group).getByLabelText('Forecast')
    const type = within(group).getByLabelText('유형')
    // then: Status·Forecast가 현재 값이고 Status, Forecast, 유형 순서다
    expect(status).toHaveDisplayValue('가격협상')
    expect(forecast).toHaveDisplayValue('Commit')
    expect(status.compareDocumentPosition(forecast) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(forecast.compareDocumentPosition(type) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('Status와 Forecast를 둘 다 바꿔 등록', () => {
  // Status와 Forecast를 바꾼 순서대로 보내고 알림에 변경 요약이 붙는다.
  // 테스트 코드: AC-079
  it('registers_with_both_status_and_forecast_changed_in_the_order_the_user_changed_them', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // when: Forecast를 Best로, Status를 기술평가로 바꾼다
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '기술평가')
    // then: 바뀐 칸 아래 "현재: <원래 이름>"이 보인다
    expect(within(form).getByText('현재: Commit')).toBeVisible()
    expect(within(form).getByText('현재: 가격협상')).toBeVisible()
    // when: 내용을 채워 등록한다
    await fillContentAndRegister(user, form)

    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    // then: 요청의 statusChanges가 바꾼 순서다
    const sent = create.mock.calls[0]?.[1].statusChanges
    expect(sent?.map((c) => c.change)).toEqual([
      { field: 'forecastKey', value: 'best' },
      { field: 'statusKey', value: 'technical_evaluation' },
    ])
    // then: 알림에 두 변경 요약이 붙는다
    expect(screen.getByText("Action이 등록되었습니다. Status가 '기술평가'로, Forecast가 'Best'로 변경되었습니다.")).toBeVisible()
    // when: Deal 상세 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    // then: 요약 바 Status가 바뀐다
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('기술평가')
  })

  // 두 번째 칸은 첫 변경을 적용한 상태로 판정하고 종결이면 알림에 알린다.
  // 테스트 코드: AC-079
  it('judges_the_second_select_after_the_first_and_reports_a_closing_in_the_message', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // when: Status를 계약완료로 바꾸고 매출을 확정한다
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)

    // then: Forecast가 Won으로 따라 바뀌고 변경 예정 안내가 하나다
    expect(forecastSelect(form)).toHaveDisplayValue('Won')
    expect(within(form).getAllByText(/저장하면 반영됩니다/)).toHaveLength(1)
    expect(within(form).getByText('현재: Commit')).toBeVisible()
    // when: 내용을 채워 등록한다
    await fillContentAndRegister(user, form)
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    // then: 알림에 계약완료와 Won 변경 요약이 붙는다
    expect(screen.getByText("Action이 등록되었습니다. Status가 '계약완료'로, Forecast가 'Won'으로 변경되었습니다.")).toBeVisible()
  })

  // 두 번째 변경은 첫 변경이 함께 바꾼 칸을 바꿀 수 있다.
  // 테스트 코드: AC-079
  it('allows_the_second_change_to_change_a_field_that_was_changed_along_with_the_first', async () => {
    // given: 바른제약 Deal의 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(12, '바른제약 PAM')

    // when: Status를 기술평가로 바꾸고 함께 바꿀 Forecast Commit을 고른 뒤 Forecast를 Best로 바꾼다
    await user.selectOptions(statusSelect(form), '기술평가')
    await chooseInDialog(user, 'Commit')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    await user.selectOptions(forecastSelect(form), 'Best')

    // then: Status 기술평가·Forecast Best이고 충돌 알림이 없다
    expect(statusSelect(form)).toHaveDisplayValue('기술평가')
    expect(forecastSelect(form)).toHaveDisplayValue('Best')
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(within(form).getAllByText(/저장하면 반영됩니다/)).toHaveLength(1)
    // when: 내용을 채워 등록하고 계약 유지를 고른다
    await fillContentAndRegister(user, form)
    await user.click(within(await screen.findByRole('dialog', { name: '라이선스 계약 처리' })).getByRole('button', { name: '유지' }))
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    // then: 요청의 변경 순서가 Status, Forecast다
    expect(create.mock.calls[0]?.[1].statusChanges?.map((c) => c.change)).toEqual([
      { field: 'statusKey', value: 'technical_evaluation' },
      { field: 'forecastKey', value: 'best' },
    ])
  })

  // 아무것도 바꾸지 않으면 statusChanges를 보내지 않는다.
  // 테스트 코드: AC-079
  it('sends_no_status_changes_when_nothing_was_changed', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // when: Status를 바꾸지 않고 등록한다
    await fillContentAndRegister(user, form)

    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    // then: 요청에 statusChanges가 없다
    expect(create.mock.calls[0]?.[1].statusChanges).toBeUndefined()
    // then: 알림은 기본 등록 문구뿐이다
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })
})

describe('Status·Forecast 변경 취소 버튼', () => {
  // 변경 취소 버튼은 두 변경을 모두 되돌린다.
  // 테스트 코드: AC-080
  it('resets_both_changes_with_the_cancel_button', async () => {
    // given: Status·Forecast를 바꾼 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const { user, form, table } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    expect(within(form).queryByRole('button', { name: CANCEL_BUTTON })).not.toBeInTheDocument()

    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')
    // when: Status·Forecast 변경 취소를 누른다
    await user.click(within(form).getByRole('button', { name: CANCEL_BUTTON }))

    // then: 두 칸이 원래 값이고 "현재:" 안내와 버튼이 사라진다
    expect(statusSelect(form)).toHaveDisplayValue('가격협상')
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
    expect(within(form).queryByText(/^현재: /)).not.toBeInTheDocument()
    expect(within(form).queryByRole('button', { name: CANCEL_BUTTON })).not.toBeInTheDocument()
    // when: 등록한다
    await fillContentAndRegister(user, form)
    await waitFor(() => expect(table).toHaveTextContent('두 필드 변경 확인'))
    // then: 요청에 statusChanges가 없다
    expect(create.mock.calls[0]?.[1].statusChanges).toBeUndefined()
  })

  // 변경 취소 버튼은 동기화 알림도 지운다.
  // 테스트 코드: AC-080
  it('also_clears_the_sync_notice', async () => {
    // given: 계약완료로 바꾸고 매출을 확정한 추가 팝업
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')
    await user.selectOptions(statusSelect(form), '계약완료')
    await confirmRevenue(user)
    expect(within(form).getByText(/저장하면 반영됩니다/)).toBeVisible()

    // when: 변경 취소를 누른다
    await user.click(within(form).getByRole('button', { name: CANCEL_BUTTON }))

    // then: 변경 예정 안내가 없고 Forecast는 원래 값이다
    expect(within(form).queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
    expect(forecastSelect(form)).toHaveDisplayValue('Commit')
  })
})

describe('접근성 (리뷰 후속)', () => {
  // 바뀐 칸의 현재 값 안내가 설명으로 연결된다.
  // 테스트 코드: AC-079
  it('links_the_current_value_hint_to_the_changed_select_as_its_description', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // when: Status를 기술평가로 바꾼다
    await user.selectOptions(statusSelect(form), '기술평가')

    // then: Status 칸의 설명이 "현재: 가격협상"이고 Forecast 칸에는 없다
    expect(statusSelect(form)).toHaveAccessibleDescription('현재: 가격협상')
    expect(forecastSelect(form)).not.toHaveAccessibleDescription()
  })

  // 되돌림 메시지를 위한 상태 영역은 처음부터 비어 있는 채로 붙어 있다.
  // 테스트 코드: AC-080
  it('keeps_an_empty_status_live_region_mounted_before_any_revert_message', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, form } = await openRegisterForm(1, '한빛은행 ITDR 도입')

    // then: 상태 영역이 비어 있다
    const region = within(form).getByRole('status')
    expect(region).toBeEmptyDOMElement()

    // when: Status, Forecast를 바꾼 뒤 Status를 원래 값으로 되돌린다
    await user.selectOptions(statusSelect(form), '기술평가')
    await user.selectOptions(forecastSelect(form), 'Best')
    await user.selectOptions(statusSelect(form), '가격협상')

    // then: 같은 영역에 "Forecast 변경도 취소되었습니다."가 나온다
    expect(within(form).getByRole('status')).toBe(region)
    expect(region).toHaveTextContent('Forecast 변경도 취소되었습니다.')
  })
})
