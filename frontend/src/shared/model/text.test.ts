import { describe, expect, it } from 'vitest'
import { withGa, withRo, withWa } from './text'

describe('조사', () => {
  it('받침 없는 한글은 로/가/와, 받침 있으면 으로/이/과, ㄹ 받침은 로', () => {
    expect(withRo('계약완료')).toBe('계약완료로')
    expect(withRo('가격협상')).toBe('가격협상으로')
    expect(withRo('기술평가')).toBe('기술평가로')
    expect(withRo('서울')).toBe('서울로')
    expect(withGa('계약완료')).toBe('계약완료가')
    expect(withGa('가격협상')).toBe('가격협상이')
    expect(withWa('Status 계약완료')).toBe('Status 계약완료와')
    expect(withWa('Forecast Won')).toBe('Forecast Won과')
  })

  it('영문은 Won·Commit 계열 받침 추정 규칙을 따른다', () => {
    expect(withRo('Won')).toBe('Won으로')
    expect(withRo('Best')).toBe('Best로')
    expect(withRo('Commit')).toBe('Commit으로')
    expect(withWa('Forecast Commit')).toBe('Forecast Commit과')
    expect(withWa('Forecast Best')).toBe('Forecast Best와')
    expect(withGa('t')).toBe('t가')
  })
})
