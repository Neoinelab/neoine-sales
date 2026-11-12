import { screen, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../../test/cssRule'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/** Deal 상세 탭도 Dashboard 탭과 같은 모양(2026-10-26): 제목보다 약간 작은 굵은 글자 + 글자 왼쪽 장식 아이콘. */

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

describe('Deal 상세 탭 모양', () => {
  // 탭 이름 왼쪽에 장식 아이콘이 있다(모양, BDD 밖).
  it.each(['Deal 상세', 'Actions', 'Deal History'])('shows a decorative icon left of the %s tab label', async (name) => {
    // given: Deal 상세 화면
    await renderAt(await detailPath(1))

    const tab = await screen.findByRole('tab', { name })

    // when: 탭 목록을 본다
    const icon = tab.querySelector('svg')

    // then: 각 탭 이름 왼쪽에 장식 아이콘이 있다
    expect(icon).not.toBeNull()
    expect(icon).toHaveAttribute('aria-hidden', 'true')
    expect(follows(icon as Element, within(tab).getByText(name))).toBe(true)
  })

  // 탭이 Dashboard와 같은 강조 탭 모양이다(BDD 밖).
  it('uses the same prominent tab style as the Dashboard', async () => {
    // given: Deal 상세 화면
    await renderAt(await detailPath(1))

    // when: 탭 클래스를 본다
    const detailTabs = (await screen.findByRole('tablist', { name: '상세 탭' })).parentElement

    // then: Dashboard와 같은 강조 탭 클래스다
    expect(detailTabs).toHaveClass('tabs-prominent')
  })

  // 강조 탭 글자는 굵고 기본 크기와 제목 크기 사이다(BDD 밖).
  it('keeps the prominent tab label bold and between the base size and the title size', () => {
    // when: 글자 크기·굵기를 읽는다 (전제: 탭 스타일 정의)
    const rule = ruleOf(readFileSync('src/shared/ui/ui.css', 'utf8'), '.tabs-prominent .tab')

    // then: 굵고 기본 크기와 제목 크기 사이다
    expect(rule).toContain('font-weight: 700')
    expect(rule).toContain('font-size: 1.2rem')
  })
})
