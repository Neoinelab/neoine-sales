import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// vitest는 frontend/ 에서 실행된다.
const css = readFileSync('src/features/deals/form/form.css', 'utf8')

describe('form.css (정적 점검)', () => {
  // Deal 폼 페이지는 상세 화면보다 좁게 폭을 제한하지 않는다.
  it('does not cap the form page narrower than the detail page', () => {
    // when: .deal-form-page 규칙을 찾는다(전제: form.css를 읽었다)
    const found = /(?:^|\})\s*\.deal-form-page\s*\{([^}]*)\}/m.exec(css)
    // then: 규칙이 있고 max-width가 없다
    expect(found).not.toBeNull()
    expect(found?.[1] ?? '').not.toContain('max-width')
  })
})
