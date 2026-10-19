import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// vitest는 frontend/ 에서 실행된다.
const css = readFileSync('src/features/deals/form/form.css', 'utf8')

describe('form.css (정적 점검)', () => {
  it('does not cap the form page narrower than the detail page', () => {
    const found = /(?:^|\})\s*\.deal-form-page\s*\{([^}]*)\}/m.exec(css)
    expect(found).not.toBeNull()
    expect(found?.[1] ?? '').not.toContain('max-width')
  })
})
