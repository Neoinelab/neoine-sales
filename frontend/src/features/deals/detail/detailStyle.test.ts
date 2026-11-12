import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { ruleOf, rulesMatching } from '../../../test/cssRule'

// vitest는 frontend/ 에서 실행된다.
const indexCss = readFileSync('src/index.css', 'utf8')
const detailCss = readFileSync('src/features/deals/detail/detail.css', 'utf8')

describe('폰트 크기 규칙 (정적 점검)', () => {
  it('h1과 상단 메뉴 링크는 하나의 공유 변수로 글자 크기를 정한다', () => {
    // when: index.css에서 h1과 상단 메뉴 링크 규칙을 찾는다
    const h1Rule = ruleOf(indexCss, 'h1')
    const navRule = ruleOf(indexCss, '.topbar nav a')
    // then: 둘 다 제목 글자 크기 변수를 쓰고 변수는 rem 값으로 정의된다
    expect(h1Rule).toContain('font-size: var(--font-title)')
    expect(navRule).toContain('font-size: var(--font-title)')
    expect(indexCss).toMatch(/--font-title:\s*[\d.]+rem/)
  })

  it('.deal-detail 아래 제목이 아닌 모든 글자 크기를 하나의 기본 토큰으로 통일한다', () => {
    // when·then: 기본 토큰 정의와 통일 규칙을 문자열로 확인한다
    expect(indexCss).toMatch(/--font-base:\s*[\d.]+rem/)
    expect(detailCss).toMatch(/\.deal-detail :not\(h1[^{]*\{[^}]*font-size:\s*var\(--font-base\)/)
  })

  it('detail.css는 통일 규칙과 제목 밖에서 다른 font-size를 선언하지 않는다', () => {
    // when: font-size가 든 줄 중 기본 토큰도 제목도 아닌 줄을 모은다
    const others = detailCss
      .split('\n')
      .filter((line) => line.includes('font-size') && !line.includes('var(--font-base)') && !/\bh[123]\b/.test(line))
    // then: 그런 줄이 없다
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

describe('보기·편집 상자와 격자 (정적 점검)', () => {
  it('보기 버튼, 읽기 전용 값, 편집 입력은 같은 상자 모양을 쓴다', () => {
    // when: 세 요소의 규칙을 읽는다
    const boxes = [
      ruleOf(kvGridCss(), '.kv-static'),
      ruleOf(detailCss, 'button.dd-click'),
      ruleOf(detailCss, '.deal-detail .dd-inline-edit :is(input, select, textarea)'),
    ]
    // then: 모두 같은 안쪽 여백과 테두리를 가진다
    for (const rule of boxes) {
      expect(rule).toContain('padding: 5px 8px')
      expect(rule).toMatch(/border:\s*1px solid/)
    }
  })

  it('제목 편집 입력은 제목 글자 크기 변수를 쓴다', () => {
    // when: 제목 편집 규칙을 확인한다
    const actual = ruleOf(detailCss, '.deal-detail .dd-h1-edit .dd-inline-edit input')
    // then: 제목 편집 입력이 제목 글자 크기 변수를 쓴다
    expect(actual).toContain('var(--font-title)')
  })

  it('머리 메타 규칙은 더 이상 없다', () => {
    // when·then: detail.css에 .dd-meta가 없다
    expect(detailCss).not.toContain('.dd-meta')
  })

  it('공유 격자 CSS는 기본 토큰 말고 다른 글자 크기를 선언하지 않는다', () => {
    // when: font-size가 든 줄 중 기본 토큰이 아닌 줄을 모은다
    const others = kvGridCss().split('\n').filter((line) => line.includes('font-size') && !line.includes('var(--font-base)'))
    // then: 그런 줄이 없다
    expect(others).toEqual([])
  })

  it('폼 타일 제목은 상세 타일 제목과 같은 모양이다', () => {
    // when: 두 규칙의 선언을 정규화해 비교한다
    const actual = normalize(ruleOf(formCss(), '.form-section h2'))
    // then: 폼 타일 제목 규칙이 상세 타일 제목 규칙과 같다
    expect(actual).toBe(normalize(ruleOf(detailCss, '.dd-card h2')))
  })
})

describe('연락처 편집 세션 입력 상자 (정적 점검)', () => {
  it('연락처 편집 세션 입력은 보기 버튼과 같은 안쪽 여백과 테두리를 가진다', () => {
    // when: 연락처 편집 세션 입력 규칙을 모은다
    const rules = rulesMatching(detailCss, /\.contact-picker--rows[^,]*\binput\b/)
    // then: 규칙이 있고 그중 하나가 보기 버튼과 같은 여백을 가진다
    expect(rules.length).toBeGreaterThan(0)
    expect(rules.some((r) => r.includes('padding: 5px 8px'))).toBe(true)
  })
})
