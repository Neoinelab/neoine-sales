import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * 날짜 입력은 shared/ui/DateInput.tsx만 native date 칸을 쓴다.
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
  // 테스트 코드: UI-022
  it('type="date"를 어떤 철자로 써도 걸린다', () => {
    for (const attr of ['type="date"', "type='date'", "type={'date'}", 'type={"date"}', 'type={`date`}']) {
      // given: 철자만 다른 리터럴 date 입력 소스
      const source = `const a = <input ${attr} value={v} onChange={(e) => set(e.target.value)} />`
      // when: 판정한다
      const found = violations('x/A.tsx', source)
      // then: literal type date로 걸린다
      expect(found).toContain('literal type date')
    }
  })

  // 테스트 코드: UI-022
  it('화살표 함수 속성 뒤에 오는 date 리터럴도 걸린다', () => {
    // given: 화살표 함수 속성 뒤에 type="date"가 있는 소스
    const source = `<input onChange={(e) => set(e.target.value)} type="date" />`
    // when: 판정한다
    const found = violations('x/A.tsx', source)
    // then: literal type date로 걸린다
    expect(found).toContain('literal type date')
  })

  // 테스트 코드: UI-022
  it('검토 목록 밖 파일의 동적 type은 걸린다', () => {
    // given: 검토 목록 밖 파일의 동적 type 소스 둘
    const variable = `<input type={kind} value={v} />`
    const ternary = `<input\n  type={cond ? 'date' : 'text'}\n/>`
    // when: 판정한다
    const first = violations('x/A.tsx', variable)
    const second = violations('x/A.tsx', ternary)
    // then: dynamic type으로 걸린다
    expect(first).toContain('dynamic type')
    expect(second).toContain('dynamic type')
  })

  // 테스트 코드: UI-022
  it('객체 리터럴의 type date는 걸린다', () => {
    // given: type이 date인 객체 리터럴 소스 둘
    const single = `const props = { type: 'date', value }`
    const double = `const props = { type: "date" }`
    // when: 판정한다
    const first = violations('x/A.tsx', single)
    const second = violations('x/a.ts', double)
    // then: object literal type date로 걸린다
    expect(first).toContain('object literal type date')
    expect(second).toContain('object literal type date')
  })

  // 테스트 코드: UI-022
  it('type을 밝히지 않고 spread한 input은 걸린다', () => {
    // given: type 없이 spread한 input 소스
    const source = `<input {...props} value={v} />`
    // when: 판정한다
    const found = violations('x/A.tsx', source)
    // then: spread without explicit type으로 걸린다
    expect(found).toContain('spread without explicit type')
  })

  // 테스트 코드: UI-022
  it('명시한 text type의 spread, 체크박스, DateInput, DateInput.tsx 자신은 통과한다', () => {
    // when: 허용 예를 판정한다
    const spreadText = violations('x/A.tsx', `<input {...rest} type="text" value={v} />`)
    const checkbox = violations('x/A.tsx', `<input type="checkbox" checked />`)
    const dateInput = violations('x/A.tsx', `<DateInput value={v} onChange={set} />`)
    const self = violations(ALLOWED, `<input type="date" />`)
    // then: 위반이 없다
    expect(spreadText).toEqual([])
    expect(checkbox).toEqual([])
    expect(dateInput).toEqual([])
    expect(self).toEqual([])
  })

  // 테스트 코드: UI-022
  it('검토 목록 파일이 date를 언급하면 DateInput이 있어야 통과한다', () => {
    // given: date를 언급하는 검토 목록 파일 소스(DateInput 없음 / 있음)
    const without = `type: 'text' | 'date'\n<input type={type} />`
    const withDateInput = `type: 'text' | 'date'\n<DateInput />\n<input type={type} />`
    // when: 판정한다
    const missing = violations(DYNAMIC_TYPE_FILES[3] as string, without)
    const present = violations(DYNAMIC_TYPE_FILES[3] as string, withDateInput)
    // then: 없으면 걸리고 있으면 통과한다
    expect(missing).toContain('dynamic type without DateInput')
    expect(present).toEqual([])
  })
})

describe('native date input guard', () => {
  // 테스트 코드: UI-022
  it('실제 소스 100개 넘는 파일을 검사 대상으로 삼는다', () => {
    // when: 검사 대상 소스를 모은다
    const files = sources(SRC).map((f) => relative(SRC, f))
    // then: 100개가 넘고 FormField.tsx와 DateInput.tsx가 들어 있다
    expect(files.length).toBeGreaterThan(100)
    expect(files).toContain(join('features', 'deals', 'form', 'FormField.tsx'))
    expect(files).toContain(ALLOWED)
  })

  // 테스트 코드: UI-022
  it('실제 소스에는 native 날짜 칸·동적 type·객체 리터럴·type 없는 spread가 없다', () => {
    // when: 실제 소스를 모두 판정한다
    const offenders = sources(SRC)
      .map((file) => ({ file: relative(SRC, file), found: violations(relative(SRC, file), readFileSync(file, 'utf8')) }))
      .filter((r) => r.found.length > 0)
    // then: 위반 파일이 없다
    expect(offenders).toEqual([])
  })

  // 테스트 코드: UI-022
  it('native 날짜 칸은 DateInput.tsx 안에 있다', () => {
    // when: DateInput.tsx의 input 태그를 본다
    const tags = readFileSync(join(SRC, ALLOWED), 'utf8').match(INPUT_TAG)?.join(' ') ?? ''
    // then: 리터럴 date 입력이 있다
    expect(DATE_LITERAL.test(tags)).toBe(true)
  })
})
