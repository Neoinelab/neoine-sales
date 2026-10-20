import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  listMemoryKey,
  rememberListSearch,
  rememberedListPath,
  sanitizeListSearch,
} from './dealListMemory'

const params = (query: string) => new URLSearchParams(query)

afterEach(() => {
  vi.restoreAllMocks()
})

describe('sanitizeListSearch (AC-08, AC-09)', () => {
  it('sanitize keeps only list keys in their original order', () => {
    expect(sanitizeListSearch('status=a&foo=1&sort=name&tab=history&page=2')).toBe('status=a&sort=name&page=2')
  })

  it('sanitize accepts URLSearchParams as well as a string', () => {
    expect(sanitizeListSearch(params('foo=1&q=abc&order=asc'))).toBe('q=abc&order=asc')
  })

  it('sanitize returns empty string when no list key remains', () => {
    expect(sanitizeListSearch('foo=1')).toBe('')
    expect(sanitizeListSearch('')).toBe('')
  })

  it('sanitize does not put a leading question mark in the result', () => {
    expect(sanitizeListSearch('status=a')).toBe('status=a')
  })
})

describe('listMemoryKey (AC-10)', () => {
  it('builds the storage key per user', () => {
    expect(listMemoryKey('u-kim')).toBe('deals.listSearch:u-kim')
    expect(listMemoryKey('u-park')).not.toBe(listMemoryKey('u-kim'))
  })
})

describe('rememberedListPath (AC-01, AC-07~AC-10)', () => {
  it('remembered path is /deals when nothing is stored', () => {
    expect(rememberedListPath('u-kim')).toBe('/deals')
  })

  it('remembered path restores stored search', () => {
    rememberListSearch('u-kim', params('status=a&year=2026&quarter=3'))
    expect(rememberedListPath('u-kim')).toBe('/deals?status=a&year=2026&quarter=3')
  })

  it('remembering stores only list keys', () => {
    rememberListSearch('u-kim', params('status=a&foo=1&tab=history'))
    expect(window.sessionStorage.getItem(listMemoryKey('u-kim'))).toBe('status=a')
  })

  it('remembering an empty search clears the entry', () => {
    rememberListSearch('u-kim', params('status=a'))
    rememberListSearch('u-kim', params(''))
    expect(rememberedListPath('u-kim')).toBe('/deals')
    expect(window.sessionStorage.getItem(listMemoryKey('u-kim'))).toBeNull()
  })

  it('remembering a search without list keys clears the entry', () => {
    rememberListSearch('u-kim', params('status=a'))
    rememberListSearch('u-kim', params('tab=history'))
    expect(window.sessionStorage.getItem(listMemoryKey('u-kim'))).toBeNull()
  })

  it('memory is kept per user', () => {
    rememberListSearch('u-kim', params('status=a'))
    expect(rememberedListPath('u-park')).toBe('/deals')
    expect(rememberedListPath('u-kim')).toBe('/deals?status=a')
  })

  it('stored garbage is filtered on read', () => {
    window.sessionStorage.setItem(listMemoryKey('u-kim'), 'x=1&owner=u9')
    expect(rememberedListPath('u-kim')).toBe('/deals?owner=u9')
  })

  it('stored garbage without list keys reads /deals', () => {
    window.sessionStorage.setItem(listMemoryKey('u-kim'), 'x=1')
    expect(rememberedListPath('u-kim')).toBe('/deals')
  })

  it('storage failure falls back to /deals', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(() => rememberListSearch('u-kim', params('status=a'))).not.toThrow()
    expect(() => rememberListSearch('u-kim', params(''))).not.toThrow()
    expect(rememberedListPath('u-kim')).toBe('/deals')
  })

  it('missing user reads /deals', () => {
    rememberListSearch('u-kim', params('status=a'))
    expect(rememberedListPath(null)).toBe('/deals')
    expect(rememberedListPath(undefined)).toBe('/deals')
  })
})

describe('next_status (AC-24)', () => {
  it('sanitize keeps next_status in the list keys', () => {
    expect(sanitizeListSearch('next_status=closed&foo=1&page=2')).toBe('next_status=closed&page=2')
  })

  it('remembered path restores next_status', () => {
    rememberListSearch('u-kim', params('status=a&next_status=not_done'))

    expect(rememberedListPath('u-kim')).toBe('/deals?status=a&next_status=not_done')
  })
})
