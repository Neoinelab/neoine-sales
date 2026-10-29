import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * AC-D7(E8): 날짜 입력은 shared/ui/DateInput.tsx만 native date 칸을 쓴다.
 * 우회 패턴(동적 type, 객체 리터럴, spread)도 잡는다. 판정 함수 `violations`는 아래 가짜 소스로 따로 검증한다.
 */
const SRC = join(__dirname, '..')
const ALLOWED = join('shared', 'ui', 'DateInput.tsx')

const INPUT_TAG = /<input\b(?:=>|[^>])*>/g
const DATE_LITERAL = /\btype\s*=\s*(?:"date"|'date'|\{\s*(?:"date"|'date'|`date`)\s*\})/
const DYNAMIC_TYPE = /\btype\s*=\s*\{(?!\s*(?:"|'|`))/
const OBJECT_DATE = /\btype\s*:\s*(?:"date"|'date'|`date`)/
const SPREAD = /\{\.\.\./
const SAFE_LITERAL_TYPE = /\btype\s*=\s*(?:"(?!date")[a-z-]+"|'(?!date')[a-z-]+')/

/** `<input type={변수}>`가 'date'가 될 수 없음을 사람이 확인한 파일(날짜는 DateInput으로 갈라낸다). */
const DYNAMIC_TYPE_FILES = [
  join('features', 'admin', 'contacts', 'ContactForm.tsx'),
  join('features', 'deals', 'detail', 'InlineControl.tsx'),
  join('features', 'deals', 'form', 'FormField.tsx'),
  join('shared', 'ui', 'fields.tsx'),
]

/** 소스 한 파일이 어긴 규칙 이름들. */
export function violations(file: string, source: string): string[] {
  if (file === ALLOWED) return []
  const found: string[] = []
  const tags = source.match(INPUT_TAG) ?? []
  if (tags.some((t) => DATE_LITERAL.test(t))) found.push('literal type date')
  if (tags.some((t) => DYNAMIC_TYPE.test(t)) && !DYNAMIC_TYPE_FILES.includes(file)) found.push('dynamic type')
  if (DYNAMIC_TYPE_FILES.includes(file) && source.includes("'date'") && !source.includes('<DateInput')) found.push('dynamic type without DateInput')
  if (tags.some((t) => SPREAD.test(t) && !SAFE_LITERAL_TYPE.test(t) && !DYNAMIC_TYPE.test(t))) found.push('spread without explicit type')
  if (OBJECT_DATE.test(source)) found.push('object literal type date')
  return found
}

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return relative(SRC, path) === 'test' ? [] : sources(path)
    return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : []
  })
}

describe('violations()', () => {
  it('flags a literal date input in every spelling', () => {
    for (const attr of ['type="date"', "type='date'", "type={'date'}", 'type={"date"}', 'type={`date`}']) {
      expect(violations('x/A.tsx', `const a = <input ${attr} value={v} onChange={(e) => set(e.target.value)} />`)).toContain('literal type date')
    }
  })

  it('flags a date literal that comes after an arrow function attribute', () => {
    expect(violations('x/A.tsx', `<input onChange={(e) => set(e.target.value)} type="date" />`)).toContain('literal type date')
  })

  it('flags a dynamic type outside the reviewed files', () => {
    expect(violations('x/A.tsx', `<input type={kind} value={v} />`)).toContain('dynamic type')
    expect(violations('x/A.tsx', `<input\n  type={cond ? 'date' : 'text'}\n/>`)).toContain('dynamic type')
  })

  it('flags an object literal with type date', () => {
    expect(violations('x/A.tsx', `const props = { type: 'date', value }`)).toContain('object literal type date')
    expect(violations('x/a.ts', `const props = { type: "date" }`)).toContain('object literal type date')
  })

  it('flags a spread input without an explicit non-date type', () => {
    expect(violations('x/A.tsx', `<input {...props} value={v} />`)).toContain('spread without explicit type')
  })

  it('accepts a spread input with an explicit text type, text inputs and DateInput itself', () => {
    expect(violations('x/A.tsx', `<input {...rest} type="text" value={v} />`)).toEqual([])
    expect(violations('x/A.tsx', `<input type="checkbox" checked />`)).toEqual([])
    expect(violations('x/A.tsx', `<DateInput value={v} onChange={set} />`)).toEqual([])
    expect(violations(ALLOWED, `<input type="date" />`)).toEqual([])
  })

  it('does not accept the reviewed dynamic-type files without DateInput when they mention date', () => {
    expect(violations(DYNAMIC_TYPE_FILES[3] as string, `type: 'text' | 'date'\n<input type={type} />`)).toContain('dynamic type without DateInput')
    expect(violations(DYNAMIC_TYPE_FILES[3] as string, `type: 'text' | 'date'\n<DateInput />\n<input type={type} />`)).toEqual([])
  })
})

describe('native date input guard', () => {
  it('scans the real source files', () => {
    const files = sources(SRC).map((f) => relative(SRC, f))
    expect(files.length).toBeGreaterThan(100)
    expect(files).toContain(join('features', 'deals', 'form', 'FormField.tsx'))
    expect(files).toContain(ALLOWED)
  })

  it('finds no native date input, dynamic type, object literal or bare spread in the sources', () => {
    const offenders = sources(SRC)
      .map((file) => ({ file: relative(SRC, file), found: violations(relative(SRC, file), readFileSync(file, 'utf8')) }))
      .filter((r) => r.found.length > 0)
    expect(offenders).toEqual([])
  })

  it('keeps the native date input inside DateInput.tsx', () => {
    expect(DATE_LITERAL.test(readFileSync(join(SRC, ALLOWED), 'utf8').match(INPUT_TAG)?.join(' ') ?? '')).toBe(true)
  })
})
