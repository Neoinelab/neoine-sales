import { describe, expect, it } from 'vitest'
import {
  FORECAST_KEYS_MAX,
  forecastParam,
  forecastSetsOf,
  forecastSummary,
  parseForecastParam,
  toggleForecastParam,
} from './forecastKeys'
import { testCodes } from './testing'
import type { Code, ForecastColumn } from './types'

/** Forecast 다중 조건: URL `forecast` 값(콤마 구분)과 필터 버튼 요약. */

const keys = (n: number): string[] => Array.from({ length: n }, (_, i) => `k${i}`)

describe('parseForecastParam', () => {
  it.each([[null], ['']])('값이 %j이면 선택 없음으로 읽는다', (raw) => {
    // when: 빈 값을 읽는다
    const result = parseForecastParam(raw)

    // then: 선택 없음이다
    expect(result).toEqual([])
  })

  it('예전 단일 값을 그대로 읽는다', () => {
    // when: 단일 값을 읽는다
    const result = parseForecastParam('commit')

    // then: 한 개짜리 목록이다
    expect(result).toEqual(['commit'])
  })

  it('읽은 key를 알파벳 순으로 정렬한다', () => {
    // when: 순서가 뒤섞인 값을 읽는다
    const result = parseForecastParam('pipeline,best')

    // then: 정렬되어 나온다
    expect(result).toEqual(['best', 'pipeline'])
  })

  it('중복·빈 항목·앞뒤 공백을 버린다', () => {
    // when: 중복·공백이 섞인 값을 읽는다
    const result = parseForecastParam(' best , best ,pipeline,')

    // then: 정리된 두 key만 남는다
    expect(result).toEqual(['best', 'pipeline'])
  })

  it('형식이 틀린 항목(대문자, 허용 밖 문자, 숫자 시작)을 버린다', () => {
    // when: 형식이 틀린 항목이 섞인 값을 각각 읽는다
    const upper = parseForecastParam('Commit,ok')
    const onlyUpper = parseForecastParam('XYZ')
    const dash = parseForecastParam('a-b,ok')
    const digit = parseForecastParam('1abc,ok')

    // then: 올바른 항목만 남는다
    expect(upper).toEqual(['ok'])
    expect(onlyUpper).toEqual([])
    expect(dash).toEqual(['ok'])
    expect(digit).toEqual(['ok'])
  })

  it('50자 key는 유지하고 51자 key는 버린다', () => {
    // given: 50자 key
    const fifty = 'a'.repeat(50)

    // when: 50자 key와 51자 key를 읽는다
    const keepResult = parseForecastParam(fifty)
    const dropResult = parseForecastParam(`${'a'.repeat(51)},ok`)

    // then: 50자는 남고 51자는 버려진다
    expect(keepResult).toEqual([fifty])
    expect(dropResult).toEqual(['ok'])
  })

  it('서로 다른 key 100개는 읽고 그보다 많으면 조건 전체를 무시한다', () => {
    // when: 100개와 101개를 읽는다
    const atLimit = parseForecastParam(keys(100).join(','))
    const overLimit = parseForecastParam(keys(101).join(','))

    // then: 상한은 100이고 100개는 모두 남으며 101개는 빈 선택이다
    expect(FORECAST_KEYS_MAX).toBe(100)
    expect(atLimit).toHaveLength(100)
    expect(overLimit).toEqual([])
  })

  it('중복은 상한 개수에 세지 않는다', () => {
    // given: 같은 key 100개를 두 번 이은 값
    const raw = [...keys(100), ...keys(100)].join(',')

    // when: 읽는다
    const result = parseForecastParam(raw)

    // then: 중복이 합쳐져 100개가 남는다
    expect(result).toHaveLength(100)
  })
})

describe('forecastParam', () => {
  it('정렬하고 중복을 없앤 key를 콤마로 잇는다', () => {
    // when: 순서가 뒤섞이고 중복된 key로 값을 만든다
    const result = forecastParam(['pipeline', 'best', 'best'])

    // then: 정렬·중복 제거된 문자열이다
    expect(result).toBe('best,pipeline')
  })

  it('key가 없으면 빈 문자열이다', () => {
    // when: 빈 목록으로 값을 만든다
    const result = forecastParam([])

    // then: 빈 문자열이다
    expect(result).toBe('')
  })
})

describe('toggleForecastParam', () => {
  it('key를 켜면 정렬된 위치에 더한다', () => {
    // when: 값이 있는 경우와 없는 경우에 key를 켠다
    const withExisting = toggleForecastParam('best', 'pipeline', true)
    const fromNull = toggleForecastParam(null, 'pipeline', true)

    // then: 정렬 위치에 들어간다
    expect(withExisting).toBe('best,pipeline')
    expect(fromNull).toBe('pipeline')
  })

  it('key를 끄면 뺀다', () => {
    // when: 켜진 key를 끈다
    const result = toggleForecastParam('best,pipeline', 'best', false)

    // then: 나머지만 남는다
    expect(result).toBe('pipeline')
  })

  it('마지막 key를 끄면 빈 값이 된다', () => {
    // when: 하나뿐인 key를 끈다
    const result = toggleForecastParam('best', 'best', false)

    // then: 빈 문자열이다
    expect(result).toBe('')
  })

  it('이미 켜진 key를 다시 켜도 값이 그대로다', () => {
    // when: 이미 켜진 key를 켠다
    const result = toggleForecastParam('best,pipeline', 'best', true)

    // then: 값이 바뀌지 않는다
    expect(result).toBe('best,pipeline')
  })

  it('켜져 있지 않은 key를 꺼도 값이 그대로다', () => {
    // when: 켜져 있지 않은 key를 끈다
    const result = toggleForecastParam('best', 'pipeline', false)

    // then: 값이 바뀌지 않는다
    expect(result).toBe('best')
  })

  it('켜는 순서와 관계없이 같은 값이 된다', () => {
    // when: 두 key를 서로 다른 순서로 켠다
    const a = toggleForecastParam(toggleForecastParam(null, 'best', true), 'pipeline', true)
    const b = toggleForecastParam(toggleForecastParam(null, 'pipeline', true), 'best', true)

    // then: 결과가 같다
    expect(a).toBe(b)
  })
})

describe('forecastSummary', () => {
  const base = testCodes().forecasts
  // admin이 추가한 Open 코드 하나
  const verbal: Code = { ...base[3]!, id: 999, key: 'verbal', name: 'Verbal', order: 7, outcome: 'open' }
  const codes: Code[] = [...base, verbal]
  const keysOf = (pick: (c: Code) => boolean) => codes.filter(pick).map((c) => c.key)

  it('선택이 없으면 "전체"라고 요약한다', () => {
    // when: 선택 없이 요약한다
    const result = forecastSummary([], codes)

    // then: "전체"다
    expect(result).toBe('전체')
  })

  it('코드 하나면 그 이름을, 모르는 코드면 key를 보인다', () => {
    // when: 알려진 key와 모르는 key를 각각 요약한다
    const known = forecastSummary(['best'], codes)
    const unknown = forecastSummary(['zzz'], codes)

    // then: 이름 또는 key다
    expect(known).toBe('Best')
    expect(unknown).toBe('zzz')
  })

  it('Lost를 포함한 모든 코드를 고르면 "모두 선택"이다', () => {
    // when: 모든 코드를 요약한다
    const result = forecastSummary(keysOf(() => true), codes)

    // then: "모두 선택"이다
    expect(result).toBe('모두 선택')
  })

  it('Lost가 아닌 코드만 정확히 고르면 "Lost 제외"다', () => {
    // when: Lost 아닌 코드 전부를 요약한다
    const result = forecastSummary(keysOf((c) => c.outcome !== 'lost'), codes)

    // then: "Lost 제외"다
    expect(result).toBe('Lost 제외')
  })

  it('추가된 코드를 포함해 Open 코드만 정확히 고르면 "Open 전체"다', () => {
    // when: Open 코드 전부를 요약한다
    const result = forecastSummary(keysOf((c) => c.outcome === 'open'), codes)

    // then: "Open 전체"다
    expect(result).toBe('Open 전체')
  })

  it('추가된 Open 코드가 빠지면 "Open 전체"가 아니라 개수로 요약한다', () => {
    // when: 추가된 Open 코드(verbal)를 뺀 Open 코드를 요약한다
    const result = forecastSummary(['pipeline', 'best', 'most_likely', 'commit'], codes)

    // then: "4개 선택"이다
    expect(result).toBe('4개 선택')
  })

  it('그 밖의 선택은 개수로 요약한다', () => {
    // when: 임의의 두 코드를 요약한다
    const result = forecastSummary(['best', 'lost'], codes)

    // then: "2개 선택"이다
    expect(result).toBe('2개 선택')
  })

  it('모르는 key만 골라도 개수로 요약한다', () => {
    // when: 모르는 key 둘을 요약한다
    const result = forecastSummary(['aaa', 'bbb'], codes)

    // then: "2개 선택"이다
    expect(result).toBe('2개 선택')
  })

  it('코드를 아직 읽지 못했으면 이름 없이 개수로 센다', () => {
    // when: 코드 목록 없이 요약한다
    const some = forecastSummary(['a', 'b', 'c'], undefined)
    const none = forecastSummary([], undefined)

    // then: 개수 또는 "전체"다
    expect(some).toBe('3개 선택')
    expect(none).toBe('전체')
  })

  it('Open 코드가 하나뿐일 때 그것만 고르면 이름을 보인다', () => {
    // given: Open 코드가 commit 하나뿐인 코드 목록
    const onlyOne = codes.filter((c) => c.outcome !== 'open' || c.key === 'commit')

    // when: commit만 요약한다
    const result = forecastSummary(['commit'], onlyOne)

    // then: 이름 "Commit"이다
    expect(result).toBe('Commit')
  })
})

const column = (key: string, outcome: 'open' | 'won', order: number): ForecastColumn => ({ key, name: key, outcome, order })
// 응답 columns(Lost 제외): Pipeline·Best·Most Likely·Commit과 admin이 추가한 Open 코드 verbal, Won
const COLUMNS: ForecastColumn[] = [
  column('pipeline', 'open', 1),
  column('best', 'open', 2),
  column('verbal', 'open', 3),
  column('most_likely', 'open', 4),
  column('commit', 'open', 5),
  column('won', 'won', 6),
]
const SETS_EXPECTED = {
  open: ['best', 'commit', 'most_likely', 'pipeline', 'verbal'],
  notLost: ['best', 'commit', 'most_likely', 'pipeline', 'verbal', 'won'],
}

describe('forecastSetsOf (Dashboard·Forecast 링크가 함께 쓴다)', () => {
  it('Open key와 Lost 제외 key를 정렬해 모은다', () => {
    // when: 응답 열에서 집합을 만든다
    const sets = forecastSetsOf(COLUMNS)

    // then: 두 집합이 정렬되어 있다
    expect(sets.open).toEqual(SETS_EXPECTED.open)
    expect(sets.notLost).toEqual(SETS_EXPECTED.notLost)
  })

  it('admin이 추가한 Open 코드는 두 집합에 모두 들어간다', () => {
    // when: 응답 열에서 집합을 만든다
    const sets = forecastSetsOf(COLUMNS)

    // then: verbal이 두 집합에 있다
    expect(sets.open).toContain('verbal')
    expect(sets.notLost).toContain('verbal')
  })

  it('응답에 Lost 열이 섞여 와도 집합에서 뺀다', () => {
    // given: Lost 열이 섞인 응답 열
    const withLost = [...COLUMNS, { key: 'lost', name: 'Lost', outcome: 'lost', order: 7 } as unknown as ForecastColumn]

    // when: 집합을 만든다
    const sets = forecastSetsOf(withLost)

    // then: lost가 빠져 원래 집합과 같다
    expect(sets.open).not.toContain('lost')
    expect(sets.notLost).not.toContain('lost')
    expect(sets).toEqual(SETS_EXPECTED)
  })

  it('열 순서와 관계없이 같은 집합이 된다', () => {
    // when: 열을 거꾸로 넣어 집합을 만든다
    const sets = forecastSetsOf([...COLUMNS].reverse())

    // then: 원래 집합과 같다
    expect(sets).toEqual(SETS_EXPECTED)
  })

  it('열이 없으면 비어 있고, Won만 있으면 Open key가 없다', () => {
    // when: 열 없이, 그리고 Won 열만으로 집합을 만든다
    const nothing = forecastSetsOf([])
    const noOpen = forecastSetsOf([column('won', 'won', 1)])

    // then: 빈 집합, Won만 있는 집합이다
    expect(nothing).toEqual({ open: [], notLost: [] })
    expect(noOpen).toEqual({ open: [], notLost: ['won'] })
  })
})
