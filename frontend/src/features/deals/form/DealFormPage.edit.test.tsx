import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, openEdit, openList, pickPerson, save } from './testHelpers'

describe('Deal 수정 (T-FORM-06)', () => {
  // 수정 폼은 Deal의 모든 값을 채운다.
  // 테스트 코드: DE-100
  it('loads every value of the deal into the form', async () => {
    // when: 기존 Deal의 수정 화면을 연다.
    await openEdit('누리통신 MFA')
    // then: 이름·Owner·Vendor·Product·고객·파트너·Status·Forecast·금액이 현재 값으로 채워진다.
    expect(screen.getByLabelText('Deal Name')).toHaveValue('누리통신 MFA')
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('이영업'))
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Silverfort'))
    expect(screen.getByLabelText('Product')).toHaveValue('MFA')
    expect(screen.getByLabelText('고객 회사명')).toHaveValue('누리통신')
    expect(screen.getByLabelText('고객 담당자명')).toHaveValue('배성훈')
    expect(screen.getByLabelText('고객 직급')).toHaveValue('과장')
    expect(screen.getByLabelText('파트너 회사명')).toHaveValue('에이원시스템')
    expect(screen.getByLabelText('파트너 담당자명')).toHaveValue('표성호')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('POC준비'))
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Best')
    expect(screen.getByLabelText('금액(단위:원)')).toHaveValue('330,000,000')
  })

  // 수정을 저장하면 상세로 간다.
  // 테스트 코드: DE-100
  it('saves edits and goes to the detail page', async () => {
    // given: 수정 화면이 열려 있다.
    const { user, location, code } = await openEdit('대한제조 NGFW')
    const name = screen.getByLabelText('Deal Name')
    // when: 이름을 고쳐 저장한다.
    await user.clear(name)
    await user.type(name, '대한제조 NGFW 확장')
    await save(user)
    // then: 그 Deal 상세 주소로 이동한다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
  })

  // 다른 파트너를 입력하면 교체 안내 후 저장된다.
  // 테스트 코드: DE-101
  it('shows a replacement notice for another partner and saves the replacement', async () => {
    // given: 활성 파트너가 있는 Deal의 수정 화면이다.
    const { user, location } = await openEdit('누리통신 MFA')
    expect(screen.queryByText(/이력으로 남고 비활성이 됩니다/)).not.toBeInTheDocument()
    // when: 다른 파트너를 고른다.
    await pickPerson(user, '파트너', '코어테크', /민지훈/)
    // then: 교체 안내가 보인다.
    expect(
      await screen.findByText('기존 활성 파트너(에이원시스템 표성호)는 이력으로 남고 비활성이 됩니다.'),
    ).toBeVisible()

    // when: 저장한다.
    await save(user)
    // then: 상세로 이동한다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    // when: 목록에서 그 Deal의 빠른 보기를 연다.
    const row = await openList(user, '누리통신 MFA')
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    // then: 새 파트너만 보인다.
    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText(/민지훈/)).toBeVisible()
    expect(within(view).queryByText(/표성호/)).not.toBeInTheDocument()
  })

  // '파트너 제거'로 활성 파트너를 제거한다.
  // 테스트 코드: DE-101
  it('removes the active partner with the remove button', async () => {
    // given: 활성 파트너가 있는 Deal의 수정 화면이다.
    const { user, location } = await openEdit('누리통신 MFA')
    // when: 파트너 제거를 누르고 저장한다.
    await user.click(screen.getByRole('button', { name: '파트너 제거' }))
    expect(screen.getByLabelText('파트너 회사명')).toHaveValue('')
    expect(
      await screen.findByText('저장하면 기존 활성 파트너(에이원시스템 표성호)가 제거되고 이력으로 남습니다.'),
    ).toBeVisible()
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const row = await openList(user, '누리통신 MFA')
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText('파트너 없음')).toBeVisible()
  })

  // 퇴사한 Owner는 보이지만 다른 Owner를 고를 때까지 저장되지 않는다.
  // 테스트 코드: DE-102
  it('keeps a resigned owner visible but refuses to save until another owner is picked', async () => {
    // given: Owner가 퇴사한 Deal의 수정 화면이다.
    const { user, location } = await openEdit('한빛은행 PAM')
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('강퇴사(퇴사)'))
    // when: 그대로 저장한다.
    await save(user)
    // then: 퇴사 문구가 나오고 수정 화면에 머문다.
    expect(
      await screen.findByText('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.'),
    ).toBeVisible()
    expect(location()).toMatch(/\/edit$/)

    // when: 재직 Owner를 골라 다시 저장한다.
    await user.selectOptions(screen.getByLabelText('Owner'), '김영업')
    await save(user)
    // then: 상세로 간다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
  })

  // 종결된 Deal도 수정 폼으로 저장된다.
  // 테스트 코드: DE-103
  it('lets a closed deal be edited as well', async () => {
    // given: Forecast가 Won인 Deal의 수정 화면이다.
    const { user, location, code } = await openEdit('청명대학교 SSO/MFA')
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    // when: 구매절차를 고쳐 저장한다.
    await user.type(screen.getByLabelText('구매절차'), ' 추가 메모')
    await save(user)
    // then: 상세로 이동한다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
  })

  // 저장이 실패하면 서버 문구를 보이고 폼에 머문다.
  // 테스트 코드: DE-104
  it('shows the server message and stays on the form when saving fails', async () => {
    // when: 다른 사람과 겹치는 이메일로 고쳐 저장한다.
    const { user, location } = await openEdit('누리통신 MFA')
    const email = screen.getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'bae1@nuri.test')
    await save(user)
    // then: '이미 등록된 연락처입니다.'가 나오고 수정 화면에 머물며 저장 버튼이 다시 활성이다.
    expect(await screen.findByText('이미 등록된 연락처입니다.')).toBeVisible()
    expect(location()).toMatch(/\/edit$/)
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })

  // 없는 code의 수정 화면은 오류 문구와 '목록으로'를 보인다.
  // 테스트 코드: DE-105
  it('shows the not-found message and a way back for an unknown code', async () => {
    // when: 없는 code의 수정 화면을 연다.
    await renderAt('/deals/20000101-ZZZZ/edit')
    // then: 'Deal을 찾을 수 없습니다.'와 '목록으로' 링크가 보인다.
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: '목록으로' })).toHaveAttribute('href', '/deals')
  })

  // 취소하면 수정은 상세로 간다.
  // 테스트 코드: DE-106
  it('goes back to the detail page when cancelled', async () => {
    // given: 수정 화면이 열려 있다.
    const { user, location, code } = await openEdit('대한제조 NGFW')
    // when: 취소를 누른다.
    await user.click(screen.getByRole('button', { name: '취소' }))
    // then: 그 Deal 상세로 이동한다.
    expect(location()).toBe(`/deals/${code}`)
  })
})

describe('Status⇄Forecast 동기화 (T-SYNC-UI, 폼)', () => {
  // Status를 계약완료로 바꾸면 매출 확인 뒤 Forecast가 Won이 되고 저장 전임을 알린다.
  // 테스트 코드: DE-107
  it('asks for revenue on 계약완료, then sets Forecast to Won and tells it is not saved yet', async () => {
    // given: 기술평가 Status의 수정 화면이다.
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    // when: Status를 계약완료로 바꾸고 매출 확정 대화상자에서 확정한다.
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    // then: Forecast가 Won이고 '아직 저장되지 않았다' 안내가 보인다.
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won')
    expect(await screen.findByText(/함께 변경됩니다\. 저장하면 반영됩니다\./)).toBeVisible()
  })

  // 확정한 매출값이 폼 칸에 들어간다.
  // 테스트 코드: DE-107
  it('puts the confirmed revenue into the form fields', async () => {
    // given: 기술평가 Status의 수정 화면이다.
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    // when: Forecast를 Won으로 바꾸고 동기화 대화상자에서 금액·날짜를 확정한다.
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const amount = within(dialog).getByLabelText('매출금액(단위:원, 실제 값)')
    await user.clear(amount)
    await user.type(amount, '400000000')
    fireEvent.change(within(dialog).getByLabelText('매출일(실제 값)'), { target: { value: '2026-12-01' } })
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    // then: 폼의 금액·Expected Close 칸이 확정값이다.
    expect(screen.getByLabelText('금액(단위:원)')).toHaveValue('400,000,000')
    expect(screen.getByLabelText('Expected Close')).toHaveValue('2026.12.01')
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  // 대화상자를 취소하면 이전 값 그대로다.
  // 테스트 코드: DE-107
  it('keeps the old Status when the revenue dialog is cancelled', async () => {
    // given: 기술평가 Status의 수정 화면이다.
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    // when: Status를 계약완료로 바꾸고 동기화 대화상자를 취소한다.
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    // then: Status가 이전 값이다.
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Most Likely')
    expect(screen.queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
  })

  // Won Deal의 Forecast를 바꾸면 Status를 고르게 한다.
  // 테스트 코드: DE-107
  it('makes the user choose a Status when a Won deal gets another Forecast', async () => {
    // given: Won Deal의 수정 화면이다.
    const { user } = await openEdit('청명대학교 SSO/MFA')
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    // when: Forecast를 Won이 아닌 값으로 바꾼다.
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    // then: '확인'이 꺼진 Status 선택 대화상자가 뜬다.
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()

    // when: 기술평가를 고르고 확인한다.
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    // then: Status는 기술평가, Forecast는 Commit이다.
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Commit')
  })

  // 동기화한 값을 저장하면 목록에 반영된다.
  // 테스트 코드: DE-107
  it('saves the synchronized values and the list shows them', async () => {
    // given: 기술평가 Status의 수정 화면이다.
    const { user, location } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    // when: 동기화를 확정하고 저장한다.
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await user.click(within(await screen.findByRole('dialog', { name: '매출 확정' })).getByRole('button', { name: '확정' }))
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(await screen.findByRole('button', { name: 'Status 수정' })).toHaveTextContent('계약완료')
    const row = await openList(user, '대한제조 MFA')
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
  })

  // 새 Deal을 Won으로 고르면 매출 확인을 묻는다.
  // 테스트 코드: DE-107
  it('asks for revenue on a new deal chosen as Won', async () => {
    // given: Deal 등록 화면이다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    const forecast = screen.getByLabelText('Forecast')
    await within(forecast).findByRole('option', { name: 'Won' })
    // when: Forecast를 Won으로 고른다.
    await user.selectOptions(forecast, 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    // then: 매출 확인 대화상자가 뜬다.
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeDisabled()
  })
})
