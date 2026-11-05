import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { LicenseContract } from '../../shared/model/types'
import { allContracts, STATUS_TEXT } from '../../test/licenseContracts'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'

/**
 * 계약관리 화면(실제 API 연동): 데이터는 Fake 게이트웨이(`gateway.licenseContracts`)에서 읽고 기대값은 그 데이터로 계산한다.
 * 목록은 서버가 정렬·필터·쪽 나누기를 하고(50건씩) 화면의 `전체 N건`은 서버 total이다. 시계는 2027-03-15 고정.
 */
const PAGE = '/contracts'
const COLUMNS = ['Deal 코드', '고객사명', 'Vendor', '제품명', '파트너사', '라이선스 시작일', '라이선스 종료일', '상태', '담당영업', '기술담당', '점검주기', 'Note']
const LOAD = { timeout: 8000 }
const PAGE_SIZE = 50

let contracts: LicenseContract[] = []
beforeEach(async () => {
  pinClock()
  contracts = await allContracts()
})
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

const bar = () => within(screen.getByRole('search', { name: '계약 검색' }))
const table = () => screen.getByRole('table', { name: '계약 목록' })
const rows = () => within(table()).getAllByRole('row').slice(1)
const codes = () => rows().map((row) => within(row).getAllByRole('cell')[0]?.textContent ?? '')
const sorted = (list: string[]) => [...list].sort()
const codesOf = (list: readonly LicenseContract[]) => list.map((c) => c.dealCode)
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => (spy.mock.calls.at(-1) as unknown[])[0] as Record<string, unknown>

async function open() {
  const view = await renderAt(PAGE)
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await waitFor(() => expect(rows().length).toBeGreaterThan(0), LOAD)
  return view
}

/** 검색 결과가 한 쪽(50건)에 다 들어오는지 확인한 기대 목록. */
function fits(expected: readonly LicenseContract[]) {
  expect(expected.length).toBeGreaterThan(0)
  expect(expected.length).toBeLessThanOrEqual(PAGE_SIZE)
  return expected
}

describe('목록 (AC2, AC19)', () => {
  it('shows the first fifty contracts with the server total and the 12 headers in order', async () => {
    expect(contracts.length).toBeGreaterThan(PAGE_SIZE)
    await open()

    expect(rows()).toHaveLength(PAGE_SIZE)
    expect(screen.getByText(`전체 ${contracts.length}건`)).toBeVisible()
    expect(within(table()).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(COLUMNS)
    expect(within(table()).queryByRole('columnheader', { name: '구분' })).not.toBeInTheDocument()
  })

  it('shows the values of the first server row in its cells and the four status labels', async () => {
    await open()
    const first = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 1)).items[0]!

    const cells = within(rows()[0]!).getAllByRole('cell')

    expect(cells[0]).toHaveTextContent(first.dealCode)
    expect(cells[1]).toHaveTextContent(first.customer)
    expect(cells[3]).toHaveTextContent(first.product)
    expect(cells[7]?.textContent).toBe(STATUS_TEXT[first.status])
    expect(cells[8]).toHaveTextContent(first.salesOwner.name)
    expect(within(table()).queryAllByRole('button', { name: /라이센스 (발급|갱신)/ })).toHaveLength(0)
  })

  it('has no mock-data notice any more', async () => {
    await open()

    expect(screen.getByRole('heading', { name: '계약관리' })).toBeVisible()
    expect(screen.queryByText(/디자인 시안/)).not.toBeInTheDocument()
    expect(screen.queryByText(/가상 데이터/)).not.toBeInTheDocument()
  })

  it('has all search conditions and the two buttons', async () => {
    await open()

    for (const name of ['고객사명', '제품명']) expect(bar().getByRole('textbox', { name })).toBeVisible()
    for (const name of ['Vendor', '담당영업', '상태', '라이선스 시작일', '라이선스 종료일']) {
      expect(bar().getByRole('combobox', { name })).toBeVisible()
    }
    expect(bar().getByRole('button', { name: '검색' })).toBeVisible()
    expect(bar().getByRole('button', { name: '초기화' })).toBeVisible()
  })

  it('allows every role to open the page', async () => {
    await renderAt(PAGE, { role: 'user' })

    expect(await screen.findByRole('table', { name: '계약 목록' }, LOAD)).toBeVisible()
  })
})

describe('고객사명·제품명 검색 (AC3, AC17)', () => {
  it('sends the customer text to the server and restores the list on reset', async () => {
    const customer = contracts[0]!.customer
    const expected = fits(contracts.filter((c) => c.customer.toLowerCase().includes(customer.toLowerCase())))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.type(bar().getByRole('textbox', { name: '고객사명' }), customer)
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ customer })
    expect(screen.getByText(`전체 ${expected.length}건`)).toBeVisible()

    await user.click(bar().getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(rows()).toHaveLength(PAGE_SIZE))
    expect(bar().getByRole('textbox', { name: '고객사명' })).toHaveValue('')
  })

  it('searches on Enter', async () => {
    const customer = contracts[0]!.customer
    const expected = fits(contracts.filter((c) => c.customer.toLowerCase().includes(customer.toLowerCase())))
    const { user } = await open()

    await user.type(bar().getByRole('textbox', { name: '고객사명' }), `${customer}{Enter}`)

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
  })

  it('filters by part of the product name ignoring case, using the server', async () => {
    const product = contracts[0]!.product
    const part = product.slice(0, 3).toUpperCase()
    const expected = fits(contracts.filter((c) => c.product.toLowerCase().includes(part.toLowerCase())))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.type(bar().getByRole('textbox', { name: '제품명' }), part)
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ product: part })
  })
})

describe('상태 검색 (C2)', () => {
  it.each(['not_issued', 'issued_new', 'issued_renewal', 'ended'] as const)('keeps only %s rows via the server', async (status) => {
    const expected = fits(contracts.filter((c) => c.status === status))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '상태' }), STATUS_TEXT[status])
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ status })
    for (const row of rows()) expect(within(row).getAllByRole('cell')[7]).toHaveTextContent(STATUS_TEXT[status])
  })

  it('offers the four statuses after 전체', async () => {
    await open()

    const labels = within(bar().getByRole('combobox', { name: '상태' })).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '미발급', '발급(신규)', '발급(갱신)', '종료'])
  })
})

describe('Vendor·담당영업 검색', () => {
  it('lists the vendors of the Vendor management list and searches by its id', async () => {
    const vendors = await gateway.vendors.list()
    const vendor = contracts.find((c) => c.vendor !== null)!.vendor!
    const expected = fits(contracts.filter((c) => c.vendor?.id === vendor.id))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const select = bar().getByRole('combobox', { name: 'Vendor' })
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(expect.arrayContaining(['전체', ...vendors.map((v) => v.name)]))
    await user.selectOptions(select, vendor.name)
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ vendorId: vendor.id })
  })

  it('searches by the sales owner user id, resigned users included in the choices', async () => {
    const owner = contracts[0]!.salesOwner
    const expected = fits(contracts.filter((c) => c.salesOwner.id === owner.id))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const select = bar().getByRole('combobox', { name: '담당영업' })
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))

    await user.selectOptions(select, owner.name)
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ ownerId: owner.id })
  })
})

describe('라이선스 종료일 검색 (AC5, AC17)', () => {
  const compact = (iso: string) => iso.replaceAll('-', '')

  it('sends the custom range to the server, both ends included', async () => {
    const ends = [...new Set(contracts.flatMap((c) => (c.licenseEnd ? [c.licenseEnd] : [])))].sort()
    const from = ends[Math.floor(ends.length / 4)]!
    const to = ends[Math.floor((ends.length * 3) / 4)]!
    const expected = fits(contracts.filter((c) => c.licenseEnd !== null && c.licenseEnd >= from && c.licenseEnd <= to))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 종료일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 시작' }), compact(from))
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 끝' }), compact(to))
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ endFrom: from, endTo: to })
  })

  it('does not search and shows the error when the start is later than the end', async () => {
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 종료일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 시작' }), '20270310')
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 끝' }), '20270301')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(await screen.findByText(/시작은 끝보다 늦을 수 없습니다/)).toBeVisible()
    expect(list).not.toHaveBeenCalled()
    expect(rows()).toHaveLength(PAGE_SIZE)
  })

  it('searches the start date range too', async () => {
    const starts = [...new Set(contracts.flatMap((c) => (c.licenseStart ? [c.licenseStart] : [])))].sort()
    const from = starts[Math.floor(starts.length / 2)]!
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 시작일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 시작일 시작' }), compact(from))
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(lastQuery(list)).toMatchObject({ startFrom: from }))
    expect(lastQuery(list).startTo).toBeUndefined()
  })

  it('offers the Deals last-updated presets plus the two upcoming presets (B7)', async () => {
    await open()

    const labels = within(bar().getByRole('combobox', { name: '라이선스 종료일' })).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '향후 1개월', '향후 2개월', '직접 지정'])
  })
})

describe('정렬 (AC6, AC18)', () => {
  const header = (name: string) => screen.getByRole('columnheader', { name })

  it('asks the server for end date ascending by default and flips the direction on click', async () => {
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const { user } = await open()

    expect(header('라이선스 종료일')).toHaveAttribute('aria-sort', 'ascending')
    expect(list.mock.calls[0]?.[0]).toMatchObject({ sort: 'licenseEnd', order: 'asc' })

    await user.click(within(header('라이선스 종료일')).getByRole('button', { name: '라이선스 종료일' }))

    await waitFor(() => expect(header('라이선스 종료일')).toHaveAttribute('aria-sort', 'descending'))
    expect(lastQuery(list)).toMatchObject({ sort: 'licenseEnd', order: 'desc' })
  })

  it.each([
    ['고객사명', 'customer'],
    ['Vendor', 'vendor'],
    ['제품명', 'product'],
    ['파트너사', 'partner'],
    ['라이선스 시작일', 'licenseStart'],
    ['상태', 'status'],
    ['담당영업', 'salesOwner'],
    ['기술담당', 'techOwner'],
    ['점검주기', 'inspection'],
    ['Note', 'note'],
    ['Deal 코드', 'dealCode'],
  ] as const)('sorts by %s on the server when its header is clicked', async (label, sort) => {
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.click(within(header(label)).getByRole('button', { name: label }))

    await waitFor(() => expect(header(label)).toHaveAttribute('aria-sort', 'ascending'))
    expect(lastQuery(list)).toMatchObject({ sort, order: 'asc' })
    expect(header('라이선스 종료일')).not.toHaveAttribute('aria-sort')
  })
})

describe('빈 결과 (AC7)', () => {
  it('shows the empty message and zero count when nothing matches, and hides it after reset', async () => {
    const { user } = await open()

    await user.type(bar().getByRole('textbox', { name: '고객사명' }), '존재하지않는고객사zzz')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 계약이 없습니다.')).toBeVisible()
    expect(screen.getByText('전체 0건')).toBeVisible()

    await user.click(bar().getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(screen.queryByText('조건에 맞는 계약이 없습니다.')).not.toBeInTheDocument())
    expect(rows()).toHaveLength(PAGE_SIZE)
  })
})
