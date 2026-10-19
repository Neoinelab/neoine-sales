import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../test/cssRule'

// vitest는 frontend/ 에서 실행된다. jsdom은 CSS를 계산하지 못하므로 선언을 정적으로 점검한다.
const read = () => readFileSync('src/shared/ui/kvGrid.css', 'utf8')

describe('kvGrid.css (정적 점검)', () => {
  it('declares no font size', () => {
    expect(read()).not.toContain('font-size')
  })

  it('lays out up to three columns that collapse to one', () => {
    const grid = ruleOf(read(), '.kv-grid')
    expect(grid).toContain('repeat(auto-fill')
    expect(grid).toContain('/ 3)')
  })

  it('aligns labels in a fixed column and values on the baseline', () => {
    const row = ruleOf(read(), '.kv-grid > :is(.kv-row, .field)')
    expect(row).toContain('var(--kv-label-w) minmax(0, 1fr)')
    expect(row).toContain('align-items: baseline')
    expect(ruleOf(read(), '.kv-grid dd')).toContain('overflow-wrap: anywhere')
  })

  it('lets a long value shrink inside its column', () => {
    expect(ruleOf(read(), '.kv-grid > :is(.kv-row, .field)')).toContain('min-width: 0')
  })
})
