import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { chooseInDialog, fillContentAndRegister, forecastSelect, openRegisterForm } from '../../test/actionFormUtils'
import { dealCodeOf, detailPath } from '../../test/detailTestUtils'
import { defaultMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import { openEdit, save } from './form/testHelpers'
import { rowOf } from './list/testHelpers'

/**
 * Won 해제 시 라이선스 계약 처리 확인 대화상자(AC9). 대화상자 '라이선스 계약 처리':
 * "이 Deal의 라이선스 계약 N건도 삭제할까요?" + 버튼 삭제(위험)/유지/취소. Deal의 license_contract_count가 1 이상일 때만 뜬다.
 * 삭제 -> 요청에 deleteLicenseContracts: true, 유지 -> false, 취소 -> 요청 없음. 기존 동기화 확인('함께 바꿀 값 선택') 뒤, 요청 전에 묻는다.
 * 대상 화면 4곳: Deal 폼 수정(저장 때), 목록 인라인 편집, 상세 요약 바, Action 등록(status_changes가 Won을 벗어날 때).
 * 시드 Won Deal 12번('바른제약 PAM')은 미발급 계약 1건뿐이라 삭제/유지/취소 흐름을, 11번('청명대학교 SSO/MFA', 발급(갱신) 계약)과 24번은 차단 흐름을 시험한다(Fake 시드 요구사항).
 * 발급 상태 계약이 있는 Deal(`hasIssuedLicenseContract`)은 Won 밖으로 바꿀 수 없다(AC29): 동기화 확인 뒤 요청 전에 '확인' 버튼 하나뿐인 안내 대화상자(삭제/유지/취소 없음)가 뜨고 요청을 보내지 않는다.
 * 화면 값이 오래되어 서버가 409를 주면(AC30) 그 문구를 기존 오류 자리에 보이고 편집 상태를 유지한다.
 */
const TITLE = '바른제약 PAM' // 시드 12번: Won, 미발급 계약 1건(삭제/유지/취소 흐름)
const ISSUED_TITLE = '청명대학교 SSO/MFA' // 시드 11번: Won, 발급(갱신) 계약 있음(차단 흐름)
const DIALOG = '라이선스 계약 처리'

afterEach(() => vi.restoreAllMocks())

const exitDialog = () => screen.findByRole('dialog', { name: DIALOG })
const noExitDialog = () => expect(screen.queryByRole('dialog', { name: DIALOG })).not.toBeInTheDocument()

async function contractCountOf(no: number): Promise<number> {
  const code = await dealCodeOf(no)
  await defaultMock.signInAs(USER_ID.root)
  return (await gateway.deals.get(code)).licenseContractCount
}

/** 화면이 열린 뒤 그 Deal의 계약을 모두 지워(admin) 0건 상태로 만든다. */
async function removeContracts(code: string, invalidate: () => Promise<void>): Promise<void> {
  await defaultMock.signInAs(USER_ID.root)
  const page = await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)
  for (const c of page.items.filter((x) => x.dealCode === code)) await gateway.licenseContracts.remove(c.id)
  await invalidate()
}

function expectDialogText(dialog: HTMLElement, count: number) {
  expect(dialog).toHaveTextContent(`이 Deal의 라이선스 계약 ${count}건도 삭제할까요?`)
  expect(within(dialog).getByRole('button', { name: '삭제' })).toBeVisible()
  expect(within(dialog).getByRole('button', { name: '유지' })).toBeVisible()
  expect(within(dialog).getByRole('button', { name: '취소' })).toBeVisible()
}

describe('seed', () => {
  // Fake 시드의 Deal에 이 테스트가 기대하는 계약만 있는지 확인한다.
  it('has exactly the contracts the tests expect on the seed deals', async () => {
    // given: Fake 게이트웨이의 시드 Deal 12번, 11번, 24번
    // when: Deal을 조회한다
    // then: 12번은 계약 1건·발급 없음, 11번과 24번은 발급 계약이 있다
    expect(await contractCountOf(12)).toBe(1)
    const code12 = await dealCodeOf(12)
    await defaultMock.signInAs(USER_ID.root)
    expect((await gateway.deals.get(code12)).hasIssuedLicenseContract).toBe(false)
    for (const no of [11, 24]) {
      const code = await dealCodeOf(no)
      await defaultMock.signInAs(USER_ID.root)
      expect((await gateway.deals.get(code)).hasIssuedLicenseContract, `deal ${no}`).toBe(true)
    }
  })
})

describe('상세 요약 바 (AC9)', () => {
  async function leave(user: UserEvent, bar: HTMLElement) {
    await user.click(within(bar).getByRole('button', { name: 'Forecast 수정' }))
    await user.selectOptions(within(bar).getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
  }
  async function openBar() {
    const view = await renderAt(await detailPath(12), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: TITLE })
    return { ...view, bar: screen.getByRole('region', { name: 'Deal 정보' }) }
  }

  // 상세 요약 바에서 Won을 벗어나 삭제를 누르면 삭제 요청이 간다.
  // 테스트 코드: LC-010
  it('asks after the sync choice and sends deleteLicenseContracts: true for 삭제', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 상세
    const count = await contractCountOf(12)
    const code = await dealCodeOf(12)
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user, bar } = await openBar()

    await leave(user, bar)
    const dialog = await exitDialog()
    expectDialogText(dialog, count)
    expect(apply).not.toHaveBeenCalled()
    // when: Forecast를 Commit으로 바꾸고 동기화 선택 뒤 라이선스 계약 처리 대화상자에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 계약 N건 삭제 문구가 보였고 요청에 deleteLicenseContracts: true가 담기며 계약이 사라진다
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    expect(apply.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: true, change: { field: 'forecastKey', value: 'commit' } })
    await waitFor(() => expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit'))
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)
  })

  // 상세 요약 바에서 유지를 누르면 계약을 남기는 요청이 간다.
  // 테스트 코드: LC-011
  it('sends deleteLicenseContracts: false for 유지 and keeps the contracts', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 상세
    const count = await contractCountOf(12)
    const code = await dealCodeOf(12)
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user, bar } = await openBar()

    await leave(user, bar)
    // when: Forecast를 Commit으로 바꾸고 대화상자에서 유지를 누른다
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))

    // then: 요청에 deleteLicenseContracts: false가 담기고 계약은 남는다
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    expect(apply.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: false })
    await waitFor(() => expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit'))
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(count)
  })

  // 상세 요약 바에서 취소를 누르면 요청하지 않고 Won 그대로다.
  // 테스트 코드: LC-012
  it('sends no request and changes nothing for 취소', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 상세
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user, bar } = await openBar()

    await leave(user, bar)
    // when: Forecast를 Commit으로 바꾸고 대화상자에서 취소를 누른다
    await user.click(within(await exitDialog()).getByRole('button', { name: '취소' }))

    await waitFor(noExitDialog)
    // then: 요청이 가지 않고 Forecast는 Won 그대로다
    expect(apply).not.toHaveBeenCalled()
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Won')
  })

  // 계약이 없으면 상세 요약 바에서 묻지 않고 요청한다.
  // 테스트 코드: LC-013
  it('does not ask when the deal has no contract', async () => {
    // given: 계약을 모두 지운 Won Deal 상세
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user, bar, client } = await openBar()
    await removeContracts(await dealCodeOf(12), () => client.invalidateQueries())

    // when: Forecast를 Commit으로 바꾼다
    await leave(user, bar)

    // then: 대화상자 없이 변경 요청이 간다
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    noExitDialog()
  })
})

describe('목록 인라인 편집 (AC9)', () => {
  const SEARCH = '/deals?q=바른제약'
  async function leave(user: UserEvent, row: HTMLElement) {
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
  }

  // 목록 인라인 편집에서 삭제를 누르면 삭제 요청이 간다.
  // 테스트 코드: LC-010
  it('asks after the sync choice and sends the chosen value', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 행
    const count = await contractCountOf(12)
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/바른제약 PAM/)

    await leave(user, row)
    const dialog = await exitDialog()
    expectDialogText(dialog, count)
    // when: Forecast를 Commit으로 바꾸고 대화상자에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 요청에 deleteLicenseContracts: true가 담기고 행이 Commit으로 바뀐다
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    expect(apply.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: true })
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
  })

  // 목록 인라인 편집에서 취소는 요청 없이, 유지는 false로 요청한다.
  // 테스트 코드: LC-011, LC-012
  it('sends false for 유지 and nothing for 취소', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 행
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/바른제약 PAM/)

    await leave(user, row)
    // when: 취소를 누르고, 다시 바꿔 유지를 누른다
    await user.click(within(await exitDialog()).getByRole('button', { name: '취소' }))
    await waitFor(noExitDialog)
    // then: 취소에는 요청이 없고 유지에는 deleteLicenseContracts: false 요청이 간다
    expect(apply).not.toHaveBeenCalled()

    await leave(user, row)
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    expect(apply.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: false })
  })

  // 계약이 없으면 목록 인라인 편집에서 묻지 않고 요청한다.
  // 테스트 코드: LC-013
  it('does not ask when the deal has no contract', async () => {
    // given: 계약을 모두 지운 Won Deal 행
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user, client } = await renderAt(SEARCH)
    const row = await rowOf(/바른제약 PAM/)
    await removeContracts(await dealCodeOf(12), () => client.invalidateQueries())

    // when: Forecast를 Commit으로 바꾼다
    await leave(user, row)

    // then: 대화상자 없이 변경 요청이 간다
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1))
    noExitDialog()
  })
})

describe('Deal 폼 수정 (AC9)', () => {
  async function leave(user: UserEvent) {
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
  }

  // Deal 폼 수정에서 저장 때 삭제를 누르면 삭제 요청이 간다.
  // 테스트 코드: LC-010
  it('asks when 저장 is pressed and sends deleteLicenseContracts: true for 삭제', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 폼
    const count = await contractCountOf(12)
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openEdit(TITLE)

    await leave(user)
    expect(screen.queryByRole('dialog', { name: DIALOG })).not.toBeInTheDocument()
    await save(user)
    const dialog = await exitDialog()
    expectDialogText(dialog, count)
    expect(update).not.toHaveBeenCalled()
    // when: Forecast를 Commit으로 바꾸고 저장한 뒤 대화상자에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 저장 전에는 묻지 않고, 요청에 deleteLicenseContracts: true가 담긴다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: true, forecastKey: 'commit' })
  })

  // Deal 폼 수정에서 취소는 폼을 남기고 요청하지 않으며 유지는 false로 요청한다.
  // 테스트 코드: LC-011, LC-012
  it('sends false for 유지 and keeps the form and sends nothing for 취소', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal 폼
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openEdit(TITLE)
    await leave(user)

    await save(user)
    // when: 저장 후 취소를 누르고, 다시 저장해 유지를 누른다
    await user.click(within(await exitDialog()).getByRole('button', { name: '취소' }))
    await waitFor(noExitDialog)
    // then: 취소에는 요청이 없고 폼 값이 남으며 유지에는 deleteLicenseContracts: false 요청이 간다
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Commit')

    await save(user)
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: false })
  })

  // Won을 벗어나지 않는 폼 저장은 묻지 않는다.
  // 테스트 코드: LC-013
  it('does not ask when the form does not leave Won', async () => {
    // given: 계약이 있는 Won Deal 폼
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openEdit(TITLE)
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))

    await user.clear(screen.getByLabelText('Deal Name'))
    await user.type(screen.getByLabelText('Deal Name'), `${TITLE} 수정`)
    // when: Deal 이름만 고치고 저장한다
    await save(user)

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    // then: 대화상자 없이 요청이 가고 deleteLicenseContracts는 담기지 않는다
    noExitDialog()
    expect(update.mock.calls[0]?.[1]).not.toHaveProperty('deleteLicenseContracts', true)
  })
})

describe('Action 등록 (AC9)', () => {
  async function leaveAndRegister(no: number) {
    const view = await openRegisterForm(no, TITLE)
    await view.user.selectOptions(forecastSelect(view.form), 'Commit')
    await chooseInDialog(view.user, '기술평가')
    await fillContentAndRegister(view.user, view.form)
    return view
  }

  // Action 등록에서 Won을 벗어나 삭제를 누르면 삭제 요청이 간다.
  // 테스트 코드: LC-010
  it('asks when the status changes leave Won and sends deleteLicenseContracts: true for 삭제', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal의 Action 등록 폼
    const count = await contractCountOf(12)
    const create = vi.spyOn(gateway.actions, 'create')

    const { user } = await leaveAndRegister(12)
    const dialog = await exitDialog()
    expectDialogText(dialog, count)
    expect(create).not.toHaveBeenCalled()
    // when: Forecast를 Commit으로 바꿔 등록하고 대화상자에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 요청에 deleteLicenseContracts: true가 담긴다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: true })
  })

  // Action 등록에서 취소는 요청 없이 폼을 남기고 유지는 false로 요청한다.
  // 테스트 코드: LC-011, LC-012
  it('sends false for 유지 and keeps the form open without a request for 취소', async () => {
    // given: 계약 1건(발급 아님)이 있는 Won Deal의 Action 등록 폼
    const create = vi.spyOn(gateway.actions, 'create')
    const { user } = await leaveAndRegister(12)

    // when: 취소를 누르고, 다시 등록해 유지를 누른다
    await user.click(within(await exitDialog()).getByRole('button', { name: '취소' }))
    await waitFor(noExitDialog)
    // then: 취소에는 요청이 없고 폼이 열려 있으며 유지에는 deleteLicenseContracts: false 요청이 간다
    expect(create).not.toHaveBeenCalled()
    expect(screen.getByRole('form', { name: 'Action 추가' })).toBeVisible()

    await user.click(within(screen.getByRole('form', { name: 'Action 추가' })).getByRole('button', { name: '등록' }))
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ deleteLicenseContracts: false })
  })

  // 상태 변경이 없는 Action 등록은 묻지 않는다.
  // 테스트 코드: LC-013
  it('does not ask when no status change is made', async () => {
    // given: 계약이 있는 Won Deal의 Action 등록 폼
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(12, TITLE)

    // when: 상태를 바꾸지 않고 Action을 등록한다
    await fillContentAndRegister(view.user, view.form)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 대화상자 없이 요청이 가고 deleteLicenseContracts는 담기지 않는다
    noExitDialog()
    expect(create.mock.calls[0]?.[1]).not.toHaveProperty('deleteLicenseContracts', true)
  })
})

const BLOCKED =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'

async function expectBlockedDialog(user: UserEvent): Promise<void> {
  const dialog = await exitDialog()
  expect(dialog).toHaveTextContent(BLOCKED)
  expect(within(dialog).getByRole('button', { name: '확인' })).toBeVisible()
  for (const name of ['삭제', '유지', '취소']) expect(within(dialog).queryByRole('button', { name })).not.toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: '확인' }))
  await waitFor(noExitDialog)
}

describe('발급 계약이 있는 Deal의 Won 이탈 차단 (AC29)', () => {
  // 발급 계약이 있는 Deal은 상세 요약 바에서 안내만 띄우고 요청하지 않는다.
  // 테스트 코드: LC-014
  it('상세 요약 바: 안내만 보이고 요청 없이 값이 Won 그대로다', async () => {
    // given: 발급(갱신) 계약이 있는 Won Deal 상세
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const view = await renderAt(await detailPath(11), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: ISSUED_TITLE })
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    await view.user.click(within(bar).getByRole('button', { name: 'Forecast 수정' }))
    // when: Forecast를 Commit으로 바꾼다
    await view.user.selectOptions(within(bar).getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await view.user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await view.user.click(within(sync).getByRole('button', { name: '확인' }))

    // then: 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없으며 Forecast는 Won 그대로다
    await expectBlockedDialog(view.user)

    expect(apply).not.toHaveBeenCalled()
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Won')
  })

  // 발급 계약이 있는 Deal은 목록 인라인 편집에서 안내만 띄우고 요청하지 않는다.
  // 테스트 코드: LC-014
  it('목록 인라인 편집: 안내만 보이고 요청 없이 값이 Won 그대로다', async () => {
    // given: 발급 계약이 있는 Won Deal 행
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const { user } = await renderAt('/deals?q=청명대학교 SSO')
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    // when: Forecast를 Commit으로 바꾼다
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))

    // then: 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없으며 Forecast는 Won 그대로다
    await expectBlockedDialog(user)

    expect(apply).not.toHaveBeenCalled()
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
  })

  // 발급 계약이 있는 Deal은 폼 저장에서 안내만 띄우고 요청하지 않는다.
  // 테스트 코드: LC-014
  it('Deal 폼 수정: 저장을 누르면 안내만 보이고 요청이 없다', async () => {
    // given: 발급 계약이 있는 Won Deal 폼
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openEdit(ISSUED_TITLE)
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    // when: Forecast를 Commit으로 바꾸고 저장한다
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))

    await save(user)
    // then: 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없다
    await expectBlockedDialog(user)

    expect(update).not.toHaveBeenCalled()
  })

  // 발급 계약이 있는 Deal은 Action 등록에서 안내만 띄우고 요청하지 않는다.
  // 테스트 코드: LC-014
  it('Action 등록: 안내만 보이고 요청이 없다', async () => {
    // given: 발급 계약이 있는 Won Deal의 Action 등록 폼
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(11, ISSUED_TITLE)
    // when: Forecast를 Commit으로 바꿔 등록한다
    await view.user.selectOptions(forecastSelect(view.form), 'Commit')
    await chooseInDialog(view.user, '기술평가')
    await fillContentAndRegister(view.user, view.form)

    // then: 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없다
    await expectBlockedDialog(view.user)

    expect(create).not.toHaveBeenCalled()
  })
})

describe('화면 값이 오래되어 서버가 409를 줄 때 (AC30)', () => {
  /** 화면이 열린 뒤 다른 사용자가 계약을 발급한 것처럼 Fake 서버에서 발급한다(화면은 모르는 상태). */
  async function issueBehindTheScreen(code: string): Promise<void> {
    await defaultMock.signInAs(USER_ID.root)
    const page = await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)
    const target = page.items.find((c) => c.dealCode === code && c.status === 'not_issued')
    if (!target) throw new Error('미발급 계약 없음')
    await gateway.licenseContracts.issue(target.id, {
      start: '2027-01-01',
      term: { amount: 1, unit: 'year' },
      techOwner: '',
      inspection: 'none',
      note: '',
    })
  }

  // 화면 값이 오래돼 서버가 409를 주면 상세 요약 바에 서버 문구를 보인다.
  // 테스트 코드: LC-015
  it('상세 요약 바: 유지를 눌러도 서버 문구가 오류로 보이고 Forecast는 Won 그대로다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal 상세
    const code = await dealCodeOf(12)
    const view = await renderAt(await detailPath(12), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: TITLE })
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    await issueBehindTheScreen(code)
    await view.user.click(within(bar).getByRole('button', { name: 'Forecast 수정' }))
    await view.user.selectOptions(within(bar).getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await view.user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await view.user.click(within(sync).getByRole('button', { name: '확인' }))
    // when: Won 밖으로 바꾸고 유지를 눌러 요청한다
    await view.user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))

    // then: 서버 409 문구가 오류로 보이고 Forecast는 Won 그대로다
    expect(await screen.findByText(BLOCKED)).toBeVisible()
    expect((await gateway.deals.get(code)).forecastKey).toBe('won')
  })

  // 화면 값이 오래돼 서버가 409를 주면 인라인 행의 alert에 서버 문구를 보인다.
  // 테스트 코드: LC-015
  it('목록 인라인 편집: 유지를 눌러도 서버 문구가 행의 alert에 보이고 편집 칸이 남으며 Forecast는 Won 그대로다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal 행
    const code = await dealCodeOf(12)
    const { user } = await renderAt('/deals?q=바른제약')
    const row = await rowOf(/바른제약 PAM/)
    await issueBehindTheScreen(code)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
    // when: Won 밖으로 바꾸고 유지를 눌러 요청한다
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))

    // then: 행의 alert에 서버 문구가 보이고 편집 칸이 남으며 Forecast는 Won 그대로다
    expect(await within(row).findByRole('alert')).toHaveTextContent(BLOCKED)
    expect(within(row).getByLabelText('Forecast 값')).toBeVisible()
    expect((await gateway.deals.get(code)).forecastKey).toBe('won')
  })

  // 폼 저장이 409를 받은 뒤 같은 변경을 다시 저장하면 안내 대화상자가 뜬다.
  // 테스트 코드: LC-015
  it('Deal 폼 수정: 409 뒤 같은 변경을 다시 저장하면 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal 폼
    const code = await dealCodeOf(12)
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openEdit(TITLE)
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    await issueBehindTheScreen(code)
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
    await save(user)
    // when: 유지로 저장해 409를 받고, 같은 변경을 다시 저장한다
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))
    // then: 서버 문구가 보이고, 다시 저장하면 안내 대화상자가 뜨며 요청은 더 가지 않는다
    expect(await screen.findByText(BLOCKED)).toBeVisible()
    expect(update).toHaveBeenCalledTimes(1)

    await save(user)
    await expectBlockedDialog(user)

    expect(update).toHaveBeenCalledTimes(1)
  })

  // 요약 바가 409를 받은 뒤 같은 변경을 다시 시도하면 안내 대화상자가 뜬다.
  // 테스트 코드: LC-015
  it('상세 요약 바: 409 뒤 같은 변경을 다시 시도하면 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal 상세
    const code = await dealCodeOf(12)
    const apply = vi.spyOn(gateway.deals, 'applyChange')
    const view = await renderAt(await detailPath(12), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: TITLE })
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    await issueBehindTheScreen(code)
    const attempt = async () => {
      await view.user.click(within(bar).getByRole('button', { name: 'Forecast 수정' }))
      await view.user.selectOptions(within(bar).getByLabelText('Forecast'), 'Commit')
      const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
      await view.user.click(within(sync).getByRole('radio', { name: '기술평가' }))
      await view.user.click(within(sync).getByRole('button', { name: '확인' }))
    }
    await attempt()
    // when: 유지로 요청해 409를 받고, 같은 변경을 다시 시도한다
    await view.user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))
    // then: 서버 문구가 보이고, 다시 시도하면 안내 대화상자가 뜨며 요청은 더 가지 않는다
    expect(await screen.findByText(BLOCKED)).toBeVisible()
    expect(apply).toHaveBeenCalledTimes(1)

    await view.user.keyboard('{Escape}')
    await attempt()
    await expectBlockedDialog(view.user)

    expect(apply).toHaveBeenCalledTimes(1)
  })

  // 폼 저장이 409면 오류 배너에 서버 문구가 보이고 폼 값이 남는다.
  // 테스트 코드: LC-015
  it('Deal 폼 수정: 서버 문구가 오류 배너에 보이고 폼 값이 남는다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal 폼
    const code = await dealCodeOf(12)
    const { user } = await openEdit(TITLE)
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    await issueBehindTheScreen(code)
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const sync = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(sync).getByRole('radio', { name: '기술평가' }))
    await user.click(within(sync).getByRole('button', { name: '확인' }))
    await save(user)
    // when: Won 밖으로 바꾸고 유지로 저장한다
    await user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))

    // then: 오류 배너에 서버 문구가 보이고 폼 값이 남는다
    expect(await screen.findByText(BLOCKED)).toBeVisible()
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Commit')
  })

  // Action 등록이 409면 서버 문구가 오류로 보이고 등록 팝업이 열려 있다.
  // 테스트 코드: LC-015
  it('Action 등록: 서버 문구가 오류로 보이고 등록 팝업이 열려 있다', async () => {
    // given: 화면에는 발급 계약이 없지만 서버에서는 발급 상태인 Won Deal의 Action 폼
    const code = await dealCodeOf(12)
    const view = await openRegisterForm(12, TITLE)
    await issueBehindTheScreen(code)
    await view.user.selectOptions(forecastSelect(view.form), 'Commit')
    await chooseInDialog(view.user, '기술평가')
    await fillContentAndRegister(view.user, view.form)
    // when: Won 밖으로 바꾸고 유지로 등록한다
    await view.user.click(within(await exitDialog()).getByRole('button', { name: '유지' }))

    // then: 서버 문구가 오류로 보이고 등록 팝업이 남는다
    expect(await screen.findByText(BLOCKED)).toBeVisible()
    expect(screen.getByRole('form', { name: 'Action 추가' })).toBeVisible()
  })
})
