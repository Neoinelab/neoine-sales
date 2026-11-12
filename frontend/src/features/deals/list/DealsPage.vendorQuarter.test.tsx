import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, describedText, openQuarterPanel, quarterButton, toggleQuarter } from './testHelpers'

/** 시드 날짜가 기준일 상대값이고 "올해" 안내가 시계에 의존하므로 기준일을 고정한다(2026-10-15). */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)

async function listReady() {
  const view = await renderAt(ALL_DEALS)
  await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
  const vendor = screen.getByLabelText('Vendor')
  await within(vendor).findByRole('option', { name: 'Silverfort' })
  return view
}

describe('Quarter 단독 선택', () => {
  // 연도 없이도 Quarter 체크박스를 쓸 수 있다
  // 테스트 코드: DL-076
  it('enables the quarter checkboxes without a year and offers Q1 to Q4 and the all button', async () => {
    // when: Quarter 묶음을 확인한다 (전제: 연도가 전체인 목록)
    const { user } = await listReady()

    // then: 체크박스가 활성이고 Q1~Q4·전체가 있다
    expect(quarterButton('전체')).toBeEnabled()
    const panel = await openQuarterPanel(user)
    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual(['1', '2', '3', '4'])
    expect(panel.getAllByRole('checkbox').map((c) => c.closest('label')?.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(panel.getByRole('button', { name: '전체' })).toBeVisible()
  })

  // 분기를 고르면 year=all 옆에 URL로 쓰고 올해 그 분기를 보인다
  // 테스트 코드: DL-077
  it('puts the quarter next to year=all in the URL and lists that quarter of this year', async () => {
    // given: 연도가 전체인 목록
    const { user, location } = await listReady()

    // when: 분기를 고른다
    await toggleQuarter(user, 'Q4')

    // then: URL에 year=all과 quarter가 있고 올해 그 분기 Deal이 보인다
    await waitFor(() => expect(location()).toContain('quarter=4'))
    expect(location()).toContain('year=all')
    const thisYearQ4 = (await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })).items
    expect(thisYearQ4.length).toBeGreaterThan(0)
    await waitFor(() => expect(dataRows()).toHaveLength(Math.min(thisYearQ4.length, 20)))
    expect(quarterButton('Q4')).toBeInTheDocument()
  })

  // 연도를 지워도 고른 분기는 유지된다
  // 테스트 코드: DL-077
  it('keeps the chosen quarter when the year is cleared', async () => {
    // given: 연도와 분기가 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=3')
    await screen.findByLabelText('Quarter')

    // when: 연도를 전체로 한다
    await user.selectOptions(screen.getByLabelText('연도'), '전체')

    // then: 분기가 유지된다
    expect(location()).toContain('quarter=3')
    expect(location()).toContain('year=all')
    expect(quarterButton('Q3')).toBeInTheDocument()
  })

  // 나중에 연도를 골라도 분기는 유지된다
  // 테스트 코드: DL-077
  it('keeps the quarter when a year is chosen later', async () => {
    // given: 분기만 걸린 목록
    const { user, location } = await listReady()
    await toggleQuarter(user, 'Q2')

    // when: 연도를 고른다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    // then: 분기가 유지된다
    expect(location()).toContain('quarter=2')
    expect(location()).toContain('year=2027')
  })

  // 연도 없는 분기는 올해 기준 안내를 보인다
  // 테스트 코드: DL-077
  it('tells that a quarter without a year means this year', async () => {
    // given: 연도가 전체이고 분기를 고르지 않은 목록
    const { user } = await listReady()
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()

    // when: Q2를 누른다
    await toggleQuarter(user, 'Q2')
    // then: 올해 기준 안내가 보인다
    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(describedText(quarterButton('Q2'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')

    // when: 연도를 2027로 고른다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    // then: 안내가 사라진다
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })

  // 안내가 Quarter 버튼에 접근성으로 연결된다
  // 테스트 코드: DL-077
  it('links the hint to the Quarter button', async () => {
    // given: 안내가 보이는 목록
    await renderAt('/deals?quarter=1')

    // when: 접근성 설명을 확인한다
    await screen.findByLabelText('Quarter')

    // then: Quarter 버튼의 설명이 안내이다
    expect(describedText(quarterButton('Q1'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
  })
})

describe('Vendor 필터와 Solution 텍스트 필터', () => {
  // Vendor 선택지의 값은 id, 표시는 이름이다
  // 테스트 코드: DL-066
  it('uses the vendor id as the option value and the name as the label', async () => {
    // given: 시드 Vendor
    await listReady()

    // when: 선택지를 확인한다
    const option = within(screen.getByLabelText('Vendor')).getByRole('option', { name: 'Okta' })

    // then: 값은 id, 표시는 이름이다
    expect(option).toHaveValue(String(seedVendorId('Okta')))
    expect(optionNames(screen.getByLabelText('Vendor'))).toEqual([
      '전체', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
  })

  // Solution은 선택 상자가 아니라 텍스트 입력이다
  // 테스트 코드: DL-065
  it('shows Solution as a text input, not a select', async () => {
    // given: 목록 필터 바
    await listReady()

    // when: 화면을 확인한다
    const solution = screen.getByLabelText('Solution')

    // then: Solution이 텍스트 입력이다
    expect(solution.tagName).toBe('INPUT')
    expect(within(solution).queryAllByRole('option')).toHaveLength(0)
  })

  // Vendor id로 거른 뒤 Solution 텍스트로 거른다
  // 테스트 코드: DL-066
  it('filters by the vendor id and then by the solution text', async () => {
    // given: 시드 목록
    const { user, location } = await listReady()

    // when: Vendor를 고른다
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Silverfort')
    // then: Vendor id로 거른 7행이 보인다
    await waitFor(() => expect(dataRows()).toHaveLength(7))
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    // when: Solution을 입력하고 검색한다
    await user.type(screen.getByLabelText('Solution'), 'mfa')
    await user.click(screen.getByRole('button', { name: '검색' }))
    // then: Solution 텍스트로 더 거른 3행이 보인다
    await waitFor(() => expect(dataRows()).toHaveLength(3))
    expect(location()).toContain('solution=mfa')
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)
  })

  // Solution만 검색해도 Vendor를 채우지 않는다
  // 테스트 코드: DL-067
  it('does not fill the vendor in when only a solution text is searched', async () => {
    // given: 시드 목록
    const { user, location } = await listReady()

    // when: Solution만 검색한다
    await user.type(screen.getByLabelText('Solution'), 'SSO')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: Vendor 선택은 전체 그대로다
    await waitFor(() => expect(dataRows()).toHaveLength(3))
    expect(location()).not.toContain('vendor=')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  // URL로 Vendor와 Solution 텍스트를 복원한다
  // 테스트 코드: DL-071
  it('restores the vendor and the solution text from the URL', async () => {
    // when: 그 주소를 연다 (전제: Vendor·Solution이 든 주소)
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}&solution=ITDR`)

    // then: 두 칸이 복원된다
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Silverfort'))
    expect(screen.getByLabelText('Solution')).toHaveValue('ITDR')
    await waitFor(() => expect(dataRows()).toHaveLength(4))
  })

  // 예전 이름 기반 Vendor는 무시하고 전체를 보인다
  // 테스트 코드: DL-072
  it('ignores an old name-based vendor in the URL and lists everything', async () => {
    // given: 이름 기반 Vendor 값이 든 주소
    await renderAt('/deals?vendor=Okta')

    // when: 그 주소를 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 조건 없이 전체가 보인다
    expect(dataRows()).toHaveLength(20)
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  // 예전 숫자 solution id는 일반 텍스트로 본다
  // 테스트 코드: DL-072
  it('treats an old numeric solution id in the URL as plain text', async () => {
    // when: 그 주소를 연다 (전제: 숫자 solution이 든 주소)
    await renderAt('/deals?solution=12')

    // then: 텍스트 조건으로 쓰인다
    await waitFor(() => expect(screen.getByLabelText('Solution')).toHaveValue('12'))
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})

describe('월 선택 표시 (R1 Minor 2·3)', () => {
  // URL 월이 분기에 속하면 월이 보인다
  // 테스트 코드: DL-078
  it('shows the month when it belongs to the quarter in the URL', async () => {
    // given: 분기와 월이 든 주소
    await renderAt('/deals?year=2026&quarter=4&month=11')

    // when: 그 주소를 연다
    await screen.findByLabelText('월')

    // then: 월 칸이 그 월이다
    expect(quarterButton('Q4')).toBeInTheDocument()
    expect(screen.getByLabelText('월')).toHaveValue('11')
  })

  // 연도 없는 월은 올해 기준 안내를 보인다
  // 테스트 코드: DL-077
  it('tells that a month without a year means this year', async () => {
    // given: 연도 전체에서 월을 고른 목록
    await renderAt('/deals?month=3')
    await screen.findByLabelText('월')

    // when: 화면을 확인한다
    const label = screen.getByLabelText('월').closest('label') as HTMLElement

    // then: 올해 기준 안내가 보인다
    expect(within(label).getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
  })

  // 연도를 함께 고르면 올해 안내를 보이지 않는다
  // 테스트 코드: DL-077
  it('does not show the this-year hint when a year is chosen with the month', async () => {
    // given: 연도와 월이 든 주소
    await renderAt('/deals?year=2026&month=3')

    // when: 그 주소를 연다
    await screen.findByLabelText('월')

    // then: 안내가 없다
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })
})
