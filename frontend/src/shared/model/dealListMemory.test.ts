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

describe('sanitizeListSearch', () => {
  it('목록 키만 원래 순서대로 남긴다', () => {
    // when: 검색 문자열을 정리한다
    const result = sanitizeListSearch('status=a&foo=1&sort=name&tab=history&page=2')

    // then: status·sort·page만 원래 순서로 남는다
    expect(result).toBe('status=a&sort=name&page=2')
  })

  it('문자열뿐 아니라 URLSearchParams도 받는다', () => {
    // when: URLSearchParams를 정리한다
    const result = sanitizeListSearch(params('foo=1&q=abc&order=asc'))

    // then: q·order만 남는다
    expect(result).toBe('q=abc&order=asc')
  })

  it('목록 키가 하나도 없으면 빈 문자열이다', () => {
    // when: 목록 키가 없는 검색과 빈 문자열을 정리한다
    const result1 = sanitizeListSearch('foo=1')
    const result2 = sanitizeListSearch('')

    // then: 둘 다 빈 문자열이다
    expect(result1).toBe('')
    expect(result2).toBe('')
  })

  it('결과 앞에 물음표를 붙이지 않는다', () => {
    // when: 목록 키 하나를 정리한다
    const result = sanitizeListSearch('status=a')

    // then: 물음표 없이 키=값만 돌아온다
    expect(result).toBe('status=a')
  })
})

describe('sanitizeListSearch product text', () => {
  it('Product를 텍스트로 기억한다', () => {
    // when: Product 조건을 정리한다
    const result1 = sanitizeListSearch('product=ITDR&status=a')
    const result2 = sanitizeListSearch(`product=${encodeURIComponent('통합 itdr')}`)

    // then: 영문·한글 Product가 텍스트로 남는다
    expect(result1).toBe('product=ITDR&status=a')
    expect(result2).toBe(`product=${encodeURIComponent('통합 itdr').replace(/%20/g, '+')}`)
  })

  it('예전 정수 Product id도 텍스트로 남긴다', () => {
    // when: 정수 Product 값을 정리한다
    const result = sanitizeListSearch('product=12&status=a')

    // then: 그대로 남는다
    expect(result).toBe('product=12&status=a')
  })

  it('기억한 Product 텍스트를 목록 경로로 되살린다', () => {
    // when: 사용자가 기억해 둔 Product 조건으로 기억된 경로를 구한다 (전제: 세션에 Product 조건이 저장된 사용자)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'product=ITDR&status=a')

    const result = rememberedListPath(USER_ID.kim)

    // then: /deals 경로에 Product 텍스트가 붙는다
    expect(result).toBe('/deals?product=ITDR&status=a')
  })
})

describe('sanitizeListSearch id parameters', () => {
  const ID_KEYS = ['owner', 'vendor']

  it('모든 id 파라미터의 정수 id를 남긴다', () => {
    // given: owner·vendor에 정수 id가 있는 검색
    const search = ID_KEYS.map((key, index) => `${key}=${index + 1}`).join('&')

    // when: 정수 id가 든 검색을 정리한다
    const result = sanitizeListSearch(search)

    // then: 검색이 그대로다
    expect(result).toBe(search)
  })

  it.each(ID_KEYS)('%s의 uuid·예전 키 값은 버리고 다른 조건은 남긴다', (key) => {
    // when: uuid 값이 든 검색과 예전 키 값이 든 검색을 정리한다
    const kept = sanitizeListSearch(`status=a&${key}=0f0e0d0c-0b0a-4908-8706-050403020100&sort=name`)
    const old = sanitizeListSearch(`${key}=u-kim&status=a`)

    // then: 해당 id 파라미터만 빠지고 나머지는 남는다
    expect(kept).toBe('status=a&sort=name')
    expect(old).toBe('status=a')
  })

  it.each(['0', '-1', '1.5', '01', '1e3', '9007199254740992'])('범위 밖 id %j은(는) 버린다', (raw) => {
    // when: 범위 밖 id가 든 검색을 정리한다
    const result = sanitizeListSearch(`vendor=${encodeURIComponent(raw)}&status=a`)

    // then: id 파라미터가 빠지고 status만 남는다
    expect(result).toBe('status=a')
  })

  it('예전 버전이 저장한 uuid 조건은 되살리지 않는다', () => {
    // when: uuid 조건이 저장된 사용자의 기억된 경로를 구한다 (전제: 예전 버전이 uuid vendor 조건을 저장해 둔 세션)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'vendor=10000000-0000-4000-8000-000000000003&status=a')

    const result = rememberedListPath(USER_ID.kim)

    // then: uuid 조건 없이 status만 복원된다
    expect(result).toBe('/deals?status=a')
  })
})

describe('sanitizeListSearch updated period', () => {
  it('최종 업데이트 날짜는 남기고 예전 Expected Close from/to는 버린다', () => {
    // when: from/to와 updated_from/updated_to가 섞인 검색을 정리한다
    const result = sanitizeListSearch('from=2026-01-01&to=2026-12-31&updated_from=2026-06-01&updated_to=2026-06-30&status=a')

    // then: updated_* 와 status만 남는다
    expect(result).toBe(
      'updated_from=2026-06-01&updated_to=2026-06-30&status=a',
    )
  })

  it('날짜만 기억하고 프리셋 이름은 기억하지 않는다', () => {
    // when: 프리셋 이름과 날짜가 함께 있는 검색을 정리한다
    const result = sanitizeListSearch('updated_period=2w&updated_from=2026-06-01&updated_to=2026-06-15')

    // then: 프리셋 이름은 빠지고 날짜만 남는다
    expect(result).toBe(
      'updated_from=2026-06-01&updated_to=2026-06-15',
    )
  })

  it('예전 버전이 저장한 from/to 조건은 되살리지 않는다', () => {
    // when: from/to가 저장된 사용자의 기억된 경로를 구한다 (전제: 예전 버전이 from/to 조건을 저장해 둔 세션)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'from=2026-01-01&to=2026-12-31&status=a')

    const result = rememberedListPath(USER_ID.kim)

    // then: from/to 없이 status만 복원된다
    expect(result).toBe('/deals?status=a')
  })

  it('상세를 다녀온 뒤 같은 날짜 범위를 되살린다', () => {
    // when: 날짜 범위가 있는 목록 검색을 기억하고 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('updated_from=2026-06-01&updated_to=2026-06-15&page=2'))

    const result = rememberedListPath(USER_ID.kim)

    // then: 같은 날짜 범위와 page가 복원된다
    expect(result).toBe('/deals?updated_from=2026-06-01&updated_to=2026-06-15&page=2')
  })
})

describe('listMemoryKey', () => {
  it('저장 키를 사용자마다 만든다', () => {
    // when: 두 사용자의 저장 키를 만든다
    const result1 = listMemoryKey(USER_ID.kim)
    const result2 = listMemoryKey(USER_ID.park)

    // then: 사용자 id가 키에 들어 있고 서로 다르다
    expect(result1).toBe(`deals.listSearch:${USER_ID.kim}`)
    expect(result2).not.toBe(listMemoryKey(USER_ID.kim))
  })
})

describe('rememberedListPath', () => {
  it('저장된 것이 없으면 기억된 경로는 /deals다', () => {
    // when: 기억된 경로를 구한다
    const result = rememberedListPath(USER_ID.kim)

    // then: /deals다
    expect(result).toBe('/deals')
  })

  it('저장된 검색을 기억된 경로로 되살린다', () => {
    // when: 검색을 기억한 뒤 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('status=a&year=2026&quarter=3'))
    const result = rememberedListPath(USER_ID.kim)

    // then: /deals에 그 검색이 붙는다
    expect(result).toBe('/deals?status=a&year=2026&quarter=3')
  })

  it('기억할 때 목록 키만 저장한다', () => {
    // when: 목록 키가 아닌 값이 섞인 검색을 기억한다
    rememberListSearch(USER_ID.kim, params('status=a&foo=1&tab=history'))
    const result = window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))

    // then: 저장소에는 목록 키만 있다
    expect(result).toBe('status=a')
  })

  it('빈 검색을 기억하면 저장된 항목을 지운다', () => {
    // when: 검색을 기억했다가 빈 검색을 기억한다
    rememberListSearch(USER_ID.kim, params('status=a'))
    rememberListSearch(USER_ID.kim, params(''))
    const result1 = rememberedListPath(USER_ID.kim)
    const result2 = window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))

    // then: 기억된 경로가 /deals이고 저장 항목이 없다
    expect(result1).toBe('/deals')
    expect(result2).toBeNull()
  })

  it('목록 키 없는 검색을 기억하면 저장된 항목을 지운다', () => {
    // when: 검색을 기억했다가 목록 키가 없는 검색을 기억한다
    rememberListSearch(USER_ID.kim, params('status=a'))
    rememberListSearch(USER_ID.kim, params('tab=history'))
    const result = window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))

    // then: 저장 항목이 없다
    expect(result).toBeNull()
  })

  it('기억은 사용자마다 따로 둔다', () => {
    // when: 한 사용자의 검색을 기억하고 두 사용자의 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('status=a'))
    const result1 = rememberedListPath(USER_ID.park)
    const result2 = rememberedListPath(USER_ID.kim)

    // then: 다른 사용자는 /deals, 기억한 사용자는 그 검색이다
    expect(result1).toBe('/deals')
    expect(result2).toBe('/deals?status=a')
  })

  it('저장된 이상한 값은 읽을 때 걸러낸다', () => {
    // when: 잘못된 키와 id가 저장된 세션의 기억된 경로를 구한다
    // x는 목록 키가 아니라 버리고, owner=9는 유효한 id라 남고, vendor=u9는 id가 아니라 버린다.
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'x=1&owner=9&vendor=u9')
    const result = rememberedListPath(USER_ID.kim)

    // then: 유효한 id만 남는다
    expect(result).toBe('/deals?owner=9')
  })

  it('목록 키 없는 저장 값은 /deals로 읽는다', () => {
    // when: 목록 키 없는 값이 저장된 세션의 기억된 경로를 구한다
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'x=1')
    const result = rememberedListPath(USER_ID.kim)

    // then: /deals다
    expect(result).toBe('/deals')
  })

  it('저장소가 실패하면 /deals로 되돌아간다', () => {
    // given: 저장소의 읽기·쓰기·삭제가 모두 예외를 던진다
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('denied')
    })

    // when·then: 검색 기억과 빈 검색으로 삭제하기는 예외를 던지지 않는다
    expect(() => rememberListSearch(USER_ID.kim, params('status=a'))).not.toThrow()
    expect(() => rememberListSearch(USER_ID.kim, params(''))).not.toThrow()

    // when: 기억된 경로를 구한다
    const result = rememberedListPath(USER_ID.kim)

    // then: /deals다
    expect(result).toBe('/deals')
  })

  it('사용자가 없으면 /deals로 읽는다', () => {
    // when: 사용자 없이 기억된 경로를 구한다 (전제: 한 사용자의 검색이 기억되어 있다)
    rememberListSearch(USER_ID.kim, params('status=a'))
    const result1 = rememberedListPath(null)
    const result2 = rememberedListPath(undefined)

    // then: null·undefined 모두 /deals다
    expect(result1).toBe('/deals')
    expect(result2).toBe('/deals')
  })
})

describe('next_status', () => {
  it('next_status를 목록 키로 남긴다', () => {
    // when: next_status가 든 검색을 정리한다
    const result = sanitizeListSearch('next_status=closed&foo=1&page=2')

    // then: next_status와 page만 남는다
    expect(result).toBe('next_status=closed&page=2')
  })

  it('기억된 경로가 next_status를 되살린다', () => {
    // when: next_status가 든 검색을 기억하고 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('status=a&next_status=not_done'))

    const result = rememberedListPath(USER_ID.kim)

    // then: next_status가 복원된다
    expect(result).toBe('/deals?status=a&next_status=not_done')
  })
})

describe('BANT 키 폐지와 overdue·stale', () => {
  it('예전 BANT 키는 기억하지 않는다', () => {
    // when: BANT 키가 든 검색을 정리하고 기억한다
    const result1 = sanitizeListSearch('budget=1&authority=2&need=3&timeline=4&status=a')
    rememberListSearch(USER_ID.kim, params('budget=1&need=3'))
    const result2 = window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))

    // then: 정리 결과에 BANT 키가 없고 저장 항목도 없다
    expect(result1).toBe('status=a')
    expect(result2).toBeNull()
  })

  it('예전 저장 항목의 BANT 키는 복원할 때 버리고 다른 조건은 남긴다', () => {
    // when: BANT 키가 저장된 세션의 기억된 경로를 구한다 (전제: 예전 버전이 BANT 키를 저장해 둔 세션)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'budget=1&status=a&timeline=4&overdue=1')

    const result = rememberedListPath(USER_ID.kim)

    // then: BANT 키 없이 status·overdue만 복원된다
    expect(result).toBe('/deals?status=a&overdue=1')
  })

  it('overdue와 stale은 기억한다', () => {
    // when: overdue·stale이 든 검색을 정리하고, 다른 검색을 기억한 뒤 기억된 경로를 구한다
    const result1 = sanitizeListSearch('overdue=1&stale=1&foo=1')
    rememberListSearch(USER_ID.kim, params('stale=1&sort=owner&order=desc'))
    const result2 = rememberedListPath(USER_ID.kim)

    // then: overdue·stale 키가 남고 기억된 경로로 복원된다
    expect(result1).toBe('overdue=1&stale=1')
    expect(result2).toBe('/deals?stale=1&sort=owner&order=desc')
  })
})

describe('outcome is no longer remembered', () => {
  it('예전 검색의 outcome은 버린다', () => {
    // when: outcome이 든 검색을 정리한다
    const result = sanitizeListSearch('year=2026&outcome=open&foo=1')

    // then: outcome 없이 year만 남는다
    expect(result).toBe('year=2026')
  })

  it('기억할 때 outcome을 저장하지 않는다', () => {
    // when: outcome이 든 검색을 기억한다
    rememberListSearch(USER_ID.kim, params('year=2026&quarter=4&outcome=not_lost&status=poc_completed'))

    const result = window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))

    // then: 저장소에 outcome이 없다
    expect(result).toBe('year=2026&quarter=4&status=poc_completed')
  })

  it('예전 항목에 outcome만 있으면 조건 없는 목록 경로로 되살린다', () => {
    // when: outcome만 저장된 세션의 기억된 경로를 구한다 (전제: 예전 버전이 outcome만 저장해 둔 세션)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'outcome=open')

    const result = rememberedListPath(USER_ID.kim)

    // then: /deals다
    expect(result).toBe('/deals')
  })

  it('다른 조건이 있는 예전 항목에서는 outcome만 버린다', () => {
    // when: outcome과 year가 저장된 세션의 기억된 경로를 구한다 (전제: 예전 버전이 outcome과 year를 저장해 둔 세션)
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'outcome=open&year=2026')

    const result = rememberedListPath(USER_ID.kim)

    // then: year만 복원된다
    expect(result).toBe('/deals?year=2026')
  })
})

describe('year=all memory', () => {
  it('year=all을 기억하고 목록 경로로 되살린다', () => {
    // when: year=all을 기억하고 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('year=all'))

    const result = rememberedListPath(USER_ID.kim)

    // then: /deals?year=all이다
    expect(result).toBe('/deals?year=all')
  })

  it('이전에 기억한 검색을 병합 없이 통째로 바꾼다', () => {
    // when: 검색을 기억한 뒤 다른 검색을 다시 기억하고 기억된 경로를 구한다
    rememberListSearch(USER_ID.kim, params('status=prospecting&sort=owner&page=3'))
    rememberListSearch(USER_ID.kim, params('year=2026&quarter=4'))

    const result = rememberedListPath(USER_ID.kim)

    // then: 나중 검색만 복원되고 이전 키는 섞이지 않는다
    expect(result).toBe('/deals?year=2026&quarter=4')
  })
})
