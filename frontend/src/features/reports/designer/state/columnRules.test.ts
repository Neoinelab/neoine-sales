import { describe, expect, it } from 'vitest'
import type { ReportOperator } from '../../../../shared/model/reportTypes'
import { columnAt, conditionUidAt, emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { aggregateChoices, filterableFields, isMoneyField } from './columnRules'

describe('그룹핑 전환', () => {
  // 테스트 코드: RQ-075
  it('첫 그룹을 켜면 숫자는 기본 집계, 텍스트는 건수로 채워진다', () => {
    // given: Vendor, Deal code, 금액, 체류 일수, Action 건수 컬럼
    const state = withColumns('deal.vendor', 'deal.code', 'deal.amount', 'deal.status_days', 'action.count')

    // when: Vendor를 그룹핑한다
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    // then: 그룹 컬럼은 집계 없음, Deal code는 건수, 금액은 합계, 체류 일수는 평균, Action 건수는 건수다
    expect(grouped.columns.map((c) => [c.field, c.group, c.aggregate])).toEqual([
      ['deal.vendor', true, null],
      ['deal.code', false, 'count'],
      ['deal.amount', false, 'sum'],
      ['deal.status_days', false, 'avg'],
      ['action.count', false, 'count'],
    ])
  })

  // 테스트 코드: RQ-075
  it('마지막 그룹을 끄면 모든 집계가 비워진다', () => {
    // given: Vendor를 그룹핑한 Vendor, 금액 설계
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    // when: 그룹핑을 끈다
    const flat = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 0), patch: { group: false } })

    // then: 집계가 모두 없다
    expect(flat.columns.map((c) => c.aggregate)).toEqual([null, null])
  })

  // 테스트 코드: RQ-075
  it('다른 그룹이 남아 있으면 집계를 유지한다', () => {
    // given: Vendor와 Status를 모두 그룹핑한 설계
    const state = withColumns('deal.vendor', 'deal.status', 'deal.amount')
    const both = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true } },
    )

    // when: Vendor 그룹핑만 끈다
    const one = reduce(both, { type: 'updateColumn', uid: uidAt(both, 0), patch: { group: false } })

    // then: 금액 집계가 합계로 남는다
    expect(columnAt(one, 2).aggregate).toBe('sum')
  })

  // 테스트 코드: RQ-075
  it('그룹이 된 컬럼의 집계는 비워진다', () => {
    // given: Vendor를 그룹핑한 Vendor, 금액 설계
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    // when: 금액도 그룹핑한다
    const regrouped = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 1), patch: { group: true } })

    // then: 금액은 그룹이고 집계가 없다
    expect(columnAt(regrouped, 1)).toMatchObject({ group: true, aggregate: null })
  })

  // 테스트 코드: RQ-075
  it('나중에 넣은 컬럼은 그룹이 있을 때만 집계(기본 또는 건수)를 받는다', () => {
    // given: Vendor만 있는 설계와 Vendor를 그룹핑한 설계
    const flat = withColumns('deal.vendor')
    const grouped = reduce(flat, { type: 'updateColumn', uid: uidAt(flat, 0), patch: { group: true } })

    // when: 금액·Deal 이름 컬럼을 그룹핑한 설계와 그룹핑 없는 설계에 각각 넣는다
    const withNumber = reduce(grouped, { type: 'addColumn', field: fieldOf('deal.amount') })
    const withText = reduce(grouped, { type: 'addColumn', field: fieldOf('deal.name') })
    const ungrouped = reduce(flat, { type: 'addColumn', field: fieldOf('deal.amount') })

    // then: 그룹핑하면 금액 합계·텍스트 건수, 그룹핑이 없으면 집계가 없다
    expect(columnAt(withNumber, 1).aggregate).toBe('sum')
    expect(columnAt(withText, 1).aggregate).toBe('count')
    expect(columnAt(ungrouped, 1).aggregate).toBeNull()
  })

  // 테스트 코드: RQ-075
  it('그룹 하나를 꺼도 다른 그룹이 남으면 꺼진 텍스트 컬럼이 건수가 된다', () => {
    // given: Vendor와 Status를 그룹핑하고 Deal 이름을 넣은 설계
    const state = withColumns('deal.vendor', 'deal.status', 'deal.name')
    const both = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true } },
    )

    // when: Vendor 그룹핑만 끈다
    const one = reduce(both, { type: 'updateColumn', uid: uidAt(both, 0), patch: { group: false } })

    // then: Vendor와 Deal 이름의 집계가 건수다
    expect(columnAt(one, 0)).toMatchObject({ group: false, aggregate: 'count' })
    expect(columnAt(one, 2).aggregate).toBe('count')
  })

  // 테스트 코드: RQ-075
  it('그룹이 있는 동안 그룹 해제한 텍스트 컬럼은 건수가 된다', () => {
    // given: Vendor와 Status를 모두 그룹핑한 설계
    const state = withColumns('deal.vendor', 'deal.status')
    const grouped = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true } },
    )

    // when: Status 그룹핑을 끈다
    const ungrouped = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 1), patch: { group: false } })

    // then: Status는 그룹이 아니고 집계가 건수다
    expect(columnAt(ungrouped, 1)).toMatchObject({ group: false, aggregate: 'count' })
  })

  // 테스트 코드: RQ-075
  it('사용자가 고른 집계는 유지된다', () => {
    // given: Vendor를 그룹핑한 Vendor, 금액 설계
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    // when: 금액 집계를 최대로 고른다
    const picked = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 1), patch: { aggregate: 'max' } })

    // then: 금액 집계가 최대다
    expect(columnAt(picked, 1).aggregate).toBe('max')
  })
})

describe('집계 선택지', () => {
  // 테스트 코드: RQ-075
  it('집계 선택지는 카탈로그를 따른다', () => {
    // when: Deal 코드·Vendor 필드에서 고를 수 있는 집계를 구한다
    const actual = aggregateChoices(fieldOf('deal.code'))
    const actual2 = aggregateChoices(fieldOf('deal.vendor'))
    const actual3 = aggregateChoices(fieldOf('deal.amount'))
    const actual4 = aggregateChoices(fieldOf('action.count'))
    // then: 텍스트·코드는 건수·고유 건수, 숫자는 4종, Action 건수는 건수만 고르게 한다
    expect(actual).toEqual(['count', 'count_distinct'])
    expect(actual2).toEqual(['count', 'count_distinct'])
    expect(actual3).toEqual(['sum', 'avg', 'min', 'max'])
    expect(actual4).toEqual(['count'])
  })
})

describe('앞 N자 옵션', () => {
  // 테스트 코드: RQ-077
  it('앞 N자를 켜면 N이 20이고 입력한 N은 유지된다', () => {
    // given: 앞 N자가 꺼진 Deal 이름 컬럼
    const state = withColumns('deal.name')
    const uid = uidAt(state, 0)

    // when: 앞 N자를 켜고 N을 5로 바꾼다
    const on = reduce(state, { type: 'updateColumn', uid, patch: { prefixOn: true } })
    const longer = reduce(on, { type: 'updateColumn', uid, patch: { prefixLength: 5 } })

    // then: 처음엔 꺼짐·N 없음, 켜면 20, 바꾸면 5다
    expect(columnAt(state, 0)).toMatchObject({ prefixOn: false, prefixLength: null })
    expect(columnAt(on, 0)).toMatchObject({ prefixOn: true, prefixLength: 20 })
    expect(columnAt(longer, 0)).toMatchObject({ prefixOn: true, prefixLength: 5 })
  })

  // 테스트 코드: RQ-077
  it('포맷을 바꿔도 앞 N자 옵션은 유지된다', () => {
    // given: 앞 N자 4를 켠 Expected Close 컬럼
    const state = withColumns('deal.expected_close')
    const uid = uidAt(state, 0)

    const on = reduce(state, { type: 'updateColumn', uid, patch: { prefixOn: true, prefixLength: 4 } })
    // when: 포맷을 요일로 바꾼다
    const changed = reduce(on, { type: 'updateColumn', uid, patch: { format: 'weekday' } })

    // then: 포맷은 요일이고 앞 N자는 켜진 4다
    expect(columnAt(changed, 0)).toMatchObject({ format: 'weekday', prefixOn: true, prefixLength: 4 })
  })

  // 테스트 코드: RQ-074
  it('텍스트·코드·사용자·숫자 컬럼은 포맷 없이, 날짜 컬럼은 기본 포맷으로 시작한다', () => {
    // when: 형식이 다른 컬럼 여섯을 넣는다
    const state = withColumns('deal.name', 'deal.status', 'deal.owner', 'deal.amount', 'deal.expected_close', 'deal.created_at')

    // then: 포맷은 없음 넷, ymd, ymd_hm이고 앞 N자는 모두 꺼져 있다
    expect(state.columns.map((c) => c.format)).toEqual([null, null, null, null, 'ymd', 'ymd_hm'])
    expect(state.columns.every((c) => !c.prefixOn && c.prefixLength === null)).toBe(true)
  })
})

describe('조건 규칙', () => {
  // 테스트 코드: RQ-078
  it('조건 필드에는 조건에 쓸 수 없는 Action 건수가 빠진다', () => {
    // when: 조건에 쓸 수 있는 필드를 거른다
    const fields = filterableFields(REPORT_CATALOG)

    // then: 40개이고 Action 건수는 없다
    expect(fields).toHaveLength(40)
    expect(fields.map((f) => f.key)).not.toContain('action.count')
    expect(fields.every((f) => f.filterable)).toBe(true)
  })

  // 테스트 코드: RQ-078
  it('조건 필드를 바꾸면 연산자와 값이 초기화된다', () => {
    // given: Deal 이름 조건에 같음 연산자와 값 은행을 넣었다
    const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })
    const uid = conditionUidAt(added, 0)
    const typed = reduce(added, { type: 'changeOperator', uid, operator: 'equals' }, { type: 'changeDraft', uid, draft: { shape: 'text', text: '은행' } })

    // when: 조건 필드를 금액으로 바꾼다
    const changed = reduce(typed, { type: 'changeConditionField', uid, field: fieldOf('deal.amount') })

    // then: 필드 금액, 연산자 =, 빈 숫자 값이다
    expect(changed.conditions[0]).toMatchObject({ field: 'deal.amount', operator: 'eq', draft: { shape: 'number', text: '' } })
  })

  // 테스트 코드: RQ-081
  it('연산자 모양마다 그 모양의 빈 값으로 시작한다', () => {
    // given: 조건 하나를 추가한 설계
    const draftOf = (key: string, operator: ReportOperator) => {
      const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf(key) })
      const uid = conditionUidAt(added, 0)
      return reduce(added, { type: 'changeOperator', uid, operator }).conditions[0]?.draft
    }

    // when: 연산자를 바꾼다
    const actual = draftOf('deal.name', 'is_empty')
    const actual2 = draftOf('deal.vendor', 'in')
    const actual3 = draftOf('deal.amount', 'between')
    const actual4 = draftOf('deal.expected_close', 'before')
    const actual5 = draftOf('deal.expected_close', 'between')
    const actual6 = draftOf('deal.created_at', 'between')
    const actual7 = draftOf('deal.expected_close', 'relative')
    // then: 값 없음·목록·범위·날짜·날짜 범위·상대 기간의 빈 값이 된다
    expect(actual).toEqual({ shape: 'none' })
    expect(actual2).toEqual({ shape: 'list', values: [] })
    expect(actual3).toEqual({ shape: 'range', low: '', high: '' })
    expect(actual4).toEqual({ shape: 'date', day: '' })
    expect(actual5).toEqual({ shape: 'date_range', first: '', last: '' })
    expect(actual6).toEqual({ shape: 'date_range', first: '', last: '' })
    expect(actual7).toMatchObject({ shape: 'relative', period: 'this_year' })
  })

  // 테스트 코드: RQ-081
  it('연산자가 같은 모양이면 입력한 값을 유지하고 다르면 버린다', () => {
    // given: 금액 조건에 1,500을 입력했다
    const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.amount') })
    const uid = conditionUidAt(added, 0)
    const typed = reduce(added, { type: 'changeDraft', uid, draft: { shape: 'number', text: '1,500' } })

    // when: 연산자를 같은 모양인 >로, 다른 모양인 범위로 각각 바꾼다
    const sameShape = reduce(typed, { type: 'changeOperator', uid, operator: 'gt' })
    const otherShape = reduce(typed, { type: 'changeOperator', uid, operator: 'between' })

    // then: 같은 모양은 1,500 유지, 다른 모양은 빈 범위다
    expect(sameShape.conditions[0]?.draft).toEqual({ shape: 'number', text: '1,500' })
    expect(otherShape.conditions[0]?.draft).toEqual({ shape: 'range', low: '', high: '' })
  })
})

describe('금액 필드 규칙', () => {
  // 테스트 코드: RQ-082
  it('금액 필드 여부는 카탈로그 단위로 정해진다', () => {
    // when: 금액 필드와 사용자 수 필드가 금액 필드인지 판정한다
    const actual = isMoneyField(fieldOf('deal.amount'))
    const actual2 = isMoneyField(fieldOf('deal.users'))
    const actual3 = isMoneyField(fieldOf('deal.status_days'))
    const actual4 = isMoneyField(fieldOf('action.count'))
    // then: 금액만 true이고 Users count·체류 일수·Action 건수는 false다
    expect(actual).toBe(true)
    expect(actual2).toBe(false)
    expect(actual3).toBe(false)
    expect(actual4).toBe(false)
  })

  // 테스트 코드: RQ-082
  it('금액 필드 여부는 기본 포맷에 기대지 않는다', () => {
    // given: 금액 필드
    const amount = fieldOf('deal.amount')

    // when: 기본 포맷이 있어도 true이고 단위를 뺀다
    const actual = isMoneyField({ ...amount, defaultFormat: 'ymd' })
    const actual2 = isMoneyField({ ...amount, unit: null })
    // then: false다
    expect(actual).toBe(true)
    expect(actual2).toBe(false)
  })
})
