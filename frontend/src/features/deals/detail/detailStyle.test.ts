import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

// vitest는 frontend/ 에서 실행된다.
const indexCss = readFileSync('src/index.css', 'utf8')
const detailCss = readFileSync('src/features/deals/detail/detail.css', 'utf8')

/** jsdom은 CSS를 계산하지 못하므로 선언을 정적으로 점검한다. */
function ruleOf(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const found = new RegExp(`(?:^|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`, 'm').exec(css)
  if (!found) throw new Error(`규칙 없음: ${selector}`)
  return found[1] ?? ''
}

describe('폰트 크기 규칙 (정적 점검)', () => {
  it('uses one shared variable for the h1 and the top menu links', () => {
    expect(ruleOf(indexCss, 'h1')).toContain('font-size: var(--font-title)')
    expect(ruleOf(indexCss, '.topbar nav a')).toContain('font-size: var(--font-title)')
    expect(indexCss).toMatch(/--font-title:\s*[\d.]+rem/)
  })

  it('unifies every non-heading font size under .deal-detail to one base token', () => {
    expect(indexCss).toMatch(/--font-base:\s*[\d.]+rem/)
    expect(detailCss).toMatch(/\.deal-detail :not\(h1[^{]*\{[^}]*font-size:\s*var\(--font-base\)/)
  })

  it('declares no other font-size inside detail.css outside the unifying rule and headings', () => {
    const others = detailCss
      .split('\n')
      .filter((line) => line.includes('font-size') && !line.includes('var(--font-base)') && !/\bh[123]\b/.test(line))
    expect(others).toEqual([])
  })
})
