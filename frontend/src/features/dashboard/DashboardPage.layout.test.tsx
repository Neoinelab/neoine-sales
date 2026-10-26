import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { NOW } from './testHelpers'

/** 화면 배치(2026-10-26): 탭이 최상단에 오고 검색 조건은 각 탭 패널 위쪽에 들어간다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

describe('Dashboard 배치', () => {
  it.each(['status', 'forecast'])('puts the filters at the top of the %s tab panel', async (tab) => {
    await renderAt(`/dashboard?tab=${tab}`)

    const panel = await screen.findByRole('tabpanel')
    const form = within(panel).getByRole('form', { name: 'Dashboard 필터' })
    const firstHeading = await within(panel).findAllByRole('heading', { level: 2 })
    expect(follows(form, firstHeading[0] as Element)).toBe(true)
  })

  it('shows the tabs before anything else below the page title', async () => {
    await renderAt('/dashboard')

    const tablist = await screen.findByRole('tablist', { name: 'Dashboard 보기' })
    const hint = await screen.findByText(/기간은 Expected Close 기준/)
    expect(follows(tablist, hint)).toBe(true)
    expect(within(screen.getByRole('tabpanel')).getByText(/기간은 Expected Close 기준/)).toBeVisible()
  })

  it.each(['Status', 'Forecast'])('shows a decorative icon left of the %s tab label', async (name) => {
    await renderAt('/dashboard')

    const tab = await screen.findByRole('tab', { name })
    const icon = tab.querySelector('svg')
    expect(icon).not.toBeNull()
    expect(icon).toHaveAttribute('aria-hidden', 'true')
    expect(follows(icon as Element, within(tab).getByText(name))).toBe(true)
  })
})
