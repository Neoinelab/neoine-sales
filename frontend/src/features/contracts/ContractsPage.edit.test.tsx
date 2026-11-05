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
  it('opens 계약 수정 with the Deal values read-only and the contract fields editable', async () => {
    const c = pick((x) => x.vendor !== null && x.partner !== null)
    const { dlg } = await openEdit(c)

    const dealValues = within(dlg).getByRole('group', { name: 'Deal 정보' })
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
    expect(within(dlg).getByLabelText('기술담당')).toHaveValue(c.techOwner)
    expect(within(dlg).getByLabelText('Note')).toHaveValue(c.note)
    expect(within(dlg).getByRole('combobox', { name: '점검주기' })).toHaveDisplayValue(INSPECTION_LABELS[c.inspection])
    expect(within(dlg).queryByText(`Deal ${c.dealCode}`)).not.toBeInTheDocument()
    expect(within(dlg).getByRole('button', { name: '저장' })).toBeVisible()
    expect(within(dlg).getByRole('button', { name: '취소' })).toBeVisible()
  })

  it('opens the dialog from the keyboard with Enter on the focused row', async () => {
    const c = pick()
    await open()

    rowOf(c).focus()
    expect(rowOf(c)).toHaveFocus()
    await userEvent.keyboard('{Enter}')

    expect(await dialog(`계약 수정 - ${c.dealName}`)).toBeVisible()
  })

  it('opens the edit dialog when the status cell of a not-issued row is clicked (no button in the table)', async () => {
    const c = pick((x) => x.status === 'not_issued')
    const { user } = await open()

    await user.click(cellsOf(c)[7]!)

    expect(await dialog(`계약 수정 - ${c.dealName}`)).toBeVisible()
    expect(within(rowOf(c)).queryAllByRole('button')).toHaveLength(0)
  })
})

describe('계약 수정 저장 (B2, AC11)', () => {
  it('saves the contract fields through PUT and shows them in the table with the notice', async () => {
    const c = pick()
    const update = vi.spyOn(gateway.licenseContracts, 'update')
    const { user, dlg } = await openEdit(c)

    await user.clear(within(dlg).getByLabelText('기술담당'))
    await user.type(within(dlg).getByLabelText('기술담당'), '새기술담당')
    await user.clear(within(dlg).getByLabelText('Note'))
    await user.type(within(dlg).getByLabelText('Note'), '수정된 메모')
    await user.selectOptions(within(dlg).getByRole('combobox', { name: '점검주기' }), INSPECTION_LABELS.monthly)
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('계약을 수정했습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(c.id, { techOwner: '새기술담당', inspection: 'monthly', note: '수정된 메모' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /^계약 수정/ })).not.toBeInTheDocument())
    await waitFor(() => expect(cellsOf(c)[9]).toHaveTextContent('새기술담당'))
    expect(cellsOf(c)[10]).toHaveTextContent(INSPECTION_LABELS.monthly)
    expect(cellsOf(c)[11]).toHaveTextContent('수정된 메모')
    expect(cellsOf(c)[1]).toHaveTextContent(c.customer)
  })

  it('does not send the Deal columns and does not require them', async () => {
    const c = pick()
    const update = vi.spyOn(gateway.licenseContracts, 'update')
    const { user, dlg } = await openEdit(c)

    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('계약을 수정했습니다.')).toBeVisible()
    expect(Object.keys(update.mock.calls[0]![1]).sort()).toEqual(['inspection', 'note', 'techOwner'])
  })

  it('shows the server message and keeps the dialog open when the server refuses (422)', async () => {
    const c = pick()
    const { user, dlg } = await openEdit(c)

    await user.click(within(dlg).getByLabelText('기술담당'))
    await user.paste('가'.repeat(101))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await within(dlg).findByRole('alert')).toBeVisible()
    expect(screen.getByRole('dialog', { name: /^계약 수정/ })).toBeVisible()
    expect(screen.queryByText('계약을 수정했습니다.')).not.toBeInTheDocument()
  })

  it('discards the edits on 취소', async () => {
    const c = pick()
    const { user, dlg } = await openEdit(c)

    await user.clear(within(dlg).getByLabelText('기술담당'))
    await user.type(within(dlg).getByLabelText('기술담당'), '버려질이름')
    await user.click(within(dlg).getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(cellsOf(c)[9]).not.toHaveTextContent('버려질이름')
    expect(screen.queryByText('계약을 수정했습니다.')).not.toBeInTheDocument()
  })

  it('shows no save button for a read-only user', async () => {
    const c = pick()
    const { dlg } = await openEdit(c, 'user')

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

  it('has a 첨부 파일 area and lists the contract files from the server', async () => {
    const c = withFiles()
    const expected = await filesOf(c)
    const { dlg } = await openEdit(c)

    expect(within(dlg).getByText('첨부 파일')).toBeVisible()
    for (const a of expected) expect(await within(dlg).findByRole('button', { name: a.fileName })).toBeVisible()
  })

  it('uploads a file through the gateway, lists it, and still lists it after reopening', async () => {
    const c = clean()
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { user, dlg } = await openEdit(c)

    await upload(dlg, file('제안서.pdf', 2048), '제안서 초안')

    expect(await within(dlg).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
    expect(send.mock.calls[0]?.[0]).toBe(c.id)
    expect(send.mock.calls[0]?.[1]).toMatchObject({ description: '제안서 초안', onExists: 'ask' })
    await user.click(within(dlg).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(cellsOf(c)[0]).toBeVisible())
    await user.click(cellsOf(c)[1]!)
    expect(await within(await dialog(`계약 수정 - ${c.dealName}`)).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
  })

  it('rejects an executable file with the Deal message', async () => {
    const { dlg } = await openEdit(clean())

    await upload(dlg, file('setup.exe'))

    expect(await within(dlg).findByRole('alert')).toHaveTextContent('실행·설치 파일(.exe)은 업로드할 수 없습니다.')
    expect(within(dlg).queryByRole('button', { name: 'setup.exe' })).not.toBeInTheDocument()
  })

  it('rejects a missing file and a description over 100 characters', async () => {
    const { user, dlg } = await openEdit(clean())

    await user.click(within(dlg).getByRole('button', { name: '업로드' }))
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('업로드할 파일을 선택하세요.')

    await user.upload(within(dlg).getByLabelText('파일'), file('메모.pdf'))
    await user.click(within(dlg).getByLabelText('설명'))
    await user.paste('가'.repeat(101))
    expect(within(dlg).getByText('101/100')).toBeVisible()
    await user.click(within(dlg).getByRole('button', { name: '업로드' }))
    expect(await within(dlg).findByRole('alert')).toHaveTextContent('설명은 100자 이내로 입력하세요.')
  })

  it('asks to replace or skip on a 409 for the same name and replaces when 교체 is chosen', async () => {
    const c = withFiles()
    const name = (await filesOf(c))[0]!.fileName
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { dlg } = await openEdit(c)

    await upload(dlg, file(name, 5000), '교체본')

    const confirm = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    expect(confirm).toHaveTextContent(`같은 이름의 파일이 이미 있습니다: ${name}`)
    await userEvent.click(within(confirm).getByRole('button', { name: '교체' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '같은 이름의 파일' })).not.toBeInTheDocument())
    await waitFor(() => expect(within(dlg).getByRole('row', { name: new RegExp(name) })).toHaveTextContent('교체본'))
    expect(send.mock.calls.map((call) => call[1].onExists)).toEqual(['ask', 'replace'])
    expect(within(dlg).getAllByRole('button', { name })).toHaveLength(1)
  })

  it('keeps the list as it was when 건너뛰기 is chosen (skip request)', async () => {
    const c = withFiles()
    const before = await filesOf(c)
    const name = before[0]!.fileName
    const send = vi.spyOn(gateway.licenseContracts.attachments, 'upload')
    const { dlg } = await openEdit(c)

    await upload(dlg, file(name, 5000), '건너뛸 설명')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '건너뛰기' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '같은 이름의 파일' })).not.toBeInTheDocument())
    expect(send.mock.calls.at(-1)?.[1].onExists).toBe('skip')
    expect((await filesOf(c)).map((a) => a.id)).toEqual(before.map((a) => a.id))
    expect(within(dlg).queryByText('건너뛸 설명')).not.toBeInTheDocument()
  })

  it('shows the 503 message when the storage location is unavailable', async () => {
    const c = clean()
    vi.spyOn(gateway.licenseContracts.attachments, 'upload').mockRejectedValue(
      Object.assign(new Error('파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'), { status: 503 }),
    )
    const { dlg } = await openEdit(c)

    await upload(dlg, file('a.pdf'))

    expect(await within(dlg).findByRole('alert')).toHaveTextContent('파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다.')
  })

  it('deletes a file after confirmation and keeps it when cancelled', async () => {
    const c = withFiles()
    const name = (await filesOf(c))[0]!.fileName
    const { user, dlg } = await openEdit(c, 'admin')

    await user.click(await within(dlg).findByRole('button', { name: `${name} 삭제` }))
    const cancelDialog = await screen.findByRole('dialog', { name: '첨부 파일 삭제' })
    expect(cancelDialog).toHaveTextContent(name)
    await user.click(within(cancelDialog).getByRole('button', { name: '취소' }))
    expect(within(dlg).getByRole('button', { name })).toBeVisible()

    await user.click(within(dlg).getByRole('button', { name: `${name} 삭제` }))
    await user.click(within(await screen.findByRole('dialog', { name: '첨부 파일 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(dlg).queryByRole('button', { name })).not.toBeInTheDocument())
    expect((await filesOf(c)).map((a) => a.fileName)).not.toContain(name)
  })

  it('downloads a file through the gateway when its name is clicked', async () => {
    const c = withFiles()
    const first = (await filesOf(c))[0]!
    const download = vi.spyOn(gateway.licenseContracts.attachments, 'download')
    const { user, dlg } = await openEdit(c)

    await user.click(await within(dlg).findByRole('button', { name: first.fileName }))

    await waitFor(() => expect(download).toHaveBeenCalledWith(first.id))
  })
})

describe('종료일 향후 기간 검색 (B7)', () => {
  it('offers upcoming presets on the end date only, not on the start date', async () => {
    await open()
    const bar = within(screen.getByRole('search', { name: '계약 검색' }))

    const start = within(bar.getByRole('combobox', { name: '라이선스 시작일' })).getAllByRole('option').map((o) => o.textContent)
    expect(start).not.toContain('향후 1개월')
    expect(start).not.toContain('향후 2개월')
  })

  it.each([
    ['향후 1개월', 1],
    ['향후 2개월', 2],
  ] as const)('sends today and today + N months as the end range for %s', async (label, months) => {
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const { user } = await open()
    const bar = within(screen.getByRole('search', { name: '계약 검색' }))
    const select = bar.getByRole('combobox', { name: '라이선스 종료일' })
    await waitFor(() => expect(within(select).getByRole('option', { name: label })).toBeEnabled())

    await user.selectOptions(select, label)
    await user.click(bar.getByRole('button', { name: '검색' }))

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

  it('colors the start and end date cells by the remaining period of issued contracts only', async () => {
    await open()

    for (const c of contracts.slice(0, 50).filter((x, _i, all) => all.filter((y) => y.dealName === x.dealName).length === 1)) {
      const cells = cellsOf(c)
      for (const index of [5, 6]) {
        expect(cells[index]!.classList.contains('expiry-danger'), `${c.dealName} danger`).toBe(level(c) === 'danger')
        expect(cells[index]!.classList.contains('expiry-warning'), `${c.dealName} warning`).toBe(level(c) === 'warning')
      }
    }
  })

  it('marks the status cell with status-issued or status-ended and nothing for not-issued', async () => {
    await open()

    for (const c of contracts.slice(0, 50).filter((x, _i, all) => all.filter((y) => y.dealName === x.dealName).length === 1)) {
      const cell = cellsOf(c)[7]!
      expect(cell.classList.contains('status-issued'), `${c.dealName} issued`).toBe(isIssued(c))
      expect(cell.classList.contains('status-ended'), `${c.dealName} ended`).toBe(c.status === 'ended')
    }
  })

  it('removes the expiry color after renewing a near-expiry contract from the dialog', async () => {
    const c = pick((x) => level(x) === 'danger')
    const { user, dlg } = await openEdit(c)
    await user.click(within(within(dlg).getByRole('group', { name: '상태' })).getByRole('button', { name: '라이센스 갱신' }))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    await screen.findByText('라이센스를 갱신했습니다.')
    await waitFor(() => {
      const renewed = rows().filter((r) => within(r).getAllByRole('cell')[0]?.textContent === c.dealName)
      const issued = renewed.find((r) => within(r).getAllByRole('cell')[7]?.textContent === '발급(갱신)')
      expect(issued).toBeDefined()
      expect(within(issued!).getAllByRole('cell')[6]!.classList.contains('expiry-danger')).toBe(false)
    })
  })
})
