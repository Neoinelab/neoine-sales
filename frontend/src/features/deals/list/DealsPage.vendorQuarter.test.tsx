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

describe('Quarter 단독 선택 (AC-18)', () => {
  it('enables the quarter checkboxes without a year and offers Q1 to Q4 and the all button', async () => {
    const { user } = await listReady()

    expect(quarterButton('전체')).toBeEnabled()
    const panel = await openQuarterPanel(user)
    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual(['1', '2', '3', '4'])
    expect(panel.getAllByRole('checkbox').map((c) => c.closest('label')?.textContent)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(panel.getByRole('button', { name: '전체' })).toBeVisible()
  })

  it('puts the quarter next to year=all in the URL and lists that quarter of this year', async () => {
    const { user, location } = await listReady()

    await toggleQuarter(user, 'Q4')

    await waitFor(() => expect(location()).toContain('quarter=4'))
    expect(location()).toContain('year=all')
    const thisYearQ4 = (await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })).items
    expect(thisYearQ4.length).toBeGreaterThan(0)
    await waitFor(() => expect(dataRows()).toHaveLength(Math.min(thisYearQ4.length, 20)))
    expect(quarterButton('Q4')).toBeInTheDocument()
  })

  it('keeps the chosen quarter when the year is cleared', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=3')
    await screen.findByLabelText('Quarter')

    await user.selectOptions(screen.getByLabelText('연도'), '전체')

    expect(location()).toContain('quarter=3')
    expect(location()).toContain('year=all')
    expect(quarterButton('Q3')).toBeInTheDocument()
  })

  it('keeps the quarter when a year is chosen later', async () => {
    const { user, location } = await listReady()
    await toggleQuarter(user, 'Q2')

    await user.selectOptions(screen.getByLabelText('연도'), '2027')

    expect(location()).toContain('quarter=2')
    expect(location()).toContain('year=2027')
  })

  it('tells that a quarter without a year means this year', async () => {
    const { user } = await listReady()
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()

    await toggleQuarter(user, 'Q2')

    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
    expect(describedText(quarterButton('Q2'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })

  it('links the hint to the Quarter button', async () => {
    await renderAt('/deals?quarter=1')
    await screen.findByLabelText('Quarter')

    expect(describedText(quarterButton('Q1'))).toBe('연도가 전체이면 올해(2026) 기준입니다.')
  })
})

describe('Vendor 필터와 Solution 텍스트 필터 (AC-15)', () => {
  it('uses the vendor id as the option value and the name as the label', async () => {
    await listReady()

    const option = within(screen.getByLabelText('Vendor')).getByRole('option', { name: 'Okta' })
    expect(option).toHaveValue(String(seedVendorId('Okta')))
    expect(optionNames(screen.getByLabelText('Vendor'))).toEqual([
      '전체', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
  })

  it('shows Solution as a text input, not a select', async () => {
    await listReady()

    const solution = screen.getByLabelText('Solution')
    expect(solution.tagName).toBe('INPUT')
    expect(within(solution).queryAllByRole('option')).toHaveLength(0)
  })

  it('filters by the vendor id and then by the solution text', async () => {
    const { user, location } = await listReady()

    await user.selectOptions(screen.getByLabelText('Vendor'), 'Silverfort')
    await waitFor(() => expect(dataRows()).toHaveLength(7))
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    await user.type(screen.getByLabelText('Solution'), 'mfa')
    await user.click(screen.getByRole('button', { name: '검색' }))
    await waitFor(() => expect(dataRows()).toHaveLength(3))
    expect(location()).toContain('solution=mfa')
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)
  })

  it('does not fill the vendor in when only a solution text is searched', async () => {
    const { user, location } = await listReady()

    await user.type(screen.getByLabelText('Solution'), 'SSO')
    await user.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(dataRows()).toHaveLength(3))
    expect(location()).not.toContain('vendor=')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  it('restores the vendor and the solution text from the URL', async () => {
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}&solution=ITDR`)

    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Silverfort'))
    expect(screen.getByLabelText('Solution')).toHaveValue('ITDR')
    await waitFor(() => expect(dataRows()).toHaveLength(4))
  })

  it('ignores an old name-based vendor in the URL and lists everything', async () => {
    await renderAt('/deals?vendor=Okta')

    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(dataRows()).toHaveLength(20)
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  it('treats an old numeric solution id in the URL as plain text', async () => {
    await renderAt('/deals?solution=12')

    await waitFor(() => expect(screen.getByLabelText('Solution')).toHaveValue('12'))
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})

describe('월 선택 표시 (R1 Minor 2·3)', () => {
  it('shows the month when it belongs to the quarter in the URL', async () => {
    await renderAt('/deals?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    expect(quarterButton('Q4')).toBeInTheDocument()
    expect(screen.getByLabelText('월')).toHaveValue('11')
  })

  it('tells that a month without a year means this year', async () => {
    await renderAt('/deals?month=3')
    await screen.findByLabelText('월')

    const label = screen.getByLabelText('월').closest('label') as HTMLElement
    expect(within(label).getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
  })

  it('does not show the this-year hint when a year is chosen with the month', async () => {
    await renderAt('/deals?year=2026&month=3')
    await screen.findByLabelText('월')

    expect(screen.queryByText(/연도가 전체이면/)).not.toBeInTheDocument()
  })
})
