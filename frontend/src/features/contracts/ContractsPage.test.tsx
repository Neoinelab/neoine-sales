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
const COLUMNS = ['Deal명', '고객사명', 'Vendor', '제품명', '파트너사', '라이선스 시작일', '라이선스 종료일', '상태', '담당영업', '기술담당']
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

const bar = () => within(screen.getByLabelText('계약 검색'))
const table = () => screen.getByRole('table', { name: '계약 목록' })
const rows = () => within(table()).getAllByRole('row').slice(1)
const codes = () => rows().map((row) => within(row).getAllByRole('cell')[0]?.textContent ?? '')
const sorted = (list: string[]) => [...list].sort()
const codesOf = (list: readonly LicenseContract[]) => list.map((c) => c.dealName)
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
  // 테스트 코드: LC-022
  it('shows the first fifty contracts with the server total and ten percentage-sized columns', async () => {
    // given: 서버에 계약이 50건보다 많다
    expect(contracts.length).toBeGreaterThan(PAGE_SIZE)

    // when: /contracts를 연다
    await open()

    // then: 계약 목록 표에 50행, 전체 N건, 머리글 10개가 보인다
    expect(rows()).toHaveLength(PAGE_SIZE)
    expect(screen.getByText(`전체 ${contracts.length}건`)).toBeVisible()
    expect(within(table()).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(COLUMNS)
    expect(Array.from(table().querySelectorAll('col'), (col) => col.style.width))
      .toEqual(['22%', '8%', '10%', '12%', '8%', '8%', '8%', '8%', '8%', '8%'])
    expect(within(table()).queryByRole('columnheader', { name: '구분' })).not.toBeInTheDocument()
    expect(within(table()).queryByRole('columnheader', { name: 'Deal 코드' })).not.toBeInTheDocument()
  })

  // 첫 행 칸에 서버 값(빈 값은 -)과 상태 표시 이름이 보인다.
  // 테스트 코드: LC-022
  it('shows the values of the first server row in its cells and the four status labels', async () => {
    // given: 서버에 계약이 있다
    await open()
    const first = (await gateway.licenseContracts.list({ sort: 'issuancePriority', order: 'asc' }, 0, 1)).items[0]!

    // when: /contracts를 연다
    const cells = within(rows()[0]!).getAllByRole('cell')

    // then: 첫 행 칸이 서버 값이고 상태는 미발급·발급(신규)·발급(갱신)·종료로 보인다
    expect(cells).toHaveLength(COLUMNS.length)
    expect(cells[0]).toHaveTextContent(first.dealName)
    expect(cells[1]).toHaveTextContent(first.customer)
    expect(cells[3]).toHaveTextContent(first.product)
    expect(cells[7]?.textContent).toBe(STATUS_TEXT[first.status])
    expect(cells[8]).toHaveTextContent(first.salesOwner.name)
    expect(within(table()).queryAllByRole('button', { name: /라이선스 (발급|갱신)/ })).toHaveLength(0)
  })

  // 시안 안내 문구가 더 이상 보이지 않는다.
  // 테스트 코드: LC-022
  it('has no mock-data notice any more', async () => {
    // when: /contracts를 연다 (전제: 서버에 계약이 있다)
    await open()

    // then: 시안 안내 문구가 없다
    expect(screen.getByRole('heading', { name: '계약관리' })).toBeVisible()
    expect(screen.queryByText(/디자인 시안/)).not.toBeInTheDocument()
    expect(screen.queryByText(/가상 데이터/)).not.toBeInTheDocument()
  })

  // 검색 조건 칸 전부와 검색·초기화 버튼이 있다.
  it('has all search conditions and the two buttons', async () => {
    // given: 계약 목록 화면
    await open()

    for (const name of ['고객사명', '제품명']) expect(bar().getByRole('textbox', { name })).toBeVisible()

    // when: /contracts를 연다
    for (const name of ['Vendor', '담당영업', '상태', '라이선스 시작일', '라이선스 종료일']) {
      expect(bar().getByRole('combobox', { name })).toBeVisible()
    }
    // then: 고객사명·제품명·Vendor·담당영업·상태·날짜 조건과 두 버튼이 보인다
    expect(bar().queryByRole('button', { name: '검색' })).not.toBeInTheDocument()
    expect(bar().getByRole('button', { name: '초기화' })).toBeVisible()
  })

  // 모든 역할이 계약관리 화면을 열 수 있다.
  // 테스트 코드: LC-022
  it('allows every role to open the page', async () => {
    // when: /contracts를 연다 (전제: admin·sales·user 각 역할)
    await renderAt(PAGE, { role: 'user' })

    // then: 목록 표가 보인다
    expect(await screen.findByRole('table', { name: '계약 목록' }, LOAD)).toBeVisible()
  })
})

describe('고객사명·제품명 검색 (AC3, AC17)', () => {
  // 고객사명 조건이 서버 조건으로 가고 초기화하면 전체로 돌아온다.
  // 테스트 코드: LC-024
  it('sends the customer text to the server and restores the list on reset', async () => {
    // given: 계약 목록 화면
    const customer = contracts[0]!.customer
    const expected = fits(contracts.filter((c) => c.customer.toLowerCase().includes(customer.toLowerCase())))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    // when: 고객사명 칸에 앞뒤 공백이 붙은 값을 넣고 검색한다
    await user.type(bar().getByRole('textbox', { name: '고객사명' }), customer)
    await user.keyboard('{Enter}')

    // then: 공백이 지워진 조건이 서버로 가고 해당 건수가 보인다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ customer })
    expect(screen.getByText(`전체 ${expected.length}건`)).toBeVisible()

    // when: 초기화를 누른다
    await user.click(bar().getByRole('button', { name: '초기화' }))

    // then: 조건 없는 목록이 보인다
    await waitFor(() => expect(rows()).toHaveLength(PAGE_SIZE))
    expect(bar().getByRole('textbox', { name: '고객사명' })).toHaveValue('')
  })

  // 고객사명 칸에서 Enter를 눌러도 검색한다.
  // 테스트 코드: LC-024
  it('searches on Enter', async () => {
    // given: 계약 목록 화면
    const customer = contracts[0]!.customer
    const expected = fits(contracts.filter((c) => c.customer.toLowerCase().includes(customer.toLowerCase())))
    const { user } = await open()

    // when: 고객사명 칸에 값을 넣고 Enter를 누른다
    await user.type(bar().getByRole('textbox', { name: '고객사명' }), `${customer}{Enter}`)

    // then: 서버 조건으로 검색된 결과가 보인다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
  })

  // 제품명 조건이 서버 조건으로 간다(대소문자 무시 부분 일치).
  // 테스트 코드: LC-024
  it('filters by part of the product name ignoring case, using the server', async () => {
    // given: 계약 목록 화면
    const product = contracts[0]!.product
    const part = product.slice(0, 3).toUpperCase()
    const expected = fits(contracts.filter((c) => c.product.toLowerCase().includes(part.toLowerCase())))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.type(bar().getByRole('textbox', { name: '제품명' }), part)
    await user.keyboard('{Enter}')

    // when: 제품명 일부를 넣고 검색한다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    // then: 서버가 거른 결과가 보인다
    expect(lastQuery(list)).toMatchObject({ product: part })
  })
})

describe('상태 검색 (C2)', () => {
  // 상태 조건이 서버 조건으로 가고 해당 상태 행만 보인다.
  // 테스트 코드: LC-024
  it.each(['not_issued', 'issued_new', 'issued_renewal', 'ended'] as const)('keeps only %s rows via the server', async (status) => {
    // given: 계약 목록 화면
    const expected = fits(contracts.filter((c) => c.status === status))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    // when: 상태를 고르고 검색한다
    await user.selectOptions(bar().getByRole('combobox', { name: '상태' }), STATUS_TEXT[status])

    // then: 그 상태의 행만 보인다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ status })
    for (const row of rows()) expect(within(row).getAllByRole('cell')[7]).toHaveTextContent(STATUS_TEXT[status])
  })

  // 상태 선택지는 전체 뒤에 네 상태가 온다.
  it('offers the four statuses after 전체', async () => {
    // given: 계약 목록 화면
    await open()

    // when: 상태 선택 상자를 본다
    const labels = within(bar().getByRole('combobox', { name: '상태' })).getAllByRole('option').map((o) => o.textContent)
    // then: 전체 + 4개 상태가 있다
    expect(labels).toEqual(['전체', '미발급', '발급(신규)', '발급(갱신)', '종료'])
  })
})

describe('Vendor·담당영업 검색', () => {
  // Vendor 선택지는 Vendor 관리 목록이고 id로 검색한다.
  // 테스트 코드: LC-024
  it('lists the vendors of the Vendor management list and searches by its id', async () => {
    // given: Vendor 관리 목록
    const vendors = await gateway.vendors.list()
    const vendor = contracts.find((c) => c.vendor !== null)!.vendor!
    const expected = fits(contracts.filter((c) => c.vendor?.id === vendor.id))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const select = bar().getByRole('combobox', { name: 'Vendor' })
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(expect.arrayContaining(['전체', ...vendors.map((v) => v.name)]))

    // when: Vendor를 고르고 검색한다
    await user.selectOptions(select, vendor.name)

    // then: vendorId 조건으로 서버가 거른 결과가 보인다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ vendorId: vendor.id })
  })

  // 담당영업은 퇴사자까지 선택지에 있고 사용자 id로 검색한다.
  // 테스트 코드: LC-024
  it('searches by the sales owner user id, resigned users included in the choices', async () => {
    // given: 퇴사자가 포함된 사용자 목록
    const owner = contracts[0]!.salesOwner
    const expected = fits(contracts.filter((c) => c.salesOwner.id === owner.id))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const select = bar().getByRole('combobox', { name: '담당영업' })
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))

    // when: 담당영업을 고르고 검색한다
    await user.selectOptions(select, owner.name)

    // then: ownerId 조건으로 서버가 거른 결과가 보인다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    expect(lastQuery(list)).toMatchObject({ ownerId: owner.id })
  })
})

describe('라이선스 종료일 검색 (AC5, AC17)', () => {
  const compact = (iso: string) => iso.replaceAll('-', '')

  // 직접 지정한 종료일 범위가 양끝 포함으로 서버에 간다.
  // 테스트 코드: LC-024
  it('sends the custom range to the server, both ends included', async () => {
    // given: 계약 목록 화면
    const ends = [...new Set(contracts.flatMap((c) => (c.licenseEnd ? [c.licenseEnd] : [])))].sort()
    const from = ends[Math.floor(ends.length / 4)]!
    const to = ends[Math.floor((ends.length * 3) / 4)]!
    const expected = fits(contracts.filter((c) => c.licenseEnd !== null && c.licenseEnd >= from && c.licenseEnd <= to))
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 종료일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 시작' }), compact(from))
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 끝' }), compact(to))
    await user.keyboard('{Enter}')

    // when: 종료일을 직접 지정해 검색한다
    await waitFor(() => expect(sorted(codes())).toEqual(sorted(codesOf(expected))))
    // then: endFrom·endTo 조건이 서버로 간다
    expect(lastQuery(list)).toMatchObject({ endFrom: from, endTo: to })
  })

  // 범위가 거꾸로면 검색하지 않고 문구를 보인다.
  // 테스트 코드: LC-025
  it('does not search and shows the error when the start is later than the end', async () => {
    // given: 종료일을 시작 2026-02-01, 끝 2026-01-31로 넣었다
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 종료일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 시작' }), '20270310')
    await waitFor(() => expect(list).toHaveBeenCalled())
    list.mockClear()
    await user.type(bar().getByRole('textbox', { name: '라이선스 종료일 끝' }), '20270301')
    // when: 검색을 누른다
    await user.keyboard('{Enter}')

    // then: 목록 요청이 가지 않고 범위 오류 문구가 보인다
    expect(await screen.findByText(/시작은 끝보다 늦을 수 없습니다/)).toBeVisible()
    expect(list).not.toHaveBeenCalled()
  })

  // 시작일 범위도 같은 방식으로 서버 조건이 된다.
  // 테스트 코드: LC-024
  it('searches the start date range too', async () => {
    // given: 계약 목록 화면
    const starts = [...new Set(contracts.flatMap((c) => (c.licenseStart ? [c.licenseStart] : [])))].sort()
    const from = starts[Math.floor(starts.length / 2)]!
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    await user.selectOptions(bar().getByRole('combobox', { name: '라이선스 시작일' }), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '라이선스 시작일 시작' }), compact(from))
    await user.keyboard('{Enter}')

    // when: 시작일을 직접 지정해 검색한다
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ startFrom: from }))
    // then: startFrom·startTo 조건이 서버로 간다
    expect(lastQuery(list).startTo).toBeUndefined()
  })

  // 종료일 기간 선택지는 Deals 최종 업데이트 프리셋에 다가오는 기간 2개가 더해진다.
  it('offers the Deals last-updated presets plus the two upcoming presets (B7)', async () => {
    // given: 계약 목록 화면
    await open()

    // when: 종료일 기간 선택 상자를 본다
    const labels = within(bar().getByRole('combobox', { name: '라이선스 종료일' })).getAllByRole('option').map((o) => o.textContent)
    // then: 프리셋과 다가오는 기간 2개가 있다
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '향후 1개월', '향후 2개월', '직접 지정'])
  })
})

describe('정렬 (AC6, AC18)', () => {
  const header = (name: string) => screen.getByRole('columnheader', { name })

  // 머리글을 누르면 그 열로 서버 정렬하고 다시 누르면 방향이 바뀐다.
  // 테스트 코드: LC-026
  it('uses issuance priority for each search and lets the end-date header override it', async () => {
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    const { user } = await open()
    expect(header('라이선스 종료일')).not.toHaveAttribute('aria-sort')
    expect(list.mock.calls[0]?.[0]).toMatchObject({ sort: 'issuancePriority', order: 'asc' })
    const endSort = within(header('라이선스 종료일')).getByRole('button', { name: '라이선스 종료일' })

    await user.click(endSort)
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ sort: 'licenseEnd', order: 'asc' }))
    expect(header('라이선스 종료일')).toHaveAttribute('aria-sort', 'ascending')

    await user.click(endSort)
    // then: 종료일 내림차순으로 서버에 요청한다
    await waitFor(() => expect(header('라이선스 종료일')).toHaveAttribute('aria-sort', 'descending'))
    expect(lastQuery(list)).toMatchObject({ sort: 'licenseEnd', order: 'desc' })

    const customer = contracts[0]!.customer
    await user.type(bar().getByRole('textbox', { name: '고객사명' }), customer)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ customer, sort: 'issuancePriority', order: 'asc' }))
    expect(header('라이선스 종료일')).not.toHaveAttribute('aria-sort')
  })

  // 각 열 머리글을 누르면 그 열로 서버 정렬하고 종료일 정렬 표시는 사라진다.
  // 테스트 코드: LC-026
  it.each([
    ['고객사명', 'customer'],
    ['Vendor', 'vendor'],
    ['제품명', 'product'],
    ['파트너사', 'partner'],
    ['라이선스 시작일', 'licenseStart'],
    ['상태', 'status'],
    ['담당영업', 'salesOwner'],
    ['기술담당', 'techOwner'],
    ['Deal명', 'dealName'],
  ] as const)('sorts by %s on the server when its header is clicked', async (label, sort) => {
    // given: 계약 목록 화면(처음 요청은 종료일 오름차순)
    const { user } = await open()
    const list = vi.spyOn(gateway.licenseContracts, 'list')

    // when: 해당 열 머리글을 누른다
    await user.click(within(header(label)).getByRole('button', { name: label }))

    // then: 그 열 오름차순으로 서버에 요청하고 종료일 정렬 표시는 없어진다
    await waitFor(() => expect(header(label)).toHaveAttribute('aria-sort', 'ascending'))
    expect(lastQuery(list)).toMatchObject({ sort, order: 'asc' })
    expect(header('라이선스 종료일')).not.toHaveAttribute('aria-sort')
  })
})

describe('빈 결과 (AC7)', () => {
  // 결과가 없으면 안내와 전체 0건이 보이고 초기화하면 사라진다.
  // 테스트 코드: LC-024
  it('shows the empty message and zero count when nothing matches, and hides it after reset', async () => {
    // given: 아무것도 일치하지 않는 조건
    const { user } = await open()

    // when: 고객사명에 없는 값을 넣고 검색한다
    await user.type(bar().getByRole('textbox', { name: '고객사명' }), '존재하지않는고객사zzz')
    await user.keyboard('{Enter}')

    // then: 조건에 맞는 계약이 없습니다와 전체 0건이 보인다
    expect(await screen.findByText('조건에 맞는 계약이 없습니다.')).toBeVisible()
    expect(screen.getByText('전체 0건')).toBeVisible()

    // when: 초기화를 누른다
    await user.click(bar().getByRole('button', { name: '초기화' }))

    // then: 안내가 사라지고 목록이 돌아온다
    await waitFor(() => expect(screen.queryByText('조건에 맞는 계약이 없습니다.')).not.toBeInTheDocument())
    expect(rows()).toHaveLength(PAGE_SIZE)
  })
})
