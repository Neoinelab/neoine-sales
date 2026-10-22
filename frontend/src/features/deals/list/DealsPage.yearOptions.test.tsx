import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/** Dashboard Drill-down(`/deals?year=…`)이 연도 select에서 "전체"로 보이면 안 된다(AC-17). 기준일 2026-10-15. */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)

describe('Deal 목록 연도 선택지에 URL 연도 포함 (AC-17)', () => {
  it('shows an out-of-range year from the URL as the selected option', async () => {
    await renderAt('/deals?year=2024')

    const year = await screen.findByLabelText('연도')
    expect(year).toHaveDisplayValue('2024')
    expect(optionNames(year)).toContain('2024')
  })

  it('keeps the default options and no duplicate when the URL year is already offered', async () => {
    await renderAt('/deals?year=2026')

    const year = await screen.findByLabelText('연도')
    expect(year).toHaveDisplayValue('2026')
    expect(optionNames(year)).toEqual(['전체', '2025', '2026', '2027', '2028'])
  })
})
