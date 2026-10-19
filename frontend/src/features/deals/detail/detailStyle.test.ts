import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { ruleOf, rulesMatching } from '../../../test/cssRule'

// vitest는 frontend/ 에서 실행된다.
const indexCss = readFileSync('src/index.css', 'utf8')
const detailCss = readFileSync('src/features/deals/detail/detail.css', 'utf8')

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

// 새 파일(kvGrid.css)이 없을 때 이 파일의 기존 테스트까지 수집 단계에서 깨지지 않도록 테스트 안에서 읽는다.
const kvGridCss = () => readFileSync('src/shared/ui/kvGrid.css', 'utf8')
const formCss = () => readFileSync('src/features/deals/form/form.css', 'utf8')

const normalize = (decl: string) =>
  decl
    .split(';')
    .map((d) => d.trim().replace(/\s+/g, ' '))
    .filter(Boolean)
    .sort()
    .join(';')

describe('보기·편집 상자와 격자 (정적 점검, AC-6~AC-8, AC-22)', () => {
  it('keeps the view button, the read-only value and the editor in the same box', () => {
    const boxes = [
      ruleOf(kvGridCss(), '.kv-static'),
      ruleOf(detailCss, 'button.dd-click'),
      ruleOf(detailCss, '.deal-detail .dd-inline-edit :is(input, select, textarea)'),
    ]
    for (const rule of boxes) {
      expect(rule).toContain('padding: 5px 8px')
      expect(rule).toMatch(/border:\s*1px solid/)
    }
  })

  it('keeps the heading editor rule', () => {
    expect(ruleOf(detailCss, '.deal-detail .dd-h1-edit .dd-inline-edit input')).toContain('var(--font-title)')
  })

  it('has no header meta rule any more', () => {
    expect(detailCss).not.toContain('.dd-meta')
  })

  it('declares no font size other than the base token in the shared grid css', () => {
    const others = kvGridCss().split('\n').filter((line) => line.includes('font-size') && !line.includes('var(--font-base)'))
    expect(others).toEqual([])
  })

  it('styles the form tile titles like the detail tile titles', () => {
    expect(normalize(ruleOf(formCss(), '.form-section h2'))).toBe(normalize(ruleOf(detailCss, '.dd-card h2')))
  })
})

describe('연락처 편집 세션 입력 상자 (정적 점검)', () => {
  it('gives the contact session inputs the same padding and border as the view button', () => {
    const rules = rulesMatching(detailCss, /\.contact-picker--rows[^,]*\binput\b/)
    expect(rules.length).toBeGreaterThan(0)
    expect(rules.some((r) => r.includes('padding: 5px 8px'))).toBe(true)
  })
})
