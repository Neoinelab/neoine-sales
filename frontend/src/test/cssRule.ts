/** CSS 정적 점검 도우미(운영 코드에서 쓰지 않는다). jsdom은 CSS를 계산하지 못하므로 선언을 문자열로 점검한다. */

/** 줄 맨 앞(또는 `}` 뒤)에서 시작하는 선택자 규칙의 선언 본문. 없으면 오류. */
export function ruleOf(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const found = new RegExp(`(?:^|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`, 'm').exec(css)
  if (!found) throw new Error(`규칙 없음: ${selector}`)
  return found[1] ?? ''
}

/** 선택자가 `pattern`에 맞는 모든 규칙의 선언 본문. */
export function rulesMatching(css: string, pattern: RegExp): string[] {
  const bodies: string[] = []
  for (const m of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (pattern.test((m[1] ?? '').trim())) bodies.push(m[2] ?? '')
  }
  return bodies
}
