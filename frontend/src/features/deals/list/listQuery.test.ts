import { describe, expect, it } from 'vitest'
import { REMEMBERED_LIST_KEYS } from '../../../shared/model/dealListMemory'
import {
  FILTER_KEYS,
  currentSort,
  defaultListParams,
  effectiveMonth,
  hasActiveFilter,
  hasListCondition,
  listQueryFromParams,
  monthOptions,
  nextSort,
  quarterClearPatch,
  quarterTogglePatch,
  quartersOf,
  updateParams,
} from './listQuery'
import { USER_ID } from '../../../test/fake/seed/ids'

const params = (query: string) => new URLSearchParams(query)

const VENDOR = 3
const PRODUCT = 'ITDR'

describe('listQueryFromParams', () => {
  it('URL 조건이 비어 있으면 쪽 나누기만 담은 조회 조건을 만든다', () => {
    // when: 빈 URL 파라미터를 조회 조건으로 바꾼다
    const actual = listQueryFromParams(params(''))
    // then: 빈 조건은 첫 쪽 20건 조건만 남는다
    expect(actual).toEqual({ offset: 0, limit: 20 })
  })

  it('URL의 모든 검색 조건·정렬·쪽을 조회 조건으로 옮긴다', () => {
    // when: 모든 키가 든 URL 파라미터를 조회 조건으로 바꾼다
    const query = listQueryFromParams(
      params(
        `q=한빛&owner=${USER_ID.kim}&vendor=${VENDOR}&product=${PRODUCT}&status=prospecting&forecast=best&year=2026&quarter=4&updated_from=2026-01-01&updated_to=2026-12-31&mine=1&overdue=1&stale=1&sort=revenueAmount&order=asc&page=3`,
      ),
    )
    // then: 키마다 해당 조회 조건으로 옮겨지고 3쪽은 offset 40이 된다
    expect(query).toEqual({
      keyword: '한빛',
      ownerId: USER_ID.kim,
      vendorId: VENDOR,
      product: PRODUCT,
      statusKey: 'prospecting',
      forecastKeys: ['best'],
      year: 2026,
      quarters: [4],
      updatedFrom: '2026-01-01',
      updatedTo: '2026-12-31',
      mine: true,
      overdue: true,
      stale: true,
      sort: 'revenueAmount',
      order: 'asc',
      offset: 40,
      limit: 20,
    })
  })

  it('최종 업데이트 날짜 하나만 있어도 옮기고, 거꾸로 된 기간도 그대로 보낸다(서버가 422로 답한다)', () => {
    // when: 시작만, 끝만, 거꾸로 된 기간을 각각 조회 조건으로 바꾼다
    const actual1 = listQueryFromParams(params('updated_from=2026-06-01'))
    const actual2 = listQueryFromParams(params('updated_to=2026-06-30'))
    const actual3 = listQueryFromParams(params('updated_from=2026-07-01&updated_to=2026-06-30'))
    // then: 시작만·끝만 있는 날짜는 각각 옮겨지고 거꾸로 된 기간도 그대로 보낸다
    expect(actual1).toEqual({ offset: 0, limit: 20, updatedFrom: '2026-06-01' })
    expect(actual2).toEqual({ offset: 0, limit: 20, updatedTo: '2026-06-30' })
    expect(actual3).toEqual({
      offset: 0,
      limit: 20,
      updatedFrom: '2026-07-01',
      updatedTo: '2026-06-30',
    })
  })

  it.each(['abc', '2026/06/01', '2026-6-1', '2026-02-30', '2026-13-01', '2026-06-01T10:00:00', '20260601', ' '])(
    '형식이 틀린 최종 업데이트 날짜 %j는 무시한다',
    (raw) => {
      // when: 잘못된 날짜를 시작·끝에 넣어 조회 조건으로 바꾼다
      const encoded = encodeURIComponent(raw)
      const query = listQueryFromParams(params(`updated_from=${encoded}&updated_to=${encoded}`))
      // then: 날짜 조건이 모두 빠진다
      expect(query).toEqual({ offset: 0, limit: 20 })
    },
  )

  it('실제 윤일은 받아들이고 윤년이 아닌 해의 2월 29일은 무시한다', () => {
    // when: 2024-02-29와 2026-02-29를 각각 바꾼다
    const actual1 = listQueryFromParams(params('updated_from=2024-02-29'))
    const actual2 = listQueryFromParams(params('updated_from=2026-02-29'))
    // then: 2024-02-29는 유지되고 2026-02-29는 무시된다
    expect(actual1).toEqual({ offset: 0, limit: 20, updatedFrom: '2024-02-29' })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
  })

  it('예전 Expected Close from/to 키는 무시한다', () => {
    // when: from·to 키가 든 URL을 바꾼다
    const actual = listQueryFromParams(params('from=2026-01-01&to=2026-12-31'))
    // then: 예전 from/to 키는 조건이 되지 않는다
    expect(actual).toEqual({ offset: 0, limit: 20 })
  })

  it('깨진 값은 실패하지 않고 무시한다', () => {
    // when: 잘못된 연도·분기·정렬·쪽·내 딜·키워드를 바꾼다
    const query = listQueryFromParams(params('year=abc&quarter=9&sort=bogus&order=up&page=0&mine=0&q=%20%20'))
    // then: 조건이 모두 빠지고 음수·숫자 아닌 쪽도 첫 쪽이 된다
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('page=-3')).offset).toBe(0)
    expect(listQueryFromParams(params('page=x')).offset).toBe(0)
  })

  it('연도 없는 분기도 그대로 보낸다(서버에서는 올해를 뜻한다)', () => {
    // when: 분기만 있는 URL을 바꾼다
    const actual = listQueryFromParams(params('quarter=2'))
    // then: 연도 없이 분기 2만 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, quarters: [2] })
  })

  it('연도와 분기가 함께 있으면 둘 다 담는다', () => {
    // when: 연도·분기가 든 URL을 바꾼다
    const actual = listQueryFromParams(params('year=2027&quarter=1'))
    // then: 연도 2027과 분기 1이 함께 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, year: 2027, quarters: [1] })
  })

  it('연도가 없어도 1~4 밖의 분기는 무시한다', () => {
    // when: 분기 0과 5를 각각 바꾼다
    const actual1 = listQueryFromParams(params('quarter=0'))
    const actual2 = listQueryFromParams(params('quarter=5'))
    // then: 분기 0과 5는 모두 무시된다
    expect(actual1).toEqual({ offset: 0, limit: 20 })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
  })

  it('Vendor id는 정수로, Product는 텍스트로 읽는다', () => {
    // when: Vendor·Product가 든 URL을 바꾼다
    const actual = listQueryFromParams(params('vendor=12&product=ITDR'))
    // then: Vendor id는 정수 12, Product는 ITDR이다
    expect(actual).toEqual({ offset: 0, limit: 20, vendorId: 12, product: 'ITDR' })
  })

  it('Product 텍스트는 그대로 넘긴다', () => {
    // when: 한글·숫자 Product 값을 각각 바꾼다
    const actual1 = listQueryFromParams(params(`product=${encodeURIComponent('통합 itdr')}`))
    const actual2 = listQueryFromParams(params('product=12'))
    // then: Product가 한글·숫자 텍스트 그대로 담긴다
    expect(actual1).toEqual({ offset: 0, limit: 20, product: '통합 itdr' })
    expect(actual2).toEqual({ offset: 0, limit: 20, product: '12' })
  })

  it('Product 텍스트는 앞뒤 공백을 자르고 빈 값은 무시한다', () => {
    // when: 공백이 낀 값, 빈 값, 공백뿐인 값을 각각 바꾼다
    const actual1 = listQueryFromParams(params('product=%20itd%20'))
    const actual2 = listQueryFromParams(params('product='))
    const actual3 = listQueryFromParams(params('product=%20%20'))
    // then: 앞뒤 공백이 잘리고 빈 값·공백뿐인 값은 Product가 빠진다
    expect(actual1).toEqual({ offset: 0, limit: 20, product: 'itd' })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
    expect(actual3).toEqual({ offset: 0, limit: 20 })
  })

  it('공백을 자른 뒤 200자를 넘는 Product는 다른 잘못된 값처럼 무시한다', () => {
    // given: 201자 Product
    const over = 'a'.repeat(201)

    // when: 201자 Product를 단독, 공백 포함, Vendor와 함께 바꾼다
    const alone = listQueryFromParams(params(`product=${over}`))
    const padded = listQueryFromParams(params(`product=%20${over}%20`))
    const withVendor = listQueryFromParams(params(`vendor=12&product=${over}`))

    // then: 모두 Product가 빠진다
    expect(alone).toEqual({ offset: 0, limit: 20 })
    expect(padded).toEqual({ offset: 0, limit: 20 })
    expect(withVendor).toEqual({ offset: 0, limit: 20, vendorId: 12 })
  })

  it('정확히 200자인 Product는 앞뒤 공백이 있어도 유지한다', () => {
    // when: 공백으로 감싼 200자 Product를 바꾼다
    const edge = 'a'.repeat(200)
    const actual = listQueryFromParams(params(`product=%20${edge}%20`))
    // then: 공백만 잘리고 Product가 유지된다
    expect(actual).toEqual({ offset: 0, limit: 20, product: edge })
  })

  it('Vendor에서는 uuid·이름 값을 무시하고 Product 텍스트에서는 무시하지 않는다', () => {
    // when: 이름·uuid Vendor와 정수 Vendor+Product를 각각 바꾼다
    const actual1 = listQueryFromParams(params('vendor=Okta'))
    const actual2 = listQueryFromParams(params('vendor=10000000-0000-4000-8000-000000000003'))
    const actual3 = listQueryFromParams(params(`vendor=${VENDOR}&product=ITDR`))
    // then: 이름·uuid Vendor는 빠지고 정수 Vendor와 Product는 담긴다
    expect(actual1).toEqual({ offset: 0, limit: 20 })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
    expect(actual3).toEqual({ offset: 0, limit: 20, vendorId: VENDOR, product: 'ITDR' })
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', '9007199254740992'])(
    '범위 밖이거나 정수가 아닌 id %j는 모든 id 파라미터에서 무시한다',
    (raw) => {
      // when: Vendor·담당자 파라미터에 같은 값을 넣어 바꾼다
      const encoded = encodeURIComponent(raw)
      const actual = listQueryFromParams(params(`vendor=${encoded}&owner=${encoded}`))
      // then: 두 id 조건이 모두 빠진다
      expect(actual).toEqual({
        offset: 0,
        limit: 20,
      })
    },
  )

  it('가장 큰 안전 정수는 id로 받아들인다', () => {
    // when: 9007199254740991 Vendor를 바꾼다
    const actual = listQueryFromParams(params('vendor=9007199254740991'))
    // then: 가장 큰 안전 정수가 Vendor id로 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, vendorId: 9007199254740991 })
  })

  it('담당자 파라미터의 예전 uuid·사용자 키는 무시한다', () => {
    // when: u-kim과 uuid 값을 각각 바꾼다
    const actual1 = listQueryFromParams(params('owner=u-kim'))
    const actual2 = listQueryFromParams(params('owner=0f0e0d0c-0b0a-4908-8706-050403020100'))
    // then: 예전 uuid·사용자 키는 담당자 조건이 되지 않는다
    expect(actual1).toEqual({ offset: 0, limit: 20 })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
  })
})

describe('updateParams', () => {
  it('값을 지정하고 빈 값은 지우며 첫 쪽으로 돌아간다', () => {
    // given: q·page·vendor가 든 URL
    const current = params(`q=a&page=3&vendor=${VENDOR}`)
    // when: Vendor를 비우고 Status를 지정한다
    const next = updateParams(current, { vendor: '', status: 'best' })
    // then: Vendor는 지워지고 Status가 생기며 q는 남고 쪽은 사라진다
    expect(next.get('vendor')).toBeNull()
    expect(next.get('status')).toBe('best')
    expect(next.get('q')).toBe('a')
    expect(next.get('page')).toBeNull()
  })

  it('최종 업데이트 날짜도 다른 조건처럼 지정하고 지운다', () => {
    // when: 날짜를 지정한다
    const set = updateParams(params('page=2'), { updated_from: '2026-06-01', updated_to: '2026-06-30' })
    // then: 날짜가 들어가고 쪽 키가 사라진다
    expect(set.get('updated_from')).toBe('2026-06-01')
    expect(set.get('updated_to')).toBe('2026-06-30')
    expect(set.get('page')).toBeNull()
    // when: 두 날짜를 빈 값으로 지운다
    const cleared = updateParams(set, { updated_from: '', updated_to: '' })
    // then: 파라미터가 비어 있다
    expect(cleared.toString()).toBe('')
  })

  it('쪽만 바꾸면 쪽을 유지하고 1쪽은 키를 생략한다', () => {
    // when: 쪽을 2로, 1로 각각 바꾼다
    const actual1 = updateParams(params('q=a'), { page: '2' }).get('page')
    const actual2 = updateParams(params('q=a&page=2'), { page: '1' }).get('page')
    // then: 쪽 2는 유지되고 1쪽은 키가 없다
    expect(actual1).toBe('2')
    expect(actual2).toBeNull()
  })
})

describe('hasActiveFilter', () => {
  it('정렬과 쪽만 있으면 활성 조건이 아니다', () => {
    // when: 정렬·쪽만 든 URL을 판정한다
    const actual = hasActiveFilter(params('sort=name&order=asc&page=2'))
    // then: 정렬·쪽만으로는 활성 조건이 아니다
    expect(actual).toBe(false)
  })
  it('최종 업데이트 날짜는 활성 조건이고 예전 from/to 키는 아니다', () => {
    // when: 날짜 키와 예전 키를 각각 판정한다
    const actual1 = hasActiveFilter(params('updated_from=2026-06-01'))
    const actual2 = hasActiveFilter(params('updated_to=2026-06-30'))
    const actual3 = hasActiveFilter(params('from=2026-06-01&to=2026-06-30'))
    // then: 날짜 키는 활성 조건이고 예전 from/to는 아니다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
  })
  it('내 딜만을 포함한 어떤 조건이든 활성 조건이다', () => {
    // when: mine·q를 각각 판정한다
    const actual1 = hasActiveFilter(params('mine=1'))
    const actual2 = hasActiveFilter(params('q=a'))
    // then: 내 딜만과 키워드는 활성 조건이다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
  })
})

describe('FILTER_KEYS', () => {
  it('검색 조건 키는 16개이고 outcome·BANT 키는 없으며 month·owner_name과 overdue/stale은 있다', () => {
    // when·then: 상수 목록(검색 조건 키·기억 키)을 확인한다
    expect(FILTER_KEYS).toHaveLength(16)
    expect(FILTER_KEYS).toContain('owner_name')
    expect(REMEMBERED_LIST_KEYS).toContain('owner_name')
    expect(FILTER_KEYS).not.toContain('outcome')
    expect(REMEMBERED_LIST_KEYS).not.toContain('outcome')
    expect(FILTER_KEYS).toContain('month')
    expect(REMEMBERED_LIST_KEYS).toContain('month')
    expect(FILTER_KEYS).toContain('updated_from')
    expect(FILTER_KEYS).toContain('updated_to')
    expect(FILTER_KEYS).not.toContain('from')
    expect(FILTER_KEYS).not.toContain('to')
    expect(REMEMBERED_LIST_KEYS).toContain('updated_from')
    expect(REMEMBERED_LIST_KEYS).not.toContain('from')
  })

  it.each(['budget', 'authority', 'need', 'timeline'])('BANT 키 %s는 더 이상 조건 키가 아니다', (key) => {
    // when·then: 상수 목록(검색 조건 키·기억 키)을 확인한다
    expect(FILTER_KEYS).not.toContain(key)
    expect(REMEMBERED_LIST_KEYS).not.toContain(key)
  })

  it.each(['overdue', 'stale'])('%s는 검색 조건 키이자 기억 키이다', (key) => {
    // when·then: 상수 목록(검색 조건 키·기억 키)을 확인한다
    expect(FILTER_KEYS).toContain(key)
    expect(REMEMBERED_LIST_KEYS).toContain(key)
  })
})

describe('sorting', () => {
  it('정렬 기본값은 최근 업데이트 순이다', () => {
    // when: 정렬 파라미터 없이 현재 정렬을 읽는다
    const actual = currentSort(params(''))
    // then: 기본 정렬은 lastUpdatedOn 내림차순이다
    expect(actual).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
  })

  it('새 열은 본래 방향으로 시작하고 두 번째 클릭에서 뒤집는다', () => {
    // when: 열을 바꿔 가며 다음 정렬을 구한다
    const actual1 = nextSort({ sort: 'lastUpdatedAt', order: 'desc' }, 'revenueDate')
    const actual2 = nextSort({ sort: 'revenueDate', order: 'asc' }, 'revenueDate')
    const actual3 = nextSort({ sort: 'name', order: 'asc' }, 'revenueAmount')
    // then: 새 열은 오름차순, 같은 열 다시 누르면 내림차순, 금액은 내림차순으로 시작한다
    expect(actual1).toEqual({ sort: 'revenueDate', order: 'asc' })
    expect(actual2).toEqual({ sort: 'revenueDate', order: 'desc' })
    expect(actual3).toEqual({ sort: 'revenueAmount', order: 'desc' })
  })
})

describe('sorting by the new columns', () => {
  const NEW_KEYS = ['owner', 'customer', 'partner', 'vendor', 'forecastKey'] as const

  it.each(NEW_KEYS)('%s 열은 오름차순으로 시작한다', (key) => {
    // when: 다른 열에서 이 열로 바꿀 때의 정렬을 구한다
    const actual = nextSort({ sort: 'lastUpdatedAt', order: 'desc' }, key)
    // then: 이 열은 오름차순으로 시작한다
    expect(actual).toEqual({ sort: key, order: 'asc' })
  })

  it.each(NEW_KEYS)('%s 열은 두 번째 클릭에서 양방향으로 뒤집는다', (key) => {
    // when: 오름·내림 상태에서 같은 열을 다시 누른 정렬을 구한다
    const actual1 = nextSort({ sort: key, order: 'asc' }, key)
    const actual2 = nextSort({ sort: key, order: 'desc' }, key)
    // then: 오름은 내림으로, 내림은 오름으로 뒤집힌다
    expect(actual1).toEqual({ sort: key, order: 'desc' })
    expect(actual2).toEqual({ sort: key, order: 'asc' })
  })

  it.each(NEW_KEYS)('URL의 sort=%s를 본래 방향 또는 지정한 방향으로 읽는다', (key) => {
    // when: 방향 없는 URL과 방향이 있는 URL을 각각 읽는다
    const actual1 = currentSort(params(`sort=${key}`))
    const actual2 = currentSort(params(`sort=${key}&order=desc`))
    const actual3 = listQueryFromParams(params(`sort=${key}&order=desc`))
    // then: 방향이 없으면 오름, 지정하면 그 방향으로 읽히고 조회 조건에도 담긴다
    expect(actual1).toEqual({ sort: key, order: 'asc' })
    expect(actual2).toEqual({ sort: key, order: 'desc' })
    expect(actual3).toEqual({ offset: 0, limit: 20, sort: key, order: 'desc' })
  })

  it.each(['forecast', 'bant', 'nextAction', 'risk', 'OWNER'])('모르는 정렬 %s는 기본 정렬로 되돌린다', (raw) => {
    // when: 모르는 정렬 값이 든 URL을 읽는다
    const actual1 = currentSort(params(`sort=${raw}&order=asc`))
    const actual2 = listQueryFromParams(params(`sort=${raw}`))
    // then: 기본 정렬로 읽히고 조회 조건에는 정렬이 없다
    expect(actual1).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
    expect(actual2).toEqual({ offset: 0, limit: 20 })
  })

  it('기존 열의 본래 방향은 그대로다', () => {
    // when: 금액·최종 업데이트·Status 열로 바꿀 때의 정렬을 구한다
    const actual1 = nextSort({ sort: 'name', order: 'asc' }, 'revenueAmount')
    const actual2 = nextSort({ sort: 'name', order: 'asc' }, 'lastUpdatedAt')
    const actual3 = nextSort({ sort: 'name', order: 'desc' }, 'statusKey')
    // then: 금액·최종 업데이트는 내림, Status는 오름으로 시작한다
    expect(actual1).toEqual({ sort: 'revenueAmount', order: 'desc' })
    expect(actual2).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
    expect(actual3).toEqual({ sort: 'statusKey', order: 'asc' })
  })
})

describe('retired BANT URL keys', () => {
  it('예전 budget/authority/need/timeline 키는 조회 조건이 되지 않는다', () => {
    // when: 예전 BANT 키가 든 URL을 바꾼다
    const query = listQueryFromParams(params('budget=1&authority=2&need=3&timeline=4'))

    // then: 쪽 나누기만 남고 BANT 조건은 없다
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(query).not.toHaveProperty('bantLabelIds')
  })

  it('예전 BANT 키는 활성 조건으로 세지 않는다', () => {
    // when: 예전 키가 든 URL을 판정한다
    const actual = hasActiveFilter(params('budget=1&authority=2&need=3&timeline=4'))
    // then: 예전 BANT 키는 활성 조건이 아니다
    expect(actual).toBe(false)
  })

  it('예전 BANT 키가 있어도 다른 조건은 유지한다', () => {
    // when: BANT 키와 Status가 함께 든 URL을 바꾼다
    const actual = listQueryFromParams(params('budget=1&status=best'))
    // then: BANT 키는 무시되고 Status 조건만 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, statusKey: 'best' })
  })
})

describe('overdue and stale URL keys', () => {
  it('overdue=1과 stale=1은 각각 단독으로 true가 된다', () => {
    // when: 각각 단독인 URL을 바꾼다
    const actual1 = listQueryFromParams(params('overdue=1'))
    const actual2 = listQueryFromParams(params('stale=1'))
    // then: overdue와 stale이 각각 true로 담긴다
    expect(actual1).toEqual({ offset: 0, limit: 20, overdue: true })
    expect(actual2).toEqual({ offset: 0, limit: 20, stale: true })
  })

  it.each(['0', 'yes', 'true', '', '2'])('overdue·stale의 값 %j는 내 딜만처럼 무시한다', (raw) => {
    // when: 1이 아닌 값을 넣은 URL을 바꾼다
    const actual = listQueryFromParams(params(`overdue=${raw}&stale=${raw}`))
    // then: 1이 아닌 값은 조건에서 빠진다
    expect(actual).toEqual({ offset: 0, limit: 20 })
  })

  it('overdue·stale은 활성 조건으로 센다', () => {
    // when: 각각 켠 URL과 빈 값 URL을 판정한다
    const actual1 = hasActiveFilter(params('overdue=1'))
    const actual2 = hasActiveFilter(params('stale=1'))
    const actual3 = hasActiveFilter(params('overdue=&stale='))
    // then: overdue·stale은 활성 조건이고 빈 값은 아니다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
  })

  it('하나가 바뀌면 첫 쪽으로 돌아가고 지우면 키가 사라진다', () => {
    // when: 3쪽에서 overdue를 켠다
    const on = updateParams(params('page=3'), { overdue: '1' })
    // then: 키가 생기고 쪽 키가 사라진다
    expect(on.get('overdue')).toBe('1')
    expect(on.has('page')).toBe(false)
    // when: overdue를 비우고, 2쪽에서 stale을 켠다
    const off = updateParams(on, { overdue: '' })
    const stale = updateParams(params('page=2'), { stale: '1' })
    // then: overdue 키가 사라지고 stale을 켜도 쪽 키가 사라진다
    expect(off.has('overdue')).toBe(false)
    expect(stale.has('page')).toBe(false)
  })
})

describe('목록 조건 기억 키', () => {
  it('기억 키는 검색 조건 키에 정렬·방향·쪽을 더한 것과 같다', () => {
    // when: 두 목록을 정렬해 비교한다
    const actual = [...REMEMBERED_LIST_KEYS].sort()
    // then: 기억 키가 검색 조건 키에 sort·order·page를 더한 목록과 같다
    expect(actual).toEqual([...FILTER_KEYS, 'sort', 'order', 'page'].sort())
  })
})

describe('next_status URL 키', () => {
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
    ['closed', 'closed'],
  ] as const)('next_status=%s는 nextActionStatus %s로 옮긴다', (wire, status) => {
    // when: 해당 값이 든 URL을 바꾼다
    const actual = listQueryFromParams(params(`next_status=${wire}`))
    // then: next_status 값이 해당 nextActionStatus로 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, nextActionStatus: status })
  })

  it.each(['', 'bogus', 'notDone', 'DONE', 'all'])('next_status=%s는 무시한다', (value) => {
    // when: 알 수 없는 값이 든 URL을 바꾼다
    const actual = listQueryFromParams(params(`next_status=${value}`))
    // then: 알 수 없는 next_status는 조건에서 빠진다
    expect(actual).toEqual({ offset: 0, limit: 20 })
  })

  it('next_status는 활성 조건이자 기억 키이다', () => {
    // when: next_status가 있는 URL과 빈 값 URL을 판정한다
    const actual1 = hasActiveFilter(params('next_status=open'))
    const actual2 = hasActiveFilter(params('next_status='))
    // then: 값이 있을 때만 활성 조건이고, 키는 검색 조건 키이자 기억 키이다
    expect(actual1).toBe(true)
    expect(actual2).toBe(false)
    expect(FILTER_KEYS).toContain('next_status')
    expect(REMEMBERED_LIST_KEYS).toContain('next_status')
  })

  it('next_status가 바뀌면 첫 쪽으로 돌아간다', () => {
    // when: 3쪽에서 next_status를 closed로 바꾼다
    const next = updateParams(params('page=3'), { next_status: 'closed' })

    // then: 값이 들어가고 쪽 키가 사라진다
    expect(next.get('next_status')).toBe('closed')
    expect(next.has('page')).toBe(false)
  })
})

describe('month URL key', () => {
  it('월은 연도와 함께 옮긴다', () => {
    // when: 연도·월이 든 URL을 바꾼다
    const actual = listQueryFromParams(params('year=2026&month=3'))
    // then: 연도 2026과 월 3이 함께 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, year: 2026, month: 3 })
  })

  it('연도 없는 월도 그대로 보낸다(서버에서는 올해를 뜻한다)', () => {
    // when: 월만 있는 URL을 바꾼다
    const actual = listQueryFromParams(params('month=3'))
    // then: 연도 없이 월 3만 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, month: 3 })
  })

  it.each(['0', '13', 'abc', '1.5', ''])('1~12 밖의 월 %j는 무시한다', (raw) => {
    // when: 잘못된 월이 든 URL을 바꾼다
    const actual = listQueryFromParams(params(`month=${raw}`))
    // then: 범위 밖·형식이 틀린 월은 무시된다
    expect(actual).toEqual({ offset: 0, limit: 20 })
  })

  it('월이 고른 분기에 속하면 월만 보낸다', () => {
    // when: 2026년 4분기 11월 URL을 바꾼다
    const query = listQueryFromParams(params('year=2026&quarter=4&month=11'))
    // then: 월만 남고 분기는 없다
    expect(query).toEqual({ offset: 0, limit: 20, year: 2026, month: 11 })
    expect(query).not.toHaveProperty('quarters')
  })

  it('월은 활성 조건이고 바뀌면 첫 쪽으로 돌아간다', () => {
    // when: month=3 URL의 활성 조건 판정과, 3쪽 URL에서 월을 바꾼 쪽 키를 구한다
    const actual1 = hasActiveFilter(params('month=3'))
    const actual2 = updateParams(params('page=3'), { month: '3' }).get('page')
    // then: 월은 활성 조건이고 월을 바꾸면 쪽 키가 사라진다
    expect(actual1).toBe(true)
    expect(actual2).toBeNull()
  })
})

describe('month URL value format matches the Forecast screen', () => {
  it.each(['03', '01', '012', '+3', ' 3', '3 '])('월 %j는 Forecast URL 해석기처럼 무시한다', (raw) => {
    // when: 0 채움·부호·공백이 든 월을 바꾼다
    const actual = listQueryFromParams(params(`year=2026&month=${encodeURIComponent(raw)}`))
    // then: 0 채움·부호·공백이 든 월은 무시된다
    expect(actual).toEqual({ offset: 0, limit: 20, year: 2026 })
  })

  it.each(['1', '9', '10', '12'])('평범한 월 %j는 받아들인다', (raw) => {
    // when: 월 URL을 바꾼다
    const actual = listQueryFromParams(params(`month=${raw}`))
    // then: 평범한 월은 숫자로 담긴다
    expect(actual).toMatchObject({ month: Number(raw) })
  })
})

describe('forecast URL value is a comma separated key list (다중 조건)', () => {
  it('정렬하고 중복을 없앤 키 목록으로 읽는다', () => {
    // when: 쉼표로 이은 Forecast 값을 바꾼다
    const actual1 = listQueryFromParams(params('forecast=pipeline%2Cbest'))
    const actual2 = listQueryFromParams(params('forecast=best%2Cbest%2C'))
    // then: Forecast 키가 정렬·중복 제거되어 담긴다
    expect(actual1).toEqual({ offset: 0, limit: 20, forecastKeys: ['best', 'pipeline'] })
    expect(actual2).toEqual({ offset: 0, limit: 20, forecastKeys: ['best'] })
  })

  it('예전 단일 값은 키 하나로 읽는다', () => {
    // when: forecast=commit을 바꾼다
    const actual = listQueryFromParams(params('forecast=commit'))
    // then: 단일 값이 키 하나로 담긴다
    expect(actual).toMatchObject({ forecastKeys: ['commit'] })
  })

  it('형식이 틀린 키는 버린다', () => {
    // when: 대문자가 섞인 값과 잘못된 값을 바꾼다
    const actual1 = listQueryFromParams(params('forecast=Commit%2Cbest'))
    const actual2 = listQueryFromParams(params('forecast=XYZ'))
    // then: 형식이 틀린 키는 빠지고 맞는 키만 남으며 전부 틀리면 조건이 없다
    expect(actual1).toMatchObject({ forecastKeys: ['best'] })
    expect(actual2).not.toHaveProperty('forecastKeys')
  })

  it('형식이 맞으면 없는 코드여도 유지한다(서버가 0건으로 답한다)', () => {
    // when: 없는 코드의 키를 바꾼다
    const actual = listQueryFromParams(params('forecast=no_such'))
    // then: 형식이 맞는 없는 코드도 담긴다
    expect(actual).toMatchObject({ forecastKeys: ['no_such'] })
  })

  it('서로 다른 키가 100개를 넘으면 조건 전체를 무시한다', () => {
    // when: 키 101개를 넣어 바꾼다
    const many = Array.from({ length: 101 }, (_, i) => `k${i}`).join('%2C')
    const actual = listQueryFromParams(params(`forecast=${many}`))
    // then: Forecast 조건 전체가 빠진다
    expect(actual).not.toHaveProperty('forecastKeys')
  })

  it('폐지된 단일 키 필드는 보내지 않는다', () => {
    // when: forecast=commit을 바꾼다
    const actual = listQueryFromParams(params('forecast=commit'))
    // then: 예전 단일 키 필드는 조회 조건에 없다
    expect(actual).not.toHaveProperty('forecastKey')
  })

  it('잘못된 값도 조건 키로는 센다', () => {
    // when: forecast=XYZ를 판정한다
    const actual = hasListCondition(params('forecast=XYZ'))
    // then: 형식이 틀린 forecast 값도 조건 키로 센다
    expect(actual).toBe(true)
  })
})

describe('outcome URL key is retired', () => {
  it.each(['open', 'won', 'lost', 'not_lost'])('outcome=%s는 무시한다', (value) => {
    // when: outcome이 든 URL을 바꾼다
    const query = listQueryFromParams(params(`outcome=${value}`))
    // then: 쪽 나누기만 남고 forecastOutcome이 없다
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(query).not.toHaveProperty('forecastOutcome')
  })

  it('forecast 키 옆의 outcome은 무시한다', () => {
    // when: forecast와 outcome이 함께 든 URL을 바꾼다
    const query = listQueryFromParams(params('forecast=commit&outcome=open'))
    // then: forecast만 남고 forecastOutcome이 없다
    expect(query).toEqual({ offset: 0, limit: 20, forecastKeys: ['commit'] })
    expect(query).not.toHaveProperty('forecastOutcome')
  })

  it('outcome은 활성 조건으로 세지 않는다', () => {
    // when: outcome이 든 URL을 판정한다
    const actual = hasActiveFilter(params('outcome=open'))
    // then: outcome은 활성 조건이 아니다
    expect(actual).toBe(false)
  })
})

describe('year=all', () => {
  it('year=all은 연도로 보내지 않는다', () => {
    // when: year=all과 분기가 든 URL을 바꾼다
    const actual = listQueryFromParams(params('year=all&quarter=4'))
    // then: 연도는 빠지고 분기 4만 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, quarters: [4] })
  })

  it('year=all은 빈 상태 안내 문구에서 활성 조건이 아니다', () => {
    // when: year=all, 분기, 연도, outcome을 각각 판정한다
    const actual1 = hasActiveFilter(params('year=all'))
    const actual2 = hasActiveFilter(params('year=all&quarter=4'))
    const actual3 = hasActiveFilter(params('year=2026'))
    const actual4 = hasActiveFilter(params('outcome=open'))
    // then: year=all만 있으면 활성 조건이 아니고 분기·연도가 더해지면 활성 조건이다
    expect(actual1).toBe(false)
    expect(actual2).toBe(true)
    expect(actual3).toBe(true)
    expect(actual4).toBe(false)
  })
})

describe('defaultListParams', () => {
  it.each(['2026-10-26', '2027-01-01', '2026-03-31', '2026-04-01'])(
    '%s에도 기본 조건은 연도 전체이고 분기가 없다 (admin)',
    (today) => {
      // when: admin의 기본 파라미터를 만든다
      const actual = defaultListParams(today, 'admin').toString()
      // then: 오늘 날짜와 무관하게 연도 전체만 담긴다
      expect(actual).toBe('year=all')
    },
  )

  it('정렬과 방향은 유지하고 쪽과 모르는 키는 버린다 (admin)', () => {
    // given: 정렬·쪽·outcome이 든 현재 파라미터
    const current = params('sort=owner&order=asc&page=3&outcome=open')
    // when: admin의 기본 파라미터를 만든다
    const actual = defaultListParams('2026-10-26', 'admin', current).toString()
    // then: 정렬·방향만 남고 쪽·outcome은 버려진다
    expect(actual).toBe('year=all&sort=owner&order=asc')
  })

  // 테스트 코드: DL-101
  it.each(['2026-10-26', '2027-01-01'])('%s에도 sales의 기본 조건이 연도 전체와 내 딜만이다', (today) => {
    // when: sales의 기본 파라미터를 만든다
    const actual = defaultListParams(today, 'sales').toString()
    // then: year=all과 mine=1이 담긴다
    expect(actual).toBe('year=all&mine=1')
  })

  it('admin과 user의 기본 조건에는 내 딜만이 없다', () => {
    // when: 두 역할의 기본 파라미터를 만든다
    const admin = defaultListParams('2026-10-26', 'admin')
    const user = defaultListParams('2026-10-26', 'user')
    // then: 둘 다 연도 전체만이고 mine 키가 없다
    expect(admin.toString()).toBe('year=all')
    expect(user.toString()).toBe('year=all')
    expect(admin.has('mine')).toBe(false)
    expect(user.has('mine')).toBe(false)
  })

  it('sales의 기본 조건도 정렬과 방향은 이어받고 쪽과 모르는 키와 현재 mine은 버린다', () => {
    // given: 정렬·쪽·모르는 키·mine이 든 현재 파라미터
    const current = params('sort=owner&order=desc&page=3&foo=1&mine=0')
    // when: sales의 기본 파라미터를 만든다
    const actual = defaultListParams('2026-10-26', 'sales', current)
    // then: year=all·mine=1·정렬·방향만 남는다
    expect(Object.fromEntries(actual.entries())).toEqual({ year: 'all', mine: '1', sort: 'owner', order: 'desc' })
  })

  it('기본 조건의 조회 조건에는 연도와 분기가 없다', () => {
    // when: sales의 기본 파라미터를 조회 조건으로 바꾼다
    const query = listQueryFromParams(defaultListParams('2026-10-26', 'sales'))
    // then: 연도·분기 없이 내 딜만 조건만 담긴다
    expect(query).toEqual({ mine: true, offset: 0, limit: 20 })
  })
})

describe('hasListCondition', () => {
  it.each(['', 'q=', 'q=%20', 'sort=name&page=2', 'outcome=open', 'foo=1'])('%j는 목록 조건이 아니다', (query) => {
    // when: 판정한다
    const actual = hasListCondition(params(query))
    // then: 조건이 없는 URL은 목록 조건이 아니다
    expect(actual).toBe(false)
  })

  it.each(['year=all', 'quarter=4', 'overdue=1', 'owner=abc', 'month=3'])('%j는 목록 조건이다', (query) => {
    // when: 판정한다
    const actual = hasListCondition(params(query))
    // then: 조건이 있는 URL은 목록 조건이다
    expect(actual).toBe(true)
  })
})

describe('quarter and month rules (to)', () => {
  it('분기와 월을 함께 보내지 않는다', () => {
    for (let quarter = 1; quarter <= 4; quarter += 1) {
      for (let month = 1; month <= 12; month += 1) {
        // when: 분기·월 조합을 조회 조건으로 바꾼다
        const query = listQueryFromParams(params(`year=2026&quarter=${quarter}&month=${month}`))
        // then: 분기와 월 중 하나만 남는다
        expect(query.quarters !== undefined && query.month !== undefined).toBe(false)
        expect(query.quarters !== undefined || query.month !== undefined).toBe(true)
      }
    }
  })

  it('월이 분기 밖이면 분기만 유지한다', () => {
    // when: 4분기에 3월을 넣은 URL을 바꾼다
    const actual = listQueryFromParams(params('year=2026&quarter=4&month=3'))
    // then: 분기 4에 월 3은 분기만 남는다
    expect(actual).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [4] })
  })

  it('분기가 올바르지 않으면 월을 유지한다', () => {
    // when: 분기 9와 월 3을 바꾼다
    const actual = listQueryFromParams(params('quarter=9&month=3'))
    // then: 분기 9는 무시되고 월 3이 유지된다
    expect(actual).toEqual({ offset: 0, limit: 20, month: 3 })
  })

  it.each([
    ['quarter=4&month=11', 11],
    ['quarter=4&month=3', undefined],
    ['month=3', 3],
    ['quarter=9&month=3', 3],
    ['month=13', undefined],
    ['', undefined],
  ])('%j의 유효한 월은 %s이다', (query, expected) => {
    // when: 유효한 월을 구한다
    const actual = effectiveMonth(params(query))
    // then: 분기에 든 월은 그대로, 밖의 월은 없음이다
    expect(actual).toBe(expected)
  })

  it('고른 분기의 석 달을 주고, 아니면 열두 달을 준다', () => {
    // when: 분기별 월 선택지를 구한다
    const actual1 = monthOptions(params('quarter=2'))
    const actual2 = monthOptions(params('quarter=4'))
    const actual3 = monthOptions(params(''))
    const actual4 = monthOptions(params('quarter=9'))
    // then: 분기 2는 4~6월, 분기 4는 10~12월, 분기가 없으면 12개월이다
    expect(actual1).toEqual([4, 5, 6])
    expect(actual2).toEqual([10, 11, 12])
    expect(actual3).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(actual4).toHaveLength(12)
  })

  it('여러 분기를 고르면 그 달들의 합집합을 준다', () => {
    // when: 두 분기를 고른 URL의 월 선택지를 구한다
    const actual1 = monthOptions(params('quarter=1%2C3'))
    const actual2 = monthOptions(params('quarter=4%2C2'))
    // then: 분기 1·3은 1~3·7~9월, 분기 4·2는 4~6·10~12월이다
    expect(actual1).toEqual([1, 2, 3, 7, 8, 9])
    expect(actual2).toEqual([4, 5, 6, 10, 11, 12])
  })

  it('분기 넷을 모두 고르면 열두 달을 준다', () => {
    // when: 네 분기의 월 선택지를 구한다
    const actual = monthOptions(params('quarter=1%2C2%2C3%2C4'))
    // then: 열두 달이 모두 나온다
    expect(actual).toHaveLength(12)
  })

  it('토글한 분기에 월이 없으면 월을 지운다', () => {
    // when: Q1·Q3와 월 2를 고른 상태에서 Q1을 끄는 변경 내용을 구한다 (Q1을 끄면 Q3만 남아 월 2는 사라진다)
    const actual = quarterTogglePatch(params('quarter=1%2C3&month=2'), 1, false)
    // then: Q1을 끄면 분기 3만 남고 월은 비워진다
    expect(actual).toEqual({ quarter: '3', month: '' })
  })

  it('새 분기에도 월이 있으면 보이는 월을 유지한다', () => {
    // when: 분기를 토글하는 변경 내용을 구한다
    const actual1 = quarterTogglePatch(params('quarter=1&month=2'), 2, true)
    const actual2 = quarterTogglePatch(params('quarter=1%2C3&month=8'), 1, false)
    // then: Q2를 켜도 월 2는 유지되고 Q1을 꺼도 월 8은 유지된다
    expect(actual1).toEqual({ quarter: '1,2' })
    expect(actual2).toEqual({ quarter: '3' })
  })

  it('첫 분기를 켜도 보이는 월은 건드리지 않는다', () => {
    // when: 월 5가 든 상태에서 Q2를 켠 변경 내용을 구한다
    const actual = quarterTogglePatch(params('month=5'), 2, true)
    // then: Q2만 켜고 월 5는 건드리지 않는다
    expect(actual).toEqual({ quarter: '2' })
  })

  it('첫 분기에 없는 월은 지운다', () => {
    // when: 월 5가 든 상태에서 Q1을 켠 변경 내용을 구한다
    const actual = quarterTogglePatch(params('month=5'), 1, true)
    // then: Q1을 켜면 월 5가 비워진다
    expect(actual).toEqual({ quarter: '1', month: '' })
  })

  it('토글한 분기를 오름차순 쉼표 목록으로 쓴다', () => {
    // when: 분기를 켜고 끈 변경 내용을 구한다
    const actual1 = quarterTogglePatch(params('quarter=3'), 1, true).quarter
    const actual2 = quarterTogglePatch(params('quarter=1%2C3'), 3, false).quarter
    // then: 분기가 1,3으로 쓰이고 3을 끄면 1만 남는다
    expect(actual1).toBe('1,3')
    expect(actual2).toBe('1')
  })

  it('마지막 분기를 끄면 빈 분기를 쓴다', () => {
    // when: 하나만 고른 상태에서 그 분기를 끈 변경 내용을 구한다
    const actual = quarterTogglePatch(params('quarter=2'), 2, false)
    // then: 분기가 빈 값이 된다
    expect(actual).toEqual({ quarter: '' })
  })

  it('현재 분기에서 보이지 않던 월은 새 분기에 들어도 지운다', () => {
    // when: Q1·Q3와 월 5에서 Q2를 켠 변경 내용을 구한다
    const actual = quarterTogglePatch(params('year=2026&quarter=1%2C3&month=5'), 2, true)
    // then: Q2를 켜면 분기는 1,2,3이고 보이지 않던 월은 비워진다
    expect(actual).toEqual({ quarter: '1,2,3', month: '' })
  })

  it('넷째 분기를 켜면 네 분기를 모두 URL에 유지한다', () => {
    // when: Q1~Q3에서 Q4를 켠 변경 내용을 구한다
    const actual = quarterTogglePatch(params('quarter=1%2C2%2C3'), 4, true)
    // then: Q4를 켜면 1,2,3,4가 모두 남는다
    expect(actual).toEqual({ quarter: '1,2,3,4' })
  })

  it('전체 버튼으로 분기를 지워도 보이는 월은 유지한다', () => {
    // when: 분기 해제 변경 내용을 구한다
    const actual1 = quarterClearPatch(params('quarter=4&month=11'))
    const actual2 = quarterClearPatch(params('quarter=1%2C3&month=8'))
    // then: 분기만 비워지고 보이던 월은 그대로다
    expect(actual1).toEqual({ quarter: '' })
    expect(actual2).not.toHaveProperty('month')
  })

  it('전체 버튼으로 분기를 지우면 보이지 않던 월은 지운다', () => {
    // when: 분기 해제 변경 내용을 구한다
    const actual = quarterClearPatch(params('quarter=4&month=3'))
    // then: 분기만 비워지고 보이지 않던 월도 함께 비워진다
    expect(actual).toEqual({ quarter: '', month: '' })
  })
})

describe('Quarter multi-select in the URL', () => {
  it('여러 분기를 오름차순 목록으로 읽는다', () => {
    // when: 분기 목록 URL을 읽는다
    const actual1 = quartersOf(params('quarter=3%2C1'))
    const actual2 = listQueryFromParams(params('year=2026&quarter=1%2C3'))
    // then: 분기가 오름차순 목록이 되고 조회 조건에는 1·3이 담긴다
    expect(actual1).toEqual([1, 3])
    expect(actual2).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [1, 3] })
  })

  it('월이 고른 분기들 중 하나에 속하면 월만 보낸다', () => {
    // when: Q1·Q3와 월 8이 든 URL을 바꾼다
    const query = listQueryFromParams(params('year=2026&quarter=1%2C3&month=8'))

    // then: 월만 남는다
    expect(query).toEqual({ offset: 0, limit: 20, year: 2026, month: 8 })
  })

  it('월이 고른 분기들 밖이면 분기만 보낸다', () => {
    // when: Q1·Q3와 월 5가 든 URL을 바꾼다
    const actual = listQueryFromParams(params('year=2026&quarter=1%2C3&month=5'))
    // then: 월이 속한 분기들이면 월만, 밖이면 분기만 담긴다
    expect(actual).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [1, 3] })
  })

  it('네 분기 모두는 분기 없음과 같아 보내지 않지만 화면에서는 읽을 수 있다', () => {
    // when: 네 분기가 든 URL을 조회 조건과 화면용 목록으로 읽는다
    const actual1 = listQueryFromParams(params('year=2026&quarter=1%2C2%2C3%2C4'))
    const actual2 = quartersOf(params('quarter=1%2C2%2C3%2C4'))
    // then: 분기 조건은 보내지 않고 화면용 목록은 1~4이다
    expect(actual1).toEqual({ offset: 0, limit: 20, year: 2026 })
    expect(actual2).toEqual([1, 2, 3, 4])
  })

  it('예전 단일 분기 주소는 그 분기 하나로 연다', () => {
    // when: quarter=4 URL을 읽는다
    const actual1 = quartersOf(params('quarter=4'))
    const actual2 = listQueryFromParams(params('quarter=4'))
    // then: 분기 4 하나로 읽히고 조회 조건에도 4가 담긴다
    expect(actual1).toEqual([4])
    expect(actual2).toEqual({ offset: 0, limit: 20, quarters: [4] })
  })

  it('형식이 틀린 항목은 버린다', () => {
    // when: 잘못된 항목이 섞인 분기 URL을 읽는다
    const actual1 = quartersOf(params('quarter=1%2C9%2Cx'))
    const actual2 = listQueryFromParams(params('quarter=9%2Cx'))
    // then: 잘못된 항목은 빠지고 1만 남으며 모두 틀리면 조건이 없다
    expect(actual1).toEqual([1])
    expect(actual2).toEqual({ offset: 0, limit: 20 })
  })

  it('여러 분기 중 하나가 월을 가지면 월을 보이게 유지한다', () => {
    // when: 유효한 월을 구한다
    const actual1 = effectiveMonth(params('quarter=1%2C3&month=8'))
    const actual2 = effectiveMonth(params('quarter=1%2C3&month=5'))
    const actual3 = effectiveMonth(params('quarter=1%2C2%2C3%2C4&month=5'))
    // then: 월 8은 보이고 월 5는 없으며 네 분기 모두면 월 5가 보인다
    expect(actual1).toBe(8)
    expect(actual2).toBeUndefined()
    expect(actual3).toBe(5)
  })

  it('여러 분기는 목록 조건으로 센다', () => {
    // when: 활성 조건·목록 조건을 판정한다
    const actual1 = hasActiveFilter(params('quarter=1%2C3'))
    const actual2 = hasListCondition(params('quarter=1%2C3'))
    // then: 여러 분기도 분기·목록 조건으로 센다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
  })
})
