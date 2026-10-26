import { screen, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../../test/cssRule'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/** Deal 상세 탭도 Dashboard 탭과 같은 모양(2026-10-26): 제목보다 약간 작은 굵은 글자 + 글자 왼쪽 장식 아이콘. */

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

describe('Deal 상세 탭 모양', () => {
  it.each(['Deal 상세', 'Actions', 'Deal History'])('shows a decorative icon left of the %s tab label', async (name) => {
    await renderAt(await detailPath(1))

    const tab = await screen.findByRole('tab', { name })
    const icon = tab.querySelector('svg')
    expect(icon).not.toBeNull()
    expect(icon).toHaveAttribute('aria-hidden', 'true')
    expect(follows(icon as Element, within(tab).getByText(name))).toBe(true)
  })

  it('uses the same prominent tab style as the Dashboard', async () => {
    await renderAt(await detailPath(1))
    const detailTabs = (await screen.findByRole('tablist', { name: '상세 탭' })).parentElement

    expect(detailTabs).toHaveClass('tabs-prominent')
  })

  it('keeps the prominent tab label bold and between the base size and the title size', () => {
    const rule = ruleOf(readFileSync('src/shared/ui/ui.css', 'utf8'), '.tabs-prominent .tab')
    expect(rule).toContain('font-weight: 700')
    expect(rule).toContain('font-size: 1.2rem')
  })
})
