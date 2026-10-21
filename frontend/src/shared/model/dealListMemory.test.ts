import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  listMemoryKey,
  rememberListSearch,
  rememberedListPath,
  sanitizeListSearch,
} from './dealListMemory'
import { USER_ID } from '../../test/fake/seed/ids'

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

describe('sanitizeListSearch id parameters (AC-22)', () => {
  const ID_KEYS = ['owner', 'vendor', 'solution', 'budget', 'authority', 'need', 'timeline']

  it('keeps integer ids of every id parameter', () => {
    const search = ID_KEYS.map((key, index) => `${key}=${index + 1}`).join('&')

    expect(sanitizeListSearch(search)).toBe(search)
  })

  it.each(ID_KEYS)('drops a uuid or old key value of %s but keeps the other conditions', (key) => {
    const kept = sanitizeListSearch(`status=a&${key}=0f0e0d0c-0b0a-4908-8706-050403020100&sort=name`)
    const old = sanitizeListSearch(`${key}=u-kim&status=a`)

    expect(kept).toBe('status=a&sort=name')
    expect(old).toBe('status=a')
  })

  it.each(['0', '-1', '1.5', '01', '1e3', '9007199254740992'])('drops the out-of-range id %j', (raw) => {
    expect(sanitizeListSearch(`vendor=${encodeURIComponent(raw)}&status=a`)).toBe('status=a')
  })

  it('does not restore an old uuid condition that an earlier version stored', () => {
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'vendor=10000000-0000-4000-8000-000000000003&status=a')

    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?status=a')
  })
})

describe('sanitizeListSearch updated period (AC-20, AC-21)', () => {
  it('keeps the updated dates and drops the old Expected Close from/to', () => {
    expect(sanitizeListSearch('from=2026-01-01&to=2026-12-31&updated_from=2026-06-01&updated_to=2026-06-30&status=a')).toBe(
      'updated_from=2026-06-01&updated_to=2026-06-30&status=a',
    )
  })

  it('stores dates only, never a preset name', () => {
    expect(sanitizeListSearch('updated_period=2w&updated_from=2026-06-01&updated_to=2026-06-15')).toBe(
      'updated_from=2026-06-01&updated_to=2026-06-15',
    )
  })

  it('does not restore an old from/to condition that an earlier version stored', () => {
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'from=2026-01-01&to=2026-12-31&status=a')

    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?status=a')
  })

  it('restores the same date range after a detail visit', () => {
    rememberListSearch(USER_ID.kim, params('updated_from=2026-06-01&updated_to=2026-06-15&page=2'))

    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?updated_from=2026-06-01&updated_to=2026-06-15&page=2')
  })
})

describe('listMemoryKey (AC-10)', () => {
  it('builds the storage key per user', () => {
    expect(listMemoryKey(USER_ID.kim)).toBe(`deals.listSearch:${USER_ID.kim}`)
    expect(listMemoryKey(USER_ID.park)).not.toBe(listMemoryKey(USER_ID.kim))
  })
})

describe('rememberedListPath (AC-01, AC-07~AC-10)', () => {
  it('remembered path is /deals when nothing is stored', () => {
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals')
  })

  it('remembered path restores stored search', () => {
    rememberListSearch(USER_ID.kim, params('status=a&year=2026&quarter=3'))
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?status=a&year=2026&quarter=3')
  })

  it('remembering stores only list keys', () => {
    rememberListSearch(USER_ID.kim, params('status=a&foo=1&tab=history'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('status=a')
  })

  it('remembering an empty search clears the entry', () => {
    rememberListSearch(USER_ID.kim, params('status=a'))
    rememberListSearch(USER_ID.kim, params(''))
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals')
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBeNull()
  })

  it('remembering a search without list keys clears the entry', () => {
    rememberListSearch(USER_ID.kim, params('status=a'))
    rememberListSearch(USER_ID.kim, params('tab=history'))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBeNull()
  })

  it('memory is kept per user', () => {
    rememberListSearch(USER_ID.kim, params('status=a'))
    expect(rememberedListPath(USER_ID.park)).toBe('/deals')
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?status=a')
  })

  it('stored garbage is filtered on read', () => {
    // x는 목록 키가 아니라 버리고, owner=9는 유효한 id라 남고, vendor=u9·budget=abc는 id가 아니라 버린다.
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'x=1&owner=9&vendor=u9&budget=abc')
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?owner=9')
  })

  it('stored garbage without list keys reads /deals', () => {
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'x=1')
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals')
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
    expect(() => rememberListSearch(USER_ID.kim, params('status=a'))).not.toThrow()
    expect(() => rememberListSearch(USER_ID.kim, params(''))).not.toThrow()
    expect(rememberedListPath(USER_ID.kim)).toBe('/deals')
  })

  it('missing user reads /deals', () => {
    rememberListSearch(USER_ID.kim, params('status=a'))
    expect(rememberedListPath(null)).toBe('/deals')
    expect(rememberedListPath(undefined)).toBe('/deals')
  })
})

describe('next_status (AC-24)', () => {
  it('sanitize keeps next_status in the list keys', () => {
    expect(sanitizeListSearch('next_status=closed&foo=1&page=2')).toBe('next_status=closed&page=2')
  })

  it('remembered path restores next_status', () => {
    rememberListSearch(USER_ID.kim, params('status=a&next_status=not_done'))

    expect(rememberedListPath(USER_ID.kim)).toBe('/deals?status=a&next_status=not_done')
  })
})
