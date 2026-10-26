import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../../test/cssRule'

// vitest는 frontend/ 에서 실행된다. jsdom은 CSS를 계산하지 못하므로 선언을 문자열로 점검한다.
const css = readFileSync('src/features/deals/list/list.css', 'utf8')

describe('빠른 조건 줄 스타일 (정적 점검, AC-15~17)', () => {
  it('makes the quick row a full-width wrapping flex row', () => {
    const rule = ruleOf(css, '.deal-filter-actions')
    expect(rule).toContain('grid-column: 1 / -1')
    expect(rule).toContain('display: flex')
    expect(rule).toContain('flex-wrap: wrap')
  })

  it('keeps the three checkboxes on one line', () => {
    expect(ruleOf(css, '.deal-filter-flags')).toContain('flex-wrap: nowrap')
  })

  it('pushes the buttons to the right end', () => {
    expect(ruleOf(css, '.deal-filter-actions .filter-buttons')).toContain('margin-left: auto')
  })

  it('shows the error area full width and hides it when empty', () => {
    expect(ruleOf(css, '.deal-filter-errors')).toContain('grid-column: 1 / -1')
    expect(ruleOf(css, '.deal-filter-errors:empty')).toContain('display: none')
  })
})

describe('Deal 이름 칸의 경고 배지 (정적 점검, 2026-10-26)', () => {
  it('puts the overdue/stale badges on the same line, right of the deal name', () => {
    const rule = ruleOf(css, '.deal-name')
    expect(rule).toMatch(/display:\s*flex/)
    expect(rule).not.toMatch(/display:\s*grid/)
    expect(rule).not.toMatch(/flex-direction:\s*column/)
    expect(rule).toMatch(/align-items:\s*center/)
  })
})
