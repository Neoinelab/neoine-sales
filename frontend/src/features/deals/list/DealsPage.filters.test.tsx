import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { dealInput } from '../../../test/fake/testing'
import { ALL_DEALS, dataRows, quarterButton, toggleForecast, toggleQuarter } from './testHelpers'
import { USER_ID } from '../../../test/fake/seed/ids'
import { defaultDealsUrl, defaultDealsUrlPattern } from '../../../test/dealsUrl'

afterEach(() => vi.restoreAllMocks())

describe('필터와 정렬 (T-LIST-05~09)', () => {
  // 키워드는 검색을 눌러야 URL에 반영되고 목록이 걸러진다
  // 테스트 코드: DL-065
  it('filters by keyword on submit and keeps it in the URL', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 키워드를 입력하고 검색을 누른다
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: URL에 q가 생기고 일치하는 Deal만 보인다
    expect(location()).toBe(`/deals?year=all&q=${encodeURIComponent('한빛은행')}`)
    await screen.findByRole('row', { name: /한빛은행 PAM/ })
    expect(dataRows()).toHaveLength(3)
  })

  // 담당자를 고르면 즉시 URL에 반영된다
  // 테스트 코드: DL-066
  it('filters by owner', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('담당자'), '박영업')

    // when: 담당자 칸에서 사용자를 고른다
    await screen.findByRole('row', { name: /미래전자 EDR 교체/ })

    // then: URL에 owner가 생기고 그 담당자의 Deal만 보인다
    expect(location()).toContain(`owner=${USER_ID.park}`)
    expect(dataRows()).toHaveLength(6)
  })

  // 담당자 선택지에 퇴사자도 있다
  // 테스트 코드: DL-066
  it('offers resigned owners in the owner filter', async () => {
    // given: 퇴사한 담당자가 있는 시드
    const { user } = await renderAt(ALL_DEALS)
    const owner = await screen.findByLabelText('담당자')
    await within(owner).findByRole('option', { name: '강퇴사(퇴사)' })

    // when: 퇴사한 담당자를 고른다
    await user.selectOptions(owner, '강퇴사(퇴사)')
    await screen.findByRole('row', { name: /한빛은행 PAM/ })

    // then: 퇴사자가 선택지에 있고 그의 Deal만 보인다
    expect(dataRows()).toHaveLength(1)
  })

  // Vendor·Status·Forecast를 고르면 즉시 URL에 반영된다
  // 테스트 코드: DL-066
  it('filters by vendor, status and forecast', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const vendor = await screen.findByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Silverfort' })

    // when: Vendor를 고른다
    await user.selectOptions(vendor, 'Silverfort')
    await screen.findByRole('row', { name: /도담건설 MFA/ })
    // then: URL에 반영되고 목록이 걸러진다
    expect(dataRows()).toHaveLength(7)
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    // when: Status를 고른다
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByText(/도담건설 MFA/)
    // then: URL에 반영되고 목록이 걸러진다
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('status=contract_completed')

    // when: Status·Vendor를 전체로 돌리고 Forecast를 고른다
    await user.selectOptions(screen.getByLabelText('Status'), '전체')
    await user.selectOptions(screen.getByLabelText('Vendor'), '전체')
    await toggleForecast(user, 'Lost')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    // then: URL에 반영되고 목록이 걸러진다
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('forecast=lost')
    expect(location()).not.toContain('forecast=lost%2C')
  })

  // Product 텍스트는 검색을 눌러야 반영된다
  // 테스트 코드: DL-065
  it('applies the product text on search', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const product = screen.getByLabelText('Product')
    expect(product.tagName).toBe('INPUT')

    // when: Product를 입력한다
    await user.type(product, '  itdr  ')
    // then: 검색 전에는 URL에 product가 없다
    expect(location()).not.toContain('product=')

    // when: 검색을 누른다
    await user.click(screen.getByRole('button', { name: '검색' }))
    // then: URL에 product가 생기고 목록이 걸러진다
    await screen.findByRole('row', { name: /미래전자 ITDR/ })
    expect(location()).toContain('product=itdr')
    expect(dataRows()).toHaveLength(4)
  })

  // Product는 Enter로 반영되어 product 조건으로 간다
  // 테스트 코드: DL-065
  it('applies the product text with Enter and sends it as the product condition', async () => {
    // given: 시드 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: Product를 입력하고 Enter를 누른다
    await user.type(screen.getByLabelText('Product'), 'MFA{Enter}')

    // then: 조회 조건에 product가 실린다
    await waitFor(() => expect(dataRows()).toHaveLength(3))
    expect(list.mock.calls.at(-1)?.[0]).toMatchObject({ product: 'MFA' })
    expect(list.mock.calls.at(-1)?.[0]).not.toHaveProperty('productId')
  })

  // Product를 비우고 검색하면 URL에서 지워진다
  // 테스트 코드: DL-065
  it('removes product from the URL when it is emptied and searched', async () => {
    // given: Product가 걸린 목록
    const { user, location } = await renderAt('/deals?product=itdr')

    await screen.findByRole('row', { name: /미래전자 ITDR/ })
    expect(screen.getByLabelText('Product')).toHaveValue('itdr')

    // when: 입력을 비우고 검색한다
    await user.clear(screen.getByLabelText('Product'))
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: URL에서 product 키가 사라진다
    await waitFor(() => expect(location()).not.toContain('product'))
    await waitFor(() => expect(dataRows()).toHaveLength(20))
  })

  // Vendor를 바꿔도 Product 텍스트는 남는다
  // 테스트 코드: DL-067
  it('keeps the product text when the vendor changes', async () => {
    // given: Product가 걸린 목록
    const { user, location } = await renderAt('/deals?product=itdr')
    await screen.findByRole('row', { name: /미래전자 ITDR/ })
    const vendor = screen.getByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Silverfort' })

    // when: Vendor를 바꾼다
    await user.selectOptions(vendor, 'Silverfort')
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')

    // then: Product 입력과 URL 값이 그대로다
    expect(location()).toContain(`vendor=${seedVendorId('Okta')}`)
    expect(location()).toContain('product=itdr')
    expect(screen.getByLabelText('Product')).toHaveValue('itdr')
  })

  // 키워드와 Product를 한 번의 검색으로 함께 적용한다
  // 테스트 코드: DL-065
  it('combines keyword and product text on one search', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 키워드와 Product를 입력하고 검색한다
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.type(screen.getByLabelText('Product'), 'ITDR')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: 두 값이 URL에 함께 반영되어 AND로 걸러진다
    await waitFor(() => expect(dataRows()).toHaveLength(1))
    expect(location()).toContain('product=ITDR')
    expect(location()).toContain(`q=${encodeURIComponent('한빛은행')}`)
  })

  // 연도·Quarter 선택이 URL에 반영된다
  // 테스트 코드: DL-076
  it('puts year and quarter in the URL', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const year = String(new Date().getFullYear())
    await user.selectOptions(screen.getByLabelText('Close 연도'), year)

    // when: 연도와 Quarter를 고른다
    await toggleQuarter(user, 'Q4')

    // then: URL에 year·quarter가 쓰인다
    expect(location()).toContain(`year=${year}`)
    expect(location()).toContain('quarter=4')
  })

  // 월을 고르면 URL에 월이 쓰이고 Quarter는 유지된다
  // 테스트 코드: DL-078
  it('puts the month in the URL and keeps the quarter', async () => {
    // given: 연도·Quarter가 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByLabelText('월')

    // when: 월을 고른다
    await user.selectOptions(screen.getByLabelText('월'), '11월')

    // then: URL에 month가 생기고 quarter도 남는다
    expect(location()).toContain('month=11')
    expect(location()).toContain('quarter=4')
    expect(quarterButton('Q4')).toBeInTheDocument()
  })

  // 고른 분기에 속한 월은 분기를 바꿔도 유지된다
  // 테스트 코드: DL-079
  it('keeps the month when the chosen quarter contains it', async () => {
    // given: 월이 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&month=11')
    await screen.findByLabelText('월')

    // when: 그 월이 포함된 다른 분기 조합으로 바꾼다
    await toggleQuarter(user, 'Q4')

    // then: 월이 유지된다
    await waitFor(() => expect(location()).toContain('quarter=4'))
    expect(location()).toContain('month=11')
  })

  // 고른 분기에 없는 월은 지워진다
  // 테스트 코드: DL-079
  it('clears the month when the chosen quarter does not contain it', async () => {
    // given: 월이 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&month=11')
    await screen.findByLabelText('월')

    // when: 그 월이 없는 분기로 바꾼다
    await toggleQuarter(user, 'Q1')

    // then: 월이 지워진다
    await waitFor(() => expect(location()).toContain('quarter=1'))
    expect(location()).not.toContain('month=')
  })

  // URL의 월로 칸을 복원하고 그 달 Deal만 보인다
  // 테스트 코드: DL-071
  it('restores the month control from the URL and lists only that month', async () => {
    // given: 월이 있는 주소
    const { client } = await renderAt('/deals?year=2028&month=2')
    await screen.findByLabelText('월')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '월필터 2월', revenueDate: '2028-02-10' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '월필터 3월', revenueDate: '2028-03-10' }))

    // when: 그 주소를 연다
    await client.invalidateQueries()

    // then: 월 칸이 복원되고 그 달 Deal만 보인다
    expect(await screen.findByRole('row', { name: /월필터 2월/ })).toBeVisible()
    expect(screen.getByLabelText('월')).toHaveDisplayValue('2월')
    expect(screen.queryByRole('row', { name: /월필터 3월/ })).not.toBeInTheDocument()
    expect(dataRows()).toHaveLength(1)
  })

  // 내 딜만 체크는 즉시 반영되고 끄면 키가 지워진다
  // 테스트 코드: DL-066
  it('shows only my deals with the my-deals toggle and removes the filter when turned off', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 내 딜만을 켠다
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    // then: 내 Deal만 보인다
    expect(location()).toContain('mine=1')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    expect(dataRows()).toHaveLength(8)

    // when: 내 딜만을 끈다
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    // then: 키가 사라지고 전체가 보인다
    expect(location()).toBe('/deals?year=all')
  })

  // URL로 모든 칸을 복원한다
  // 테스트 코드: DL-071
  it('restores every control from the URL, as when coming back from a detail page', async () => {
    // given: 조건이 모두 들어 있는 주소
    await renderAt('/deals?mine=1&status=contract_completed&sort=name&order=asc')

    // when: 그 주소를 연다
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })

    // then: 모든 선택·입력·체크가 URL 값으로 복원된다
    expect(dataRows()).toHaveLength(2)
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).toBeChecked()
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  // 초기화는 모든 조건을 지우고 연도 전체 기본 조건으로 간다
  // 테스트 코드: DL-070
  it('clears every condition with the reset button and goes back to the default condition (all years)', async () => {
    // given: admin이 여러 조건을 건 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt(`/deals?q=한빛&vendor=${seedVendorId('Okta')}&product=ITDR&sort=name&order=asc`, { role: 'admin' })

    // when: 초기화를 누른다 (admin의 기본 조건은 연도 전체. sales의 연도 전체 + 내 딜만은 DL-102)
    await user.click(await screen.findByRole('button', { name: '초기화' }))

    // then: 모든 칸이 비고 주소가 /deals?year=all이다
    expect(location()).toMatch(defaultDealsUrlPattern('admin'))
    await waitFor(() => expect(screen.getByLabelText('키워드')).toHaveValue(''))
    expect(screen.getByLabelText('Product')).toHaveValue('')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    await waitFor(() => expect(Object.keys(list.mock.calls.at(-1)?.[0] ?? {}).sort()).toEqual(['limit', 'offset']))
  })

  // Expected Close 정렬은 방향을 뒤집는다
  // 테스트 코드: DL-089
  it('sorts by Expected Close and flips the direction', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: Expected Close 머리글을 누른다
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    // then: 오름차순이 되고 행 순서도 따른다
    expect(location()).toContain('sort=revenueDate')
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'ascending'))
    expect(dataRows()[0]).toHaveTextContent('도담건설 MFA')

    // when: Expected Close 머리글을 한 번 더 누른다
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    // then: 내림차순이 되고 행 순서도 따른다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('대한제조 NGFW')
  })

  // 금액 정렬은 큰 금액 먼저(자연 방향)이고 기본 정렬은 최종 업데이트다
  // 테스트 코드: DL-089
  it('sorts by amount with the largest first and marks the default sort on the last update', async () => {
    // given: 시드 목록
    const { user } = await renderAt(ALL_DEALS)

    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')

    // when: 금액 머리글을 누른다
    await user.click(screen.getByRole('button', { name: '금액(단위:원)' }))
    // then: 금액이 큰 순서(내림차순)로 정렬된다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:원)' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('한빛은행 ITDR 도입')
  })

  // 조건에 맞는 Deal이 없으면 안내 문구를 보인다
  // 테스트 코드: DL-062
  it('tells that nothing matches when a condition finds no deal', async () => {
    // when: 검색한다 (전제: 일치하는 Deal이 없는 조건)
    await renderAt('/deals?q=없는이름')

    // then: '조건에 맞는 Deal이 없습니다.'가 보인다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})

/** 최종 업데이트 기간. Fake 시계를 고정하고, 기대 결과는 같은 Fake 게이트웨이의 날짜 조회로 만든다. */
describe('최종 업데이트 기간 필터', () => {
  const NOW = '2026-10-15T09:00:00+09:00'
  const TWO_WEEKS = { from: '2026-10-01', to: '2026-10-15' }
  const THREE_MONTHS = { from: '2026-07-15', to: '2026-10-15' }

  beforeEach(() => resetMock({ now: NOW }))
  afterEach(() => {
    vi.restoreAllMocks()
    resetMock({ now: null })
  })

  const search = (location: string) => new URLSearchParams(location.split('?')[1] ?? '')
  const expectedIn = async (range: { from?: string; to?: string }) =>
    gateway.deals.list({ updatedFrom: range.from, updatedTo: range.to, limit: 100 })

  async function waitForRows(total: number) {
    await waitFor(() => expect(dataRows()).toHaveLength(total))
  }

  // 최종 업데이트 선택은 일곱 가지이고 Expected Close 기간 입력은 없다
  // 테스트 코드: DL-085
  it('no longer shows the Expected Close period inputs and offers seven options', async () => {
    // given: 시드 목록
    await renderAt(ALL_DEALS)

    // when: 최종 업데이트 선택 상자를 확인한다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 전체·프리셋 5개·직접 지정의 7개가 있다
    expect(screen.queryByLabelText('기간 시작')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('기간 끝')).not.toBeInTheDocument()
    const select = screen.getByLabelText('최종 업데이트')
    expect(select).toHaveDisplayValue('전체')
    const labels = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('종료일')).not.toBeInTheDocument()
  })

  // 최근 2주 프리셋은 서버 날짜를 URL에 쓴다
  // 테스트 코드: DL-085
  it('filters by the recent-two-weeks preset and puts the server dates in the URL', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt('/deals?year=all&page=2')
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    const all = await expectedIn({})
    const expected = await expectedIn(TWO_WEEKS)
    expect(expected.total).toBeGreaterThan(0)
    expect(expected.total).toBeLessThan(all.total)

    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    // when: 최근 2주를 고른다
    await user.selectOptions(select, '최근 2주')

    // then: URL에 서버가 푼 updated_from·updated_to가 쓰이고 목록이 걸러진다
    await waitForRows(expected.total)
    expect(search(location()).get('updated_from')).toBe(TWO_WEEKS.from)
    expect(search(location()).get('updated_to')).toBe(TWO_WEEKS.to)
    expect(search(location()).get('page')).toBeNull()
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('최근 2주')
    expect(search(location()).has('updated_period')).toBe(false)
  })

  // 긴 프리셋도 서버가 푼 날짜를 쓴다
  // 테스트 코드: DL-085
  it('uses the dates the server resolved for a longer preset', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 3개월' })).toBeEnabled())

    // when: 더 긴 프리셋을 고른다
    await user.selectOptions(select, '최근 3개월')

    // then: 서버가 푼 날짜가 URL에 쓰인다
    await waitFor(() => expect(search(location()).get('updated_from')).toBe(THREE_MONTHS.from))
    expect(search(location()).get('updated_to')).toBe(THREE_MONTHS.to)
  })

  // 전체와 초기화는 기간을 지운다
  // 테스트 코드: DL-085
  it('clears the period with 전체 and with the reset button', async () => {
    // given: 기간이 걸린 목록
    const { user, location } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}&status=prospecting`)

    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))

    // when: 전체를 고른다
    await user.selectOptions(select, '전체')
    // then: 기간 키가 지워지고 다른 조건은 남는다
    expect(search(location()).has('updated_from')).toBe(false)
    expect(search(location()).has('updated_to')).toBe(false)
    expect(search(location()).get('status')).toBe('prospecting')

    // when: 기간을 다시 걸고 초기화를 누른다
    await user.selectOptions(screen.getByLabelText('최종 업데이트'), '최근 2주')
    await waitFor(() => expect(search(location()).get('updated_from')).toBe(TWO_WEEKS.from))
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 기본 조건으로 돌아가고 기간이 전체이다
    expect(location()).toBe(defaultDealsUrl(NOW))
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체')
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  // 직접 지정은 URL을 바꾸지 않고 날짜 칸을 현재 값으로 연다
  // 테스트 코드: DL-086
  it('shows date inputs for 직접 지정, prefilled from the preset without changing the URL', async () => {
    // given: 프리셋이 걸린 목록
    const { user, location } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)

    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))
    const before = location()

    // when: 직접 지정을 고른다
    await user.selectOptions(select, '직접 지정')

    // then: 시작일·종료일 칸이 열려 현재 날짜로 채워지고 URL은 그대로다
    expect(screen.getByLabelText('시작일')).toHaveValue(TWO_WEEKS.from.replaceAll('-', '.'))
    expect(screen.getByLabelText('종료일')).toHaveValue(TWO_WEEKS.to.replaceAll('-', '.'))
    expect(location()).toBe(before)
  })

  // 전체에서 직접 지정은 빈 칸을 열고 시작일만으로도 조회된다
  // 테스트 코드: DL-086
  it('opens empty date inputs from 전체 and filters with only a start date, then clears it', async () => {
    // given: 기간이 없는 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 직접 지정을 고른다
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')
    // then: 빈 날짜 칸이 열린다
    expect(screen.getByLabelText('시작일')).toHaveValue('')
    const since = await expectedIn({ from: '2026-10-01' })

    // when: 시작일만 넣는다
    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-01' } })
    // then: 시작일만으로 조회된다
    await waitForRows(Math.min(since.total, 20))
    expect(search(location()).get('updated_from')).toBe('2026-10-01')
    expect(search(location()).has('updated_to')).toBe(false)
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('직접 지정')

    // when: 시작일을 비운다
    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '' } })
    // then: 조건이 풀린다
    await waitFor(() => expect(search(location()).has('updated_from')).toBe(false))
  })

  // yyyymmdd 입력은 ISO 날짜로 URL에 쓰인다
  // 테스트 코드: DL-086
  it('types yyyymmdd in the start date and puts the ISO date in the URL (AC-D1)', async () => {
    // given: 직접 지정 칸
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 시작일에 yyyymmdd를 입력한다
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')

    await user.type(screen.getByLabelText('시작일'), '20261001')

    // then: URL에 ISO 날짜가 쓰인다
    expect(screen.getByLabelText('시작일')).toHaveValue('2026.10.01')
    await waitFor(() => expect(search(location()).get('updated_from')).toBe('2026-10-01'))
  })

  // 덜 친 시작일은 URL을 바꾸지 않고 칸이 문구를 보인다
  // 테스트 코드: DL-086
  it('does not change the URL for a partly typed start date and shows the message after leaving (AC-D3)', async () => {
    // given: 직접 지정 칸
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')
    const before = location()

    // when: 시작일을 덜 치고 칸을 벗어난다
    await user.type(screen.getByLabelText('시작일'), '2026.10')
    await user.tab()

    // then: URL은 그대로이고 칸에 문구가 보인다
    expect(location()).toBe(before)
    expect(search(location()).has('updated_from')).toBe(false)
    expect(await screen.findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  // 없는 종료일은 URL을 바꾸지 않는다
  // 테스트 코드: DL-086
  it('does not change the URL for a non-existing end date (AC-D3)', async () => {
    // given: 직접 지정 칸
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 없는 날짜를 입력한다
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')

    await user.type(screen.getByLabelText('종료일'), '20261340')
    await user.tab()

    // then: URL은 그대로다
    expect(search(location()).has('updated_to')).toBe(false)
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
  })

  // 시작이 끝보다 늦으면 서버 문구를 배너로 보인다
  // 테스트 코드: DL-087
  it('shows the server error when the start date is after the end date', async () => {
    // given: 직접 지정 칸
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 시작일을 종료일보다 늦게 넣는다
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')

    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-10' } })
    fireEvent.change(screen.getByLabelText('종료일'), { target: { value: '2026-10-01' } })

    // then: 서버 문구가 목록 오류 배너로 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다')
    expect(search(location()).get('updated_from')).toBe('2026-10-10')
    expect(search(location()).get('updated_to')).toBe('2026-10-01')
  })

  // 프리셋과 같은 URL 날짜는 그 프리셋으로 표시된다
  // 테스트 코드: DL-088
  it('restores the preset from matching dates in the URL', async () => {
    // given: 오늘의 프리셋과 같은 날짜가 URL에 있는 주소
    await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)

    // when: 그 주소를 연다
    const select = await screen.findByLabelText('최종 업데이트')

    // then: 선택 상자가 그 프리셋이다
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  // 프리셋과 다른 날짜는 직접 지정으로 표시된다
  // 테스트 코드: DL-088
  it('shows 직접 지정 with the dates when they match no preset of today', async () => {
    // given: 프리셋에 없는 날짜가 URL에 있는 주소
    await renderAt('/deals?updated_from=2026-10-02&updated_to=2026-10-15')

    // when: 그 주소를 연다
    const select = await screen.findByLabelText('최종 업데이트')

    // then: 직접 지정과 날짜 칸이 보인다
    await waitFor(() => expect(select).toHaveDisplayValue('직접 지정'))
    expect(screen.getByLabelText('시작일')).toHaveValue('2026.10.02')
    expect(screen.getByLabelText('종료일')).toHaveValue('2026.10.15')
  })

  // 한쪽만 있어도 직접 지정으로 표시된다
  // 테스트 코드: DL-088
  it('shows 직접 지정 when only one side is in the URL', async () => {
    // given: 시작일만 URL에 있는 주소
    await renderAt('/deals?updated_to=2026-10-15')

    // when: 그 주소를 연다
    const select = await screen.findByLabelText('최종 업데이트')

    // then: 직접 지정이다
    await waitFor(() => expect(select).toHaveDisplayValue('직접 지정'))
    expect(screen.getByLabelText('시작일')).toHaveValue('')
    expect(screen.getByLabelText('종료일')).toHaveValue('2026.10.15')
  })

  // URL의 잘못된 최종 업데이트 날짜는 조회에 쓰지 않는다
  // 테스트 코드: DL-072
  it('ignores a malformed updated date in the URL for the query', async () => {
    // given: 틀린 날짜가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?updated_from=2026-02-30&updated_to=abc')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 그 주소를 연다
    const query = list.mock.calls.at(-1)?.[0]

    // then: 조회에 그 날짜가 실리지 않는다
    expect(query?.updatedFrom).toBeUndefined()
    expect(query?.updatedTo).toBeUndefined()
  })

  // 예전 from/to 키는 조건으로도 활성 필터로도 세지 않는다
  // 테스트 코드: DL-072
  it('ignores the old from/to keys: no Expected Close period and no filter marker', async () => {
    // given: 예전 from·to 키가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=all&from=2099-01-01&to=2099-12-31')

    // when: 그 주소를 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 기간 조건과 활성 필터 표시가 없다
    expect(Object.keys(list.mock.calls.at(-1)?.[0] ?? {}).sort()).toEqual(['limit', 'offset'])
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체')
  })

  // 프리셋을 못 읽어도 URL 날짜로 조회한다
  // 테스트 코드: DL-085
  it('keeps using the URL dates when the presets fail to load', async () => {
    // given: 프리셋 조회가 실패하는 Fake
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure)
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 날짜가 든 주소를 연다
    await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)

    // then: URL 날짜로 조회된다
    expect(await screen.findByRole('alert')).toHaveTextContent('기간 정보를 불러오지 못했습니다.')
    await waitFor(() => expect(list.mock.calls.at(-1)?.[0]).toMatchObject({ updatedFrom: TWO_WEEKS.from, updatedTo: TWO_WEEKS.to }))
    const select = screen.getByLabelText('최종 업데이트')
    expect(select).toHaveDisplayValue('직접 지정')
    expect(screen.getByLabelText('시작일')).toHaveValue(TWO_WEEKS.from.replaceAll('-', '.'))
    expect(within(select).getByRole('option', { name: '최근 2주' })).toBeDisabled()
    expect(within(select).getByRole('option', { name: '최근 6개월' })).toBeDisabled()
  })

  // 뒤로 가기로 날짜가 사라지면 전체로 돌아가 날짜 칸이 닫힌다
  // 테스트 코드: DL-088
  it('goes back to 전체 and hides the date inputs when browser back removes the custom dates', async () => {
    // given: 직접 지정을 연 목록
    const { user, location, goTo } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 브라우저 뒤로 가기를 한다
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')
    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-01' } })

    // then: 전체로 표시되고 날짜 칸이 닫힌다
    await waitFor(() => expect(search(location()).get('updated_from')).toBe('2026-10-01'))

    goTo(-1)

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await waitFor(() => expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('종료일')).not.toBeInTheDocument()
  })

  // 뒤로 가기로 날짜가 프리셋 범위로 돌아오면 그 프리셋이 표시된다
  // 테스트 코드: DL-088
  it('shows the matching preset when browser back returns the custom dates to a preset range', async () => {
    // given: 최근 2주 프리셋이 걸린 목록
    const { user, location, goTo } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))

    // when: 직접 지정으로 바꾸고 종료일을 고친다
    await user.selectOptions(select, '직접 지정')
    fireEvent.change(screen.getByLabelText('종료일'), { target: { value: '2026-10-14' } })
    // then: URL의 종료일이 바뀌고 직접 지정으로 표시된다
    await waitFor(() => expect(search(location()).get('updated_to')).toBe('2026-10-14'))
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('직접 지정')

    // when: 브라우저 뒤로 가기를 한다
    goTo(-1)

    // then: 프리셋 표시로 돌아온다
    await waitFor(() => expect(search(location()).get('updated_to')).toBe(TWO_WEEKS.to))
    await waitFor(() => expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('최근 2주'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  // 프리셋을 고를 때마다 서버에 다시 물어 새 날짜를 쓴다
  // 테스트 코드: DL-085
  it('asks the server for the periods again when a preset is chosen and uses the new dates', async () => {
    // given: 서버 날짜가 바뀐 상황
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const nextDay = { from: '2026-10-02', to: '2026-10-16' }
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (spy.mock.calls.length === 1) return original()
      const first = await original()
      return {
        today: nextDay.to,
        periods: first.periods.map((p) => (p.key === '2w' ? { ...p, ...nextDay } : p)),
        upcoming: first.upcoming,
      }
    })
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // 첫 응답은 화면을 열 때의 날짜(10-15), 두 번째부터는 자정이 지난 날짜(10-16)로 응답한다.
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    const callsBeforeChoosing = spy.mock.calls.length

    // when: 프리셋을 고른다
    await user.selectOptions(select, '최근 2주')

    // then: 다시 푼 날짜가 URL에 쓰인다
    await waitFor(() => expect(search(location()).get('updated_from')).toBe(nextDay.from))
    expect(search(location()).get('updated_to')).toBe(nextDay.to)
    expect(spy.mock.calls.length).toBeGreaterThan(callsBeforeChoosing)
  })

  // 다시 묻기가 실패하면 URL을 두고 오류 배너를 보인다
  // 테스트 코드: DL-085
  it('keeps the URL dates and shows the error when asking for the periods again fails on choosing a preset', async () => {
    // given: 프리셋 재조회가 실패하는 Fake
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 다시 불러오지 못했습니다.',
    })
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    let failing = false
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (failing) throw failure
      return original()
    })
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    failing = true

    // when: 프리셋을 고른다
    await user.selectOptions(select, '최근 2주')

    // then: URL은 그대로이고 오류 배너가 보인다
    // 같은 쿼리를 쓰는 화면 쪽 배너와 겹쳐 alert가 둘일 수 있어 모두 모아 본다.
    const alerts = await screen.findAllByRole('alert', undefined, { timeout: 15000 })
    expect(alerts.map((a) => a.textContent)).toContain('기간 정보를 다시 불러오지 못했습니다.')
    expect(search(location()).has('updated_from')).toBe(false)
    expect(search(location()).has('updated_to')).toBe(false)
    // 재시도 횟수·간격은 구현에 맡기므로 재시도가 끝날 때까지 넉넉히 기다린다.
  }, 20000)
})
