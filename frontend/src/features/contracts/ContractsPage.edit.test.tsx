import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { LicenseContract } from '../../shared/model/types'
import { allContracts, isIssued } from '../../test/licenseContracts'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'
import { INSPECTION_LABELS } from './contractLabels'

/** 계약관리 수정·첨부·만료 색(B1~B8, 실제 API). Deal에서 오는 5칸은 읽기 전용이다. 시계는 2027-03-15 고정. */
const PAGE = '/contracts'
const LOAD = { timeout: 8000 }

let contracts: LicenseContract[] = []
beforeEach(async () => {
  pinClock()
  contracts = await allContracts()
})
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

const table = () => screen.getByRole('table', { name: '계약 목록' })
const rows = () => within(table()).getAllByRole('row').slice(1)
/** 같은 Deal에 갱신 이력이 있으면 코드가 겹치므로 상태까지 같이 본다. */
const rowOf = (c: LicenseContract) => rows().find((r) => within(r).getAllByRole('cell')[0]?.textContent === c.dealName)!
const cellsOf = (c: LicenseContract) => within(rowOf(c)).getAllByRole('cell')
const dialog = (name: string) => screen.findByRole('dialog', { name })

/** 한 쪽(50건)에 보이고 Deal 코드가 유일한 계약 하나를 고른다. */
function pick(match: (c: LicenseContract) => boolean = () => true): LicenseContract {
  const shown = contracts.slice(0, 50)
  const found = shown.find((c) => match(c) && shown.filter((x) => x.dealName === c.dealName).length === 1)
  if (!found) throw new Error('조건에 맞는 계약이 첫 쪽에 없다')
  return found
}

async function open() {
  const view = await renderAt(PAGE)
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await waitFor(() => expect(rows().length).toBeGreaterThan(0), LOAD)
  return view
}

async function openEdit(c: LicenseContract, role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderAt(PAGE, { role })
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await waitFor(() => expect(rows().length).toBeGreaterThan(0), LOAD)
  await view.user.click(cellsOf(c)[1]!)
  return { ...view, dlg: await dialog(`계약 수정 - ${c.dealName}`) }
}

function file(name: string, size = 10, type = 'application/pdf'): File {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: size })
  return f
}

describe('행 클릭 -> 계약 수정 (B1, AC11)', () => {
  // 행을 클릭하면 계약 수정 대화상자가 열리고 Deal 정보는 읽기 전용, 계약 칸은 편집 가능하다.
  // 테스트 코드: LC-036
  it('opens 계약 수정 with the Deal values read-only and the contract fields editable', async () => {
    // given: sales로 연 계약 목록
    const c = pick((x) => x.vendor !== null && x.partner !== null)
    const { dlg } = await openEdit(c)

    const dealValues = within(dlg).getByRole('group', { name: 'Deal 정보' })
    // when: 행을 클릭한다
    for (const [label, value] of [
      ['고객사명', c.customer],
      ['Vendor', c.vendor!.name],
      ['제품명', c.product],
      ['파트너사', c.partner!],
      ['담당영업', c.salesOwner.name],
    ] as const) {
      expect(within(dealValues).getByText(label)).toBeVisible()
      expect(within(dealValues).getByText(value)).toBeVisible()
      // 속성 이름과 값은 한 항목(같은 줄) 안에 함께 있다
      expect(within(dealValues).getByText(label).parentElement).toHaveTextContent(value)
      expect(within(dlg).queryByRole('textbox', { name: label })).not.toBeInTheDocument()
      expect(within(dlg).queryByRole('combobox', { name: label })).not.toBeInTheDocument()
    }
    // then: 제목 계약 수정 - Deal명, Deal 정보 5칸은 글자, 세 계약 칸은 입력 칸이다
    expect(within(dlg).getByLabelText('기술담당')).toHaveValue(c.techOwner)
    expect(within(dlg).getByLabelText('Note')).toHaveValue(c.note)
    expect(within(dlg).getByRole('combobox', { name: '점검주기' })).toHaveDisplayValue(INSPECTION_LABELS[c.inspection])
    expect(within(dlg).queryByText(`Deal ${c.dealCode}`)).not.toBeInTheDocument()
    expect(within(dlg).getByRole('button', { name: '저장' })).toBeVisible()
    expect(within(dlg).getByRole('button', { name: '취소' })).toBeVisible()
  })

  // 행에 포커스하고 Enter를 눌러도 대화상자가 열린다.
  // 테스트 코드: LC-036
  it('opens the dialog from the keyboard with Enter on the focused row', async () => {
    // given: sales로 연 계약 목록
    const c = pick()
    // when: 행에 포커스하고 Enter를 누른다
    await open()

    rowOf(c).focus()
    // then: 계약 수정 대화상자가 열린다
    expect(rowOf(c)).toHaveFocus()
    await userEvent.keyboard('{Enter}')

    expect(await dialog(`계약 수정 - ${c.dealName}`)).toBeVisible()
  })

  // 미발급 행의 상태 칸을 눌러도 수정 대화상자가 열리고 표에는 버튼이 없다.
  // 테스트 코드: LC-036
  it('opens the edit dialog when the status cell of a not-issued row is clicked (no button in the table)', async () => {
    // given: 미발급 계약이 있는 목록
    const c = pick((x) => x.status === 'not_issued')
    const { user } = await open()

    // when: 상태 칸을 클릭한다
    await user.click(cellsOf(c)[7]!)

    // then: 수정 대화상자가 열린다
    expect(await dialog(`계약 수정 - ${c.dealName}`)).toBeVisible()
    expect(within(rowOf(c)).queryAllByRole('button')).toHaveLength(0)
  })
})

describe('계약 수정 저장 (B2, AC11)', () => {
  // 계약 칸을 저장하면 PUT으로 가고 표에 반영되며 알림이 보인다.
  // 테스트 코드: LC-036
  it('saves the contract fields through PUT and shows them in the table with the notice', async () => {
    // given: sales로 연 계약 수정 대화상자
    const c = pick()
    const update = vi.spyOn(gateway.licenseContracts, 'update')
    const { user, dlg } = await openEdit(c)

    await user.clear(within(dlg).getByLabelText('기술담당'))
    await user.type(within(dlg).getByLabelText('기술담당'), '새기술담당')
    await user.clear(within(dlg).getByLabelText('Note'))
    await user.type(within(dlg).getByLabelText('Note'), '수정된 메모')
    await user.selectOptions(within(dlg).getByRole('combobox', { name: '점검주기' }), INSPECTION_LABELS.monthly)
    // when: 기술담당·점검주기·Note를 고치고 저장한다
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    // then: 대화상자가 닫히고 계약을 수정했습니다 알림과 표의 새 값이 보인다
    expect(await screen.findByText('계약을 수정했습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(c.id, { techOwner: '새기술담당', inspection: 'monthly', note: '수정된 메모' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /^계약 수정/ })).not.toBeInTheDocument())
    await waitFor(() => expect(cellsOf(c)[9]).toHaveTextContent('새기술담당'))
    expect(cellsOf(c)[10]).toHaveTextContent(INSPECTION_LABELS.monthly)
    expect(cellsOf(c)[11]).toHaveTextContent('수정된 메모')
    expect(cellsOf(c)[1]).toHaveTextContent(c.customer)
  })

  // 수정 요청에는 Deal 칸이 없고 Deal 칸을 요구하지도 않는다.
  // 테스트 코드: LC-036
  it('does not send the Deal columns and does not require them', async () => {
    // given: 계약 수정 대화상자
    const c = pick()
    const update = vi.spyOn(gateway.licenseContracts, 'update')
    const { user, dlg } = await openEdit(c)

    // when: 저장한다
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    // then: 요청이 세 계약 칸만 담는다
    expect(await screen.findByText('계약을 수정했습니다.')).toBeVisible()
    expect(Object.keys(update.mock.calls[0]![1]).sort()).toEqual(['inspection', 'note', 'techOwner'])
  })

  // 서버가 거절하면 대화상자 안에 문구를 보이고 닫지 않는다.
  // 테스트 코드: LC-037
  it('shows the server message and keeps the dialog open when the server refuses (422)', async () => {
    // given: 서버가 수정에 422를 주도록 준비한 계약
    const c = pick()
    const { user, dlg } = await openEdit(c)

    await user.click(within(dlg).getByLabelText('기술담당'))
    await user.paste('가'.repeat(101))
    // when: 저장한다
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    // then: 대화상자 안 alert에 서버 문구가 보이고 대화상자는 열려 있다
    expect(await within(dlg).findByRole('alert')).toBeVisible()
    expect(screen.getByRole('dialog', { name: /^계약 수정/ })).toBeVisible()
    expect(screen.queryByText('계약을 수정했습니다.')).not.toBeInTheDocument()
  })

  // 취소하면 편집한 값을 버린다.
  it('discards the edits on 취소', async () => {
    // given: 값을 고친 계약 수정 대화상자
    const c = pick()
    const { user, dlg } = await openEdit(c)

    await user.clear(within(dlg).getByLabelText('기술담당'))
    await user.type(within(dlg).getByLabelText('기술담당'), '버려질이름')
    await user.click(within(dlg).getByRole('button', { name: '취소' }))

    // when: 취소를 누른다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // then: 다시 열면 원래 값이다
    expect(cellsOf(c)[9]).not.toHaveTextContent('버려질이름')
    expect(screen.queryByText('계약을 수정했습니다.')).not.toBeInTheDocument()
  })

  // user에게는 저장 버튼이 없다.
  // 테스트 코드: LC-038
  it('shows no save button for a read-only user', async () => {
    // given: user로 연 계약 수정 대화상자
    const c = pick()
    // when: 대화상자를 연다
    const { dlg } = await openEdit(c, 'user')

    // then: 저장 버튼이 없다
    expect(within(dlg).queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
    expect(within(dlg).getByLabelText('기술담당')).toBeDisabled()
  })
})

describe('첨부 파일 (B6, AC20)', () => {
  const withFiles = () => pick((c) => c.attachmentCount > 0)
  const clean = () => pick((c) => c.attachmentCount === 0)
  const filesOf = (c: LicenseContract) => gateway.licenseContracts.attachments.list(c.id)

  async function upload(dlg: HTMLElement, f: File, description = '') {
    const user = userEvent.setup()
    await user.upload(within(dlg).getByLabelText('파일'), f)
    if (description) await user.type(within(dlg).getByLabelText('설명'), description)
    await user.click(within(dlg).getByRole('button', { name: '업로드' }))
  }

  // 첨부 파일 영역에 서버의 기존 첨부 목록이 보인다.
  // 테스트 코드: LC-070
  it('has a 첨부 파일 area and lists the contract files from the server', async () => {
    // given: 서버에 첨부가 있는 계약
    const c = withFiles()
    const expected = await filesOf(c)
    // when: 계약 수정 대화상자를 연다
    const { dlg } = await openEdit(c)

    // then: 첨부 파일 영역에 서버 목록이 보인다
    expect(within(dlg).getByText('첨부 파일')).toBeVisible()
    for (const a of expected) expect(await within(dlg).findByRole('button', { name: a.fileName })).toBeVisible()
  })

  // 파일을 올리면 알림과 함께 목록에 보이고 다시 열어도 보인다.
  // 테스트 코드: LC-070
  it('uploads a file through the gateway, lists it, and still lists it after reopening', async () => {
    // given: sales로 연 계약 대화상자
    const c = clean()
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { user, dlg } = await openEdit(c)

    // when: 파일을 고르고 업로드를 누른다
    await upload(dlg, file('제안서.pdf', 2048), '제안서 초안')

    // then: 업로드되었습니다 알림, 목록에 파일이 보이고 다시 열어도 보인다
    expect(await within(dlg).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
    expect(send.mock.calls[0]?.[0]).toBe(c.id)
    expect(send.mock.calls[0]?.[1]).toMatchObject({ description: '제안서 초안', onExists: 'ask' })
    await user.click(within(dlg).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(cellsOf(c)[0]).toBeVisible())
    await user.click(cellsOf(c)[1]!)
    expect(await within(await dialog(`계약 수정 - ${c.dealName}`)).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
  })

  // 실행 파일은 요청 없이 Deal 첨부와 같은 문구로 거절된다.
  // 테스트 코드: LC-071
  it('rejects an executable file with the Deal message', async () => {
    // given: 계약 대화상자의 업로드 폼
    const { dlg } = await openEdit(clean())

    // when: setup.exe를 고르고 업로드한다
    await upload(dlg, file('setup.exe'))

    // then: 요청이 가지 않고 문구가 alert로 보인다
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('실행·설치 파일(.exe)은 업로드할 수 없습니다.')
    expect(within(dlg).queryByRole('button', { name: 'setup.exe' })).not.toBeInTheDocument()
  })

  // 파일이 없거나 설명이 100자를 넘으면 요청 없이 문구를 보인다.
  // 테스트 코드: LC-071
  it('rejects a missing file and a description over 100 characters', async () => {
    // given: 계약 대화상자의 업로드 폼
    const { user, dlg } = await openEdit(clean())

    // when: 파일 없이, 설명 101자로 각각 업로드한다
    await user.click(within(dlg).getByRole('button', { name: '업로드' }))
    // then: 요청이 가지 않고 문구가 alert로 보인다
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('업로드할 파일을 선택하세요.')

    await user.upload(within(dlg).getByLabelText('파일'), file('메모.pdf'))
    await user.click(within(dlg).getByLabelText('설명'))
    await user.paste('가'.repeat(101))
    expect(within(dlg).getByText('101/100')).toBeVisible()
    await user.click(within(dlg).getByRole('button', { name: '업로드' }))
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('설명은 100자 이내로 입력하세요.')
  })

  // 같은 이름이면 교체·건너뛰기를 묻고 교체를 고르면 replace로 올린다.
  // 테스트 코드: LC-072
  it('asks to replace or skip on a 409 for the same name and replaces when 교체 is chosen', async () => {
    // given: a.pdf가 있는 계약 대화상자
    const c = withFiles()
    const name = (await filesOf(c))[0]!.fileName
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { dlg } = await openEdit(c)

    // when: a.pdf를 올려 409를 받고 교체를 누른다
    await upload(dlg, file(name, 5000), '교체본')

    const confirm = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    // then: 같은 이름의 파일 대화상자가 떴고 replace 요청 뒤 교체되었습니다 알림이 보인다
    expect(confirm).toHaveTextContent(`같은 이름의 파일이 이미 있습니다: ${name}`)
    await userEvent.click(within(confirm).getByRole('button', { name: '교체' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '같은 이름의 파일' })).not.toBeInTheDocument())
    await waitFor(() => expect(within(dlg).getByRole('row', { name: new RegExp(name) })).toHaveTextContent('교체본'))
    expect(send.mock.calls.map((call) => call[1].onExists)).toEqual(['ask', 'replace'])
    expect(within(dlg).getAllByRole('button', { name })).toHaveLength(1)
  })

  // 건너뛰기를 고르면 skip 요청 뒤 목록이 그대로다.
  // 테스트 코드: LC-072
  it('keeps the list as it was when 건너뛰기 is chosen (skip request)', async () => {
    // given: a.pdf가 있는 계약 대화상자
    const c = withFiles()
    const before = await filesOf(c)
    const name = before[0]!.fileName
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { dlg } = await openEdit(c)

    await upload(dlg, file(name, 5000), '건너뛸 설명')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '건너뛰기' }))

    // when: a.pdf를 올려 409를 받고 건너뛰기를 누른다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '같은 이름의 파일' })).not.toBeInTheDocument())
    // then: skip 요청이 가고 목록은 그대로다
    expect(send.mock.calls.at(-1)?.[1].onExists).toBe('skip')
    expect((await filesOf(c)).map((a) => a.id)).toEqual(before.map((a) => a.id))
    expect(within(dlg).queryByText('건너뛸 설명')).not.toBeInTheDocument()
  })

  // 저장 위치를 쓸 수 없다는 서버 문구를 보인다.
  // 테스트 코드: LC-073
  it('shows the 503 message when the storage location is unavailable', async () => {
    // given: 서버가 업로드에 503을 주는 상태
    const c = clean()
    vi.spyOn(gateway.licenseContracts.attachments, 'upload').mockRejectedValue(
      Object.assign(new Error('파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'), { status: 503 }),
    )
    const { dlg } = await openEdit(c)

    // when: 파일을 올린다
    await upload(dlg, file('a.pdf'))

    // then: 서버 문구가 alert로 보이고 목록은 그대로다
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다.')
  })

  // 첨부 삭제는 확인 뒤에만 요청한다.
  // 테스트 코드: LC-078
  it('deletes a file after confirmation and keeps it when cancelled', async () => {
    // given: 첨부가 있는 계약 대화상자
    const c = withFiles()
    const name = (await filesOf(c))[0]!.fileName
    const { user, dlg } = await openEdit(c, 'admin')

    // when: 삭제를 눌러 확인 창에서 취소하고, 다시 삭제를 눌러 삭제한다
    await user.click(await within(dlg).findByRole('button', { name: `${name} 삭제` }))
    const cancelDialog = await screen.findByRole('dialog', { name: '첨부 파일 삭제' })
    // then: 취소하면 요청이 없고 확인하면 삭제되었습니다 알림과 함께 목록에서 사라진다
    expect(cancelDialog).toHaveTextContent(name)
    await user.click(within(cancelDialog).getByRole('button', { name: '취소' }))
    expect(within(dlg).getByRole('button', { name })).toBeVisible()

    await user.click(within(dlg).getByRole('button', { name: `${name} 삭제` }))
    await user.click(within(await screen.findByRole('dialog', { name: '첨부 파일 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(dlg).queryByRole('button', { name })).not.toBeInTheDocument())
    expect((await filesOf(c)).map((a) => a.fileName)).not.toContain(name)
  })

  // 파일명을 누르면 내려받는다.
  // 테스트 코드: LC-074
  it('downloads a file through the gateway when its name is clicked', async () => {
    // given: 첨부가 있는 계약 대화상자
    const c = withFiles()
    const first = (await filesOf(c))[0]!
    const download = vi.spyOn(gateway.licenseContracts.attachments, 'download')
    const { user, dlg } = await openEdit(c)

    // when: 파일명을 누른다
    await user.click(await within(dlg).findByRole('button', { name: first.fileName }))

    // then: 게이트웨이 다운로드가 호출되고 그 이름·내용으로 저장이 시작된다
    await waitFor(() => expect(download).toHaveBeenCalledWith(first.id))
  })
})

describe('종료일 향후 기간 검색 (B7)', () => {
  // 다가오는 기간 프리셋은 종료일에만 있고 시작일에는 없다.
  it('offers upcoming presets on the end date only, not on the start date', async () => {
    // given: 계약 목록 화면
    // when: 시작일·종료일 기간 선택 상자를 본다
    await open()
    const bar = within(screen.getByRole('search', { name: '계약 검색' }))

    const start = within(bar.getByRole('combobox', { name: '라이선스 시작일' })).getAllByRole('option').map((o) => o.textContent)
    // then: 종료일에만 다가오는 기간 프리셋이 있다
    expect(start).not.toContain('향후 1개월')
    expect(start).not.toContain('향후 2개월')
  })

  // 종료일 향후 1·2개월 프리셋은 오늘~오늘+N개월 범위로 서버에 검색한다.
  // 테스트 코드: LC-024
  it.each([
    ['향후 1개월', 1],
    ['향후 2개월', 2],
  ] as const)('sends today and today + N months as the end range for %s', async (label, months) => {
    // given: 서버 시계 2027-03-15의 계약 목록 화면
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const { user } = await open()
    const bar = within(screen.getByRole('search', { name: '계약 검색' }))
    const select = bar.getByRole('combobox', { name: '라이선스 종료일' })
    await waitFor(() => expect(within(select).getByRole('option', { name: label })).toBeEnabled())

    // when: 종료일에서 향후 프리셋을 고르고 검색한다
    await user.selectOptions(select, label)
    await user.click(bar.getByRole('button', { name: '검색' }))

    // then: endFrom은 오늘, endTo는 오늘 + N개월로 서버에 간다
    const to = new Date('2027-03-15T00:00:00Z')
    to.setUTCMonth(to.getUTCMonth() + months)
    await waitFor(() => expect((list.mock.calls.at(-1) as unknown[])[0]).toMatchObject({ endFrom: '2027-03-15', endTo: to.toISOString().slice(0, 10) }))
  })
})

describe('만료 임박 색과 상태 색 (B8)', () => {
  const today = '2027-03-15'
  const plus = (months: number) => {
    const d = new Date(`${today}T00:00:00Z`)
    d.setUTCMonth(d.getUTCMonth() + months)
    return d.toISOString().slice(0, 10)
  }
  const level = (c: LicenseContract) => (!isIssued(c) || c.licenseEnd === null ? null : c.licenseEnd < plus(1) ? 'danger' : c.licenseEnd < plus(2) ? 'warning' : null)

  // 발급 계약의 날짜 칸은 남은 기간에 따라 위험·주의 색이 붙는다.
  // 테스트 코드: LC-027
  it('colors the start and end date cells by the remaining period of issued contracts only', async () => {
    // given: 서버 시계 2027-03-15와 종료일이 다른 발급 계약들
    // when: 목록을 연다
    await open()

    // then: 시작일·종료일 칸에 위험·주의·색 없음이 붙고 종료·미발급은 색이 없다
    for (const c of contracts.slice(0, 50).filter((x, _i, all) => all.filter((y) => y.dealName === x.dealName).length === 1)) {
      const cells = cellsOf(c)
      for (const index of [5, 6]) {
        expect(cells[index]!.classList.contains('expiry-danger'), `${c.dealName} danger`).toBe(level(c) === 'danger')
        expect(cells[index]!.classList.contains('expiry-warning'), `${c.dealName} warning`).toBe(level(c) === 'warning')
      }
    }
  })

  // 상태 칸은 발급이면 status-issued, 종료면 status-ended, 미발급이면 없다.
  // 테스트 코드: LC-027
  it('marks the status cell with status-issued or status-ended and nothing for not-issued', async () => {
    // given: 상태가 다른 계약들
    // when: 목록을 연다
    await open()

    // then: 상태 칸 클래스가 상태에 맞다
    for (const c of contracts.slice(0, 50).filter((x, _i, all) => all.filter((y) => y.dealName === x.dealName).length === 1)) {
      const cell = cellsOf(c)[7]!
      expect(cell.classList.contains('status-issued'), `${c.dealName} issued`).toBe(isIssued(c))
      expect(cell.classList.contains('status-ended'), `${c.dealName} ended`).toBe(c.status === 'ended')
    }
  })

  // 만료 임박 계약을 갱신하면 새 행에는 색이 없다.
  // 테스트 코드: LC-027
  it('removes the expiry color after renewing a near-expiry contract from the dialog', async () => {
    // given: 위험 색이 붙은 발급 계약
    const c = pick((x) => level(x) === 'danger')
    const { user, dlg } = await openEdit(c)
    await user.click(within(within(dlg).getByRole('group', { name: '상태' })).getByRole('button', { name: '라이센스 갱신' }))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    // when: 대화상자에서 갱신한다
    await screen.findByText('라이센스를 갱신했습니다.')
    // then: 새 행에는 만료 색이 없다
    await waitFor(() => {
      const renewed = rows().filter((r) => within(r).getAllByRole('cell')[0]?.textContent === c.dealName)
      const issued = renewed.find((r) => within(r).getAllByRole('cell')[7]?.textContent === '발급(갱신)')
      expect(issued).toBeDefined()
      expect(within(issued!).getAllByRole('cell')[6]!.classList.contains('expiry-danger')).toBe(false)
    })
  })
})
