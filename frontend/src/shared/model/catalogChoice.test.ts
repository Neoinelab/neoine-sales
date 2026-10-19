import { describe, expect, it } from 'vitest'
import { toChoice } from './catalogChoice'

const OPTIONS = [
  { id: 'at-1', name: '미팅' },
  { id: 'at-2', name: 'Demo' },
] as const

describe('toChoice (AC-26, AC-31)', () => {
  it('returns null for a blank text', () => {
    expect(toChoice('', OPTIONS)).toBeNull()
    expect(toChoice('   ', OPTIONS)).toBeNull()
  })

  it('returns the id of the option with the same name', () => {
    expect(toChoice('미팅', OPTIONS)).toEqual({ id: 'at-1' })
  })

  it('returns the id for a case-insensitive match and ignores surrounding spaces', () => {
    expect(toChoice('  demo ', OPTIONS)).toEqual({ id: 'at-2' })
    expect(toChoice('DEMO', OPTIONS)).toEqual({ id: 'at-2' })
  })

  it('returns the trimmed name when no option has the same name', () => {
    expect(toChoice('  웨비나  ', OPTIONS)).toEqual({ name: '웨비나' })
  })

  it('does not treat a partial match as the same option', () => {
    expect(toChoice('미', OPTIONS)).toEqual({ name: '미' })
  })

  it('returns a name when there are no options at all', () => {
    expect(toChoice('미팅', [])).toEqual({ name: '미팅' })
  })
})
