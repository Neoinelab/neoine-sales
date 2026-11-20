import { afterEach, describe, expect, it, vi } from 'vitest'
import { CODE, serverDealDetail, serverDealRow } from '../../test/fixtures/serverDeal'
import type { DealInput, DealSortKey } from '../../shared/model/types'
import { createDealsHttp } from './deals'
import { createHttpGateway } from './index'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

const page = (items: unknown[], total = items.length) => ({ items, total, offset: 0, limit: 20 })
const query = (path: string) => new URL(path, 'http://localhost').searchParams

const input = (over: Partial<DealInput> = {}): DealInput => ({
  name: '한빛은행 ITDR',
  ownerId: USER_ID.kim,
  vendorId: 6,
  product: 'ITDR',
  users: 100,
  statusKey: 'prospecting',
  forecastKey: 'pipeline',
  revenueAmount: 500_000_000,
  revenueDate: '2027-01-31',
  customer: { contactId: null, company: '한빛은행', name: '정민수', title: '과장', email: 'min@hanbit.test', phone: null },
  partner: null,
  quote: { submitted: null, submittedDate: null },
  poc: { state: null, completedDate: null },
  procurement: '',
  bant: { budget: null, authority: null, need: null, timeline: null },
  ...over,
})

describe('deals.list owner over HTTP', () => {
  // 담당자 이름은 owner_name으로, 담당자 id는 owner_user_id로 보내고 서로 섞지 않는다
  // 테스트 코드: DL-143
  it('sends ownerName as owner_name and ownerId as owner_user_id without mixing them', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])), json(page([])))

    // when: 이름만, 그리고 id만 준 list를 호출한다
    await createDealsHttp().list({ ownerName: '김영' })
    await createDealsHttp().list({ ownerId: 3 })

    // then: 첫 쿼리는 owner_name만, 둘째 쿼리는 owner_user_id만 가진다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ owner_name: '김영' })
    expect(Object.fromEntries(query(calls[1]?.path ?? ''))).toEqual({ owner_user_id: '3' })
  })

  // 이름이 비어 있으면 owner_name을 보내지 않는다
  // 테스트 코드: DL-143
  it('does not send owner_name when the name is empty', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 빈 이름으로 list를 호출한다
    await createDealsHttp().list({ ownerName: '' })

    // then: 쿼리에 owner_name이 없다
    expect(query(calls[0]?.path ?? '').has('owner_name')).toBe(false)
  })
})

describe('deals.list month over HTTP (P6)', () => {
  // 월은 year 옆의 month 쿼리 키로 보낸다
  // 테스트 코드: DL-100
  it('sends month as a query key next to year', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: month와 year를 준 list를 호출한다
    await createDealsHttp().list({ year: 2026, month: 3 })

    // then: 쿼리에 year와 month가 있다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', month: '3' })
  })

  // month가 없으면 보내지 않는다
  // 테스트 코드: DL-100
  it('does not send month when it is not set', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: month 없이 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters: [4] })

    // then: 쿼리에 month가 없다
    expect(query(calls[0]?.path ?? '').has('month')).toBe(false)
  })
})

describe('deals.list quarters over HTTP (Quarter 다중 선택)', () => {
  // 고른 분기마다 quarter 키를 반복해 보낸다
  // 테스트 코드: DL-100
  it('repeats the quarter key once per chosen quarter', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 분기 여러 개로 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters: [1, 3] })

    // then: quarter 키가 분기 수만큼 반복된다
    expect(query(calls[0]?.path ?? '').getAll('quarter')).toEqual(['1', '3'])
    expect(query(calls[0]?.path ?? '').get('year')).toBe('2026')
  })

  // 분기 하나는 quarter 키 하나로 보낸다
  // 테스트 코드: DL-100
  it('sends a single quarter as one quarter key', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 분기 하나로 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters: [2] })

    // then: quarter 키가 하나다
    expect(query(calls[0]?.path ?? '').getAll('quarter')).toEqual(['2'])
  })

  // 분기가 비었거나 없으면 quarter 키를 보내지 않는다
  // 테스트 코드: DL-100
  it.each([[[]], [undefined]])('sends no quarter key for %j', async (quarters) => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 빈 분기 목록 또는 undefined로 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters })

    // then: quarter 키가 없다
    expect(query(calls[0]?.path ?? '').has('quarter')).toBe(false)
  })

  // 예전 단일 분기 필드는 보내지 않는다
  // 테스트 코드: DL-100
  it('never sends the old single-quarter query field', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 분기로 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters: [1, 3], month: undefined })

    // then: 예전 단일 필드가 없다
    expect(calls[0]?.path).not.toContain('quarters=')
  })
})

describe('deals.list forecast outcome over HTTP', () => {
  // forecastOutcome을 forecast_outcome으로 보낸다
  // 테스트 코드: DL-100
  it.each(['open', 'won', 'lost', 'not_lost'] as const)('sends forecastOutcome %s as forecast_outcome', async (outcome) => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: forecastOutcome으로 list를 호출한다
    await createDealsHttp().list({ year: 2026, forecastOutcome: outcome })

    // then: forecast_outcome 쿼리가 있다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', forecast_outcome: outcome })
  })

  // forecast_key와 함께 보내면 둘 다 쿼리에 있다
  // 테스트 코드: DL-100
  it('sends it next to forecast_key (the server ANDs them)', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: key와 outcome으로 list를 호출한다
    await createDealsHttp().list({ forecastKeys: ['commit'], forecastOutcome: 'open' })

    // then: 두 쿼리가 모두 있다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ forecast_key: 'commit', forecast_outcome: 'open' })
  })

  // forecast_outcome이 없으면 보내지 않는다
  // 테스트 코드: DL-100
  it('does not send forecast_outcome when it is not set', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: outcome 없이 list를 호출한다
    await createDealsHttp().list({ year: 2026, quarters: [4] })

    // then: forecast_outcome이 없다
    expect(query(calls[0]?.path ?? '').has('forecast_outcome')).toBe(false)
  })
})

describe('deals.list forecast keys over HTTP (Forecast 다중 조건)', () => {
  const sent = (path: string) => query(path).getAll('forecast_key')

  // key마다 forecast_key를 반복해 보낸다
  // 테스트 코드: DL-100
  it('repeats forecast_key once per key', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: key 여러 개로 list를 호출한다
    await createDealsHttp().list({ forecastKeys: ['best', 'pipeline'] })

    // then: forecast_key가 key 수만큼 반복된다
    expect(sent(calls[0]?.path ?? '')).toEqual(['best', 'pipeline'])
    expect(calls[0]?.path).toContain('forecast_key=best&forecast_key=pipeline')
  })

  // key 하나는 forecast_key 하나로 보낸다
  // 테스트 코드: DL-100
  it('sends a single key as one forecast_key', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: key 하나로 list를 호출한다
    await createDealsHttp().list({ forecastKeys: ['commit'] })

    // then: forecast_key가 하나다
    expect(sent(calls[0]?.path ?? '')).toEqual(['commit'])
  })

  // key가 비었거나 없으면 forecast_key를 보내지 않는다
  // 테스트 코드: DL-100
  it.each([[[]], [undefined]] as const)('sends no forecast_key for %j', async (keys) => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 빈 목록 또는 undefined로 list를 호출한다
    await createDealsHttp().list({ year: 2026, forecastKeys: keys })

    // then: forecast_key가 없다
    expect(query(calls[0]?.path ?? '').has('forecast_key')).toBe(false)
  })
})

describe('deals.list over HTTP', () => {
  // 조건이 없으면 쿼리 없이 GET /deals다
  // 테스트 코드: DL-100
  it('sends GET /deals without a query when nothing is set', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 조건 없이 list를 호출한다
    await createDealsHttp().list({})

    // then: 쿼리 없는 GET /deals가 나간다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals' })
  })

  // 모든 조건을 snake_case 쿼리 키로 바꾼다
  // 테스트 코드: DL-100
  it('maps every filter to its snake_case query key', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 모든 조건을 준 list를 호출한다
    await createDealsHttp().list({
      keyword: '한빛',
      ownerId: USER_ID.kim,
      vendorId: 6,
      product: 'ITDR',
      statusKey: 'prospecting',
      forecastKeys: ['pipeline'],
      year: 2026,
      quarters: [4],
      updatedFrom: '2026-10-01',
      updatedTo: '2026-12-31',
      mine: true,
      overdue: true,
      stale: true,
      nextActionStatus: 'closed',
      sort: 'revenueAmount',
      order: 'asc',
      offset: 20,
      limit: 50,
    })

    // then: 각 키가 snake_case 쿼리로 나간다
    expect(calls[0]?.method).toBe('GET')
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      keyword: '한빛',
      owner_user_id: String(USER_ID.kim),
      vendor_id: '6',
      product: 'ITDR',
      status_key: 'prospecting',
      forecast_key: 'pipeline',
      year: '2026',
      quarter: '4',
      updated_from: '2026-10-01',
      updated_to: '2026-12-31',
      mine: 'true',
      overdue: 'true',
      stale: 'true',
      next_action_status: 'closed',
      sort: 'revenue_amount',
      order: 'asc',
      offset: '20',
      limit: '50',
    })
  })

  // 설정한 최종 업데이트 날짜만 보내고 폐지된 Expected Close 기간은 보내지 않는다
  // 테스트 코드: DL-100
  it('sends only the updated dates that are set and never the retired revenue period', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])), json(page([])))

    await createDealsHttp().list({ updatedFrom: '2026-10-01' })
    await createDealsHttp().list({ updatedTo: '2026-10-15' })

    const first = query(calls[0]?.path ?? '')
    // when: 시작/끝 날짜를 각각 준 list를 호출한다
    const second = query(calls[1]?.path ?? '')
    // then: updated_from/updated_to만 나가고 revenue_*는 없다
    expect(Object.fromEntries(first)).toEqual({ updated_from: '2026-10-01' })
    expect(Object.fromEntries(second)).toEqual({ updated_to: '2026-10-15' })
    expect(first.has('revenue_from') || first.has('revenue_to')).toBe(false)
  })

  // Next Action 상태 필터를 서버 값으로 바꾼다(notDone → not_done)
  // 테스트 코드: DL-100
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['notDone', 'not_done'],
    ['closed', 'closed'],
  ] as const)('maps the Next Action status filter %s to %s', async (status, wire) => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: nextActionStatus로 list를 호출한다
    await createDealsHttp().list({ nextActionStatus: status })

    // then: next_action_status가 서버 값이다
    expect(query(calls[0]?.path ?? '').get('next_action_status')).toBe(wire)
  })

  // 상태 필터를 고르지 않으면 보내지 않는다
  // 테스트 코드: DL-100
  it('does not send a status filter when none is chosen', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 조건 없이 list를 호출한다
    await createDealsHttp().list({})

    // then: next_action_status가 없다
    expect(query(calls[0]?.path ?? '').has('next_action_status')).toBe(false)
  })

  // 정렬 키를 서버 값으로 바꾼다
  // 테스트 코드: DL-100
  it.each([
    ['name', 'name'],
    ['revenueAmount', 'revenue_amount'],
    ['revenueDate', 'revenue_date'],
    ['lastUpdatedAt', 'last_updated_at'],
    ['statusKey', 'status'],
    ['owner', 'owner'],
    ['customer', 'customer'],
    ['partner', 'partner'],
    ['vendor', 'vendor'],
    ['forecastKey', 'forecast'],
  ] as [DealSortKey, string][])('maps the sort key %s to %s', async (sort, server) => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 화면 정렬 키로 list를 호출한다
    await createDealsHttp().list({ sort })

    // then: sort가 서버 값이다
    expect(query(calls[0]?.path ?? '').get('sort')).toBe(server)
  })

  // bant_ 파라미터는 보내지 않는다
  // 테스트 코드: DL-100
  it('never sends a bant_ parameter', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 여러 조건으로 list를 호출한다
    await createDealsHttp().list({ ownerId: 3, vendorId: 12, mine: true, overdue: true, sort: 'owner', order: 'desc' })

    // then: bant_ 키가 없다
    expect([...query(calls[0]?.path ?? '').keys()].filter((key) => key.startsWith('bant_'))).toEqual([])
  })

  // overdue·stale은 켰을 때만 각각 보낸다
  // 테스트 코드: DL-100
  it('sends overdue and stale only when they are on, and each alone', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])), json(page([])), json(page([])), json(page([])))

    await createDealsHttp().list({ overdue: true })
    await createDealsHttp().list({ stale: true })
    await createDealsHttp().list({ overdue: false, stale: false })
    // when: 켠 조합마다 list를 호출한다
    await createDealsHttp().list({})

    // then: 켠 키만 나간다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ overdue: 'true' })
    expect(Object.fromEntries(query(calls[1]?.path ?? ''))).toEqual({ stale: 'true' })
    for (const index of [2, 3]) {
      const sent = query(calls[index]?.path ?? '')
      expect(sent.has('overdue') || sent.has('stale')).toBe(false)
    }
  })

  // mine이 false면 보내지 않고 offset 0은 요청하면 보낸다
  // 테스트 코드: DL-100
  it('does not send mine when it is false and sends offset 0 when asked', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ mine: false, offset: 0 })

    // when: mine=false, offset=0으로 list를 호출한다
    const sent = query(calls[0]?.path ?? '')
    // then: mine은 없고 offset=0이 있다
    expect(sent.has('mine')).toBe(false)
    expect(sent.get('offset')).toBe('0')
  })

  // 서버 페이지의 행과 total·offset·limit을 읽는다
  // 테스트 코드: DL-100
  it('reads the rows with total, offset and limit of the server page', async () => {
    // given: 서버 페이지 응답
    stubFetch(json({ items: [serverDealRow()], total: 41, offset: 20, limit: 20 }))

    // when: list를 호출한다
    const result = await createDealsHttp().list({ offset: 20 })

    // then: 행이 camelCase로 바뀌고 total·offset·limit이 그대로다
    expect(result).toMatchObject({ total: 41, offset: 20, limit: 20 })
    expect(result.items[0]).toMatchObject({ code: CODE, statusKey: 'prospecting', ownerId: USER_ID.kim })
  })

  // 연도 없는 분기는 분기만 보낸다
  // 테스트 코드: DL-100
  it('sends a quarter without a year as the quarter alone (the server reads it as this year)', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: 연도 없이 분기로 list를 호출한다
    await createDealsHttp().list({ quarters: [2] })

    // then: quarter만 나가고 year는 없다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ quarter: '2' })
  })

  // 예전 vendor 텍스트·solution_id 파라미터는 보내지 않는다
  // 테스트 코드: DL-100
  it('does not send the old vendor text, solution id and solution parameters', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ vendorId: 6, product: 'ITDR' })

    // when: Vendor/Product로 list를 호출한다
    const sent = query(calls[0]?.path ?? '')
    // then: 폐지된 키가 없다
    expect(sent.has('vendor')).toBe(false)
    expect(sent.has('solution_id')).toBe(false)
    expect(sent.has('solution')).toBe(false)
    expect(sent.get('vendor_id')).toBe('6')
    expect(sent.get('product')).toBe('ITDR')
  })

  // 빈 Product는 빼고 텍스트는 공백·한글 그대로 보낸다
  // 테스트 코드: DL-100
  it('omits an empty product filter and sends the text as it is, including spaces and non-ASCII', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])), json(page([])))

    await createDealsHttp().list({ product: '' })
    // when: 빈 Product와 텍스트 Product로 list를 호출한다
    await createDealsHttp().list({ product: '통합 ITDR' })

    // then: 빈 값은 빠지고 텍스트는 원문 그대로다
    expect(query(calls[0]?.path ?? '').has('product')).toBe(false)
    expect(query(calls[1]?.path ?? '').get('product')).toBe('통합 ITDR')
  })

  // id 조건은 정수 쿼리 값으로 보낸다
  // 테스트 코드: DL-100
  it('sends id filters as integer query values', async () => {
    // given: 서버 응답을 흉내 낸 fetch
    const { calls } = stubFetch(json(page([])))

    // when: ownerId·vendorId로 list를 호출한다
    await createDealsHttp().list({ ownerId: 3, vendorId: 9007199254740991 })

    // then: owner_user_id·vendor_id가 정수 문자열이다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      owner_user_id: '3',
      vendor_id: '9007199254740991',
    })
  })
})

describe('deals.get / impact over HTTP', () => {
  // 상세는 GET /deals/{code}를 읽어 파트너 이력이 든 상세로 바꾼다.
  // 테스트 코드: DD-116
  it('get reads GET /deals/{code} as a detail with the partner history', async () => {
    // given: 서버 상세 응답
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: 게이트웨이로 Deal을 읽는다
    const detail = await createDealsHttp().get(CODE)

    // then: GET 경로가 맞고 상세에 code와 파트너 이력이 있다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}` })
    expect(detail).toMatchObject({ code: CODE, partnerHistory: [] })
  })

  // 없는 Deal 상세는 서버의 404 문구를 보인다.
  // 테스트 코드: DD-116
  it('get shows the 404 message', async () => {
    // given: 404 응답
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 게이트웨이로 Deal을 읽는다 → status 404, kind not-found, 서버 문구가 오류에 담긴다
    await expect(createDealsHttp().get(CODE)).rejects.toMatchObject({ status: 404, kind: 'not-found', message: 'Deal을 찾을 수 없습니다.' })
  })

  // 삭제 영향은 다섯 건수를 camelCase로 바꿔 돌려준다.
  // 테스트 코드: DD-116
  it('impact reads GET /deals/{code}/deletion-impact in camelCase with five counts', async () => {
    // given: 다섯 건수가 든 서버 응답
    const { calls } = stubFetch(json({ history_count: 5, action_count: 3, attachment_count: 2, license_contract_count: 4, comment_count: 6 }))

    // when: 게이트웨이로 삭제 영향을 읽는다
    const impact = await createDealsHttp().impact(CODE)

    // then: GET 경로가 맞고 historyCount 등 다섯 값이 camelCase다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/deletion-impact` })
    expect(impact).toStrictEqual({ historyCount: 5, actionCount: 3, attachmentCount: 2, licenseContractCount: 4, commentCount: 6 })
  })

  // 없는 Deal의 삭제 영향은 404 오류다.
  // 테스트 코드: DD-116
  it('impact shows the 404 of an unknown deal', async () => {
    // given: 404 응답
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 삭제 영향을 읽는다 → status 404 오류다
    await expect(createDealsHttp().impact(CODE)).rejects.toMatchObject({ status: 404 })
  })

  // facets 호출이 사라졌다.
  it('has no facets call any more', () => {
    // when: Deal HTTP 어댑터를 만든다
    const result = 'facets' in createDealsHttp()
    // then: facets 메서드가 없다
    expect(result).toBe(false)
  })
})

describe('deals.create over HTTP', () => {
  // 등록은 snake_case 본문(BANT 선택 객체 포함)으로 POST하고 201 상세를 읽는다.
  // 테스트 코드: DE-111
  it('posts the snake_case body and reads the 201 detail', async () => {
    // given: 서버가 201 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail(), 201, { Location: `/api/v1/deals/${CODE}` }))

    // when: 파트너·견적·POC·BANT가 든 입력으로 create를 호출한다.
    const detail = await createDealsHttp().create(
      input({
        partner: { contactId: 11, company: '코어테크', name: '이파트', title: '', email: null, phone: '02-000-0000' },
        quote: { submitted: 'YES', submittedDate: '2026-10-05' },
        poc: { state: 'ING', completedDate: null },
        bant: { budget: { id: 1 }, authority: null, need: null, timeline: { name: '내후년 구매' } },
        procurement: '입찰',
      }),
    )

    // then: POST /api/v1/deals 본문이 snake_case 필드와 BANT 선택 객체이고 상세의 code를 읽는다.
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/deals' })
    expect(calls[0]?.body).toEqual({
      name: '한빛은행 ITDR',
      owner_user_id: USER_ID.kim,
      vendor_id: 6,
      product: 'ITDR',
      users: 100,
      status_key: 'prospecting',
      forecast_key: 'pipeline',
      revenue_amount: 500_000_000,
      revenue_date: '2027-01-31',
      customer: { contact_id: null, company: '한빛은행', name: '정민수', title: '과장', email: 'min@hanbit.test', phone: null },
      partner: { contact_id: 11, company: '코어테크', name: '이파트', title: null, email: null, phone: '02-000-0000' },
      quote: { submitted: 'YES', submitted_date: '2026-10-05' },
      poc: { state: 'ING', completed_date: null },
      procurement: '입찰',
      bant: { budget: { id: 1 }, authority: null, need: null, timeline: { name: '내후년 구매' } },
    })
    expect(detail.code).toBe(CODE)
  })

  // 빈 직급과 없는 파트너는 null로 보낸다.
  // 테스트 코드: DE-111
  it('sends an empty title as null and no partner as null', async () => {
    // given: 서버가 201 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail(), 201))

    await createDealsHttp().create(input({ customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: null, phone: null } }))

    // when: 직급이 ''이고 파트너가 없는 입력으로 create를 호출한다.
    const body = calls[0]?.body as { customer: { title: unknown }; partner: unknown }
    // then: 고객 직급과 partner가 null이다.
    expect(body.customer.title).toBeNull()
    expect(body.partner).toBeNull()
  })

  // 빈 Expected Close는 null로 보내 서버 문구에 맡긴다.
  // 테스트 코드: DE-111
  it('sends an empty Expected Close as null so the server answers its own message', async () => {
    // given: 서버가 201 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail(), 201))

    // when: revenueDate ''로 create를 호출한다.
    await createDealsHttp().create(input({ revenueDate: '' }))

    // then: revenue_date가 null이다.
    expect((calls[0]?.body as { revenue_date: unknown }).revenue_date).toBeNull()
  })

  // 등록 오류는 상태별 종류와 서버 문구로 reject한다.
  it.each([
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
    [404, 'not-found', '연락처를 찾을 수 없습니다.', 'not-found'],
    [409, 'already-exists', '이미 등록된 연락처입니다.', 'conflict'],
    [422, 'invalid-value', 'Deal Name을 입력하세요.', 'validation'],
  ])('shows the %s error with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 오류 응답을 준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: Deal을 등록한다 → 상태에 맞는 종류의 오류와 서버 문구로 reject한다
    await expect(createDealsHttp().create(input())).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('deals.update over HTTP', () => {
  // 수정은 준 필드만 PATCH로 보낸다.
  // 테스트 코드: DE-112
  it('patches only the fields that are given', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: 일부 필드만 담아 update를 호출한다.
    await createDealsHttp().update(CODE, { name: '새 이름', ownerId: USER_ID.park, statusKey: 'qualified', revenueAmount: 700_000_000, revenueDate: '2027-02-28' })

    // then: 본문에 준 필드만 있다.
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: `/api/v1/deals/${CODE}` })
    expect(calls[0]?.body).toEqual({
      name: '새 이름',
      owner_user_id: USER_ID.park,
      status_key: 'qualified',
      revenue_amount: 700_000_000,
      revenue_date: '2027-02-28',
    })
  })

  // 수정에서도 빈 Expected Close는 null로 보낸다.
  // 테스트 코드: DE-112
  it('sends an empty Expected Close as null so the server refuses it with its own message', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: revenueDate ''로 update를 호출한다.
    await createDealsHttp().update(CODE, { revenueDate: '' })

    // then: revenue_date가 null이다.
    expect(calls[0]?.body).toEqual({ revenue_date: null })
  })

  // Vendor만 바꾸면 vendor_id만 보낸다.
  // 테스트 코드: DE-112
  it('sends only vendor_id when the vendor changes (the product is independent)', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: vendorId만 담아 update를 호출한다.
    await createDealsHttp().update(CODE, { vendorId: 3 })

    // then: 본문에 vendor_id만 있다.
    expect(calls[0]?.body).toEqual({ vendor_id: 3 })
  })

  // Product만 바꾸면 product만 보낸다.
  // 테스트 코드: DE-112
  it('sends only the product text when the product changes', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: product만 담아 update를 호출한다.
    await createDealsHttp().update(CODE, { product: 'MFA' })

    // then: 본문에 product만 있다.
    expect(calls[0]?.body).toEqual({ product: 'MFA' })
  })

  // 빈 Product는 빈 문자열로 보내고 주지 않은 Vendor 필드는 생략한다.
  // 테스트 코드: DE-112
  it('sends an empty product as an empty string and omits vendor fields that are not given', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()), json(serverDealDetail()))

    // when: 빈 product과 name만 담아 update를 각각 호출한다.
    await createDealsHttp().update(CODE, { product: '' })
    await createDealsHttp().update(CODE, { name: 'x' })

    // then: 첫 본문은 product ''만, 둘째는 name만 있고 vendor_id는 없다.
    expect(calls[0]?.body).toEqual({ product: '' })
    expect(calls[1]?.body).toEqual({ name: 'x' })
  })

  // partner null은 본문에 유지해 서버가 파트너를 제거하게 한다.
  // 테스트 코드: DE-112
  it('keeps partner null in the body so that the server removes the partner', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: partner null로 update를 호출한다.
    await createDealsHttp().update(CODE, { partner: null })

    // then: 본문에 partner: null이 있다.
    expect(calls[0]?.body).toEqual({ partner: null })
  })

  // patch의 중첩 필드(quote, poc 등)는 하위 키로 변환한다.
  // 테스트 코드: DE-112
  it('maps the nested fields of a patch', async () => {
    // given: 서버가 200 상세를 돌려준다.
    const { calls } = stubFetch(json(serverDealDetail()))

    // when: quote·poc를 담아 update를 호출한다.
    await createDealsHttp().update(CODE, {
      customer: { contactId: 1, company: '한빛은행', name: '정민수', title: '', email: null, phone: null },
      quote: { submitted: 'NO', submittedDate: null },
      poc: { state: 'YES', completedDate: '2026-10-10' },
      bant: { budget: null, authority: { id: 2 }, need: { name: '신규 요건' }, timeline: null },
      users: 5,
      procurement: '',
    })

    // then: 하위 snake_case 키로 변환된다.
    expect(calls[0]?.body).toEqual({
      customer: { contact_id: 1, company: '한빛은행', name: '정민수', title: null, email: null, phone: null },
      quote: { submitted: 'NO', submitted_date: null },
      poc: { state: 'YES', completed_date: '2026-10-10' },
      bant: { budget: null, authority: { id: 2 }, need: { name: '신규 요건' }, timeline: null },
      users: 5,
      procurement: '',
    })
  })

  // 수정 오류는 상태별 종류와 서버 문구로 reject한다.
  it.each([
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [409, 'already-exists', 'conflict'],
    [422, 'invalid-value', 'validation'],
  ])('shows the %s error', async (status, serverKind, kind) => {
    // given: 서버가 오류 응답을 준다
    stubFetch(problem(status, serverKind, '서버 문구'))

    // when·then: Deal을 수정한다 → 상태에 맞는 종류의 오류와 서버 문구로 reject한다
    await expect(createDealsHttp().update(CODE, { name: 'x' })).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })
})

describe('deals.applyChange over HTTP', () => {
  const answer = (over: Record<string, unknown> = {}) => ({ deal: serverDealDetail(), co_changed: [], notice: null, ...over })

  // 단일 변경 네 필드를 snake_case 본문으로 POST한다.
  // 테스트 코드: DD-116
  it.each([
    [{ field: 'statusKey', value: 'qualified' }, { field: 'status_key', value: 'qualified' }],
    [{ field: 'forecastKey', value: 'commit' }, { field: 'forecast_key', value: 'commit' }],
    [{ field: 'revenueAmount', value: 900_000_000 }, { field: 'revenue_amount', value: 900_000_000 }],
    [{ field: 'revenueDate', value: '2027-03-31' }, { field: 'revenue_date', value: '2027-03-31' }],
  ] as const)('posts %j as %j', async (change, server) => {
    // given: Status·Forecast·금액·Expected Close 각각의 변경
    const { calls } = stubFetch(json(answer()))

    // when: 게이트웨이로 변경을 보낸다
    await createDealsHttp().applyChange(CODE, { change })

    // then: POST /deals/{code}/changes에 field가 snake_case인 change만 담긴다
    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/changes` })
    expect(calls[0]?.body).toEqual({ change: server })
  })

  // resolution 답을 snake_case로 보낸다.
  // 테스트 코드: DD-116
  it('maps the resolution answers to snake_case', async () => {
    // given: 네 답이 든 종결 변경
    const { calls } = stubFetch(json(answer()))

    // when: 게이트웨이로 변경을 보낸다
    await createDealsHttp().applyChange(CODE, {
      change: { field: 'statusKey', value: 'contract_completed' },
      resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-14', statusKey: 'qualified', forecastKey: 'commit' },
    })

    // then: 본문 resolution이 revenue_amount 등 snake_case다
    expect(calls[0]?.body).toEqual({
      change: { field: 'status_key', value: 'contract_completed' },
      resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-14', status_key: 'qualified', forecast_key: 'commit' },
    })
  })

  // 응답의 co_changed와 notice를 coChanged·notice로 바꾼다.
  // 테스트 코드: DD-116
  it('maps co_changed and the notice of the response', async () => {
    // given: 함께 바뀐 값이 든 서버 응답
    stubFetch(
      json(
        answer({
          deal: serverDealDetail({ status_key: 'contract_completed', forecast_key: 'won' }),
          co_changed: [{ field: 'forecast_key', from: 'commit', to: 'won' }],
          notice: "Forecast가 'Won'으로 함께 변경되었습니다.",
        }),
      ),
    )

    // when: 게이트웨이로 변경을 보낸다
    const result = await createDealsHttp().applyChange(CODE, { change: { field: 'statusKey', value: 'contract_completed' } })

    // then: coChanged가 camelCase 필드이고 notice와 변경된 Deal이 맞다
    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'commit', to: 'won' }])
    expect(result.notice).toBe("Forecast가 'Won'으로 함께 변경되었습니다.")
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
  })

  // 독립 변경은 빈 coChanged와 null notice를 돌려준다.
  // 테스트 코드: DD-116
  it('answers an empty coChanged and a null notice for an independent change', async () => {
    // given: 함께 바뀐 값이 없는 서버 응답
    stubFetch(json(answer()))

    // when: 게이트웨이로 변경을 보낸다
    const result = await createDealsHttp().applyChange(CODE, { change: { field: 'forecastKey', value: 'commit' } })

    // then: coChanged가 빈 배열이고 notice가 null이다
    expect(result).toMatchObject({ coChanged: [], notice: null })
  })

  // 매출을 요구하는 422 문구를 그대로 보인다.
  // 테스트 코드: DD-116
  it('shows the 422 message that asks for the revenue', async () => {
    // given: 매출 필요 422 응답
    stubFetch(problem(422, 'invalid-value', 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'))

    // when·then: 게이트웨이로 계약완료 변경을 보낸다 → status 422와 서버 문구가 오류에 담긴다
    await expect(createDealsHttp().applyChange(CODE, { change: { field: 'statusKey', value: 'contract_completed' } })).rejects.toMatchObject({
      status: 422,
      message: 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.',
    })
  })

  // 단일 변경의 403·404 오류를 status로 보인다.
  // 테스트 코드: DD-116
  it.each([
    [403, 'forbidden'],
    [404, 'not-found'],
  ])('shows the %s error', async (status, serverKind) => {
    // given: 403 또는 404 응답
    stubFetch(problem(status, serverKind, '서버 문구'))

    // when·then: 게이트웨이로 변경을 보낸다 → 해당 status의 오류다
    await expect(createDealsHttp().applyChange(CODE, { change: { field: 'forecastKey', value: 'commit' } })).rejects.toMatchObject({ status })
  })
})

describe('deals.remove over HTTP', () => {
  // 삭제는 confirm_code 쿼리로 DELETE하고 204를 성공으로 받는다.
  // 테스트 코드: DD-116
  it('deletes with the confirm code in the query and accepts the 204', async () => {
    // given: 204 응답
    const { calls } = stubFetch(noContent())

    // when: 게이트웨이로 삭제한다
    const result = await createDealsHttp().remove(CODE, CODE)

    // then: DELETE 경로에 confirm_code가 있고 결과는 undefined다
    expect(result).toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/deals/${CODE}?confirm_code=${CODE}` })
  })

  // 입력한 확인 code는 달라도 그대로 보내고 서버의 422 문구를 보인다.
  // 테스트 코드: DD-116
  it('sends the typed confirm code as it is, even when it differs', async () => {
    // given: 불일치 422 응답
    const { calls } = stubFetch(problem(422, 'invalid-value', 'Deal code가 일치하지 않습니다.'))

    // when·then: 틀린 확인 code로 삭제한다 → 쿼리에 입력 그대로의 값이 있고 오류가 'Deal code가 일치하지 않습니다.'다
    await expect(createDealsHttp().remove(CODE, 'wrong')).rejects.toMatchObject({ status: 422, message: 'Deal code가 일치하지 않습니다.' })

    expect(query(calls[0]?.path ?? '').get('confirm_code')).toBe('wrong')
  })

  // 삭제의 403·404·409 오류를 kind와 서버 문구로 보인다.
  // 테스트 코드: DD-116
  it.each([
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [409, 'invalid-state', 'conflict'],
  ])('shows the %s error', async (status, serverKind, kind) => {
    // given: 403, 404, 409 응답
    stubFetch(problem(status, serverKind, '서버 문구'))

    // when·then: 게이트웨이로 삭제한다 → status·kind·서버 문구가 오류에 담긴다
    await expect(createDealsHttp().remove(CODE, CODE)).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })
})

describe('http gateway wiring', () => {
  // 게이트웨이의 Deal 어댑터는 501 자리표시가 아니라 실제 서버를 호출한다.
  it('uses the real deals adapter instead of the 501 placeholder', async () => {
    // given: 서버가 빈 목록을 준다
    const { calls } = stubFetch(json(page([])))
    // when: 게이트웨이로 Deal 목록을 읽는다
    await createHttpGateway().deals.list({})
    // then: GET /api/v1/deals를 부른다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals' })
  })

  // 게이트웨이의 이력 어댑터는 501 자리표시가 아니라 실제 서버를 호출한다.
  it('uses the real history adapter instead of the 501 placeholder', async () => {
    // given: 서버가 빈 이력을 준다
    const { calls } = stubFetch(json([]))
    // when: 게이트웨이로 이력을 읽는다
    await createHttpGateway().history.list(CODE, {})
    // then: GET /api/v1/deals/{code}/history를 부른다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/history` })
  })

  // 게이트웨이의 첨부 어댑터는 501 자리표시가 아니라 실제 서버를 호출한다.
  it('uses the real attachments adapter instead of the 501 placeholder', async () => {
    // given: 서버가 빈 첨부 목록을 준다
    const { calls } = stubFetch(json({ items: [] }))
    // when: 게이트웨이로 첨부 목록을 읽는다
    const items = await createHttpGateway().attachments.list(CODE)
    // then: 빈 목록을 받고 GET /api/v1/deals/{code}/attachments를 부른다
    expect(items).toEqual([])
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/attachments` })
  })

  // 게이트웨이의 Forecast 어댑터는 501 자리표시가 아니라 실제 서버를 호출한다.
  it('uses the real forecast adapter instead of the 501 placeholder', async () => {
    // given: 서버가 빈 객체를 준다(응답 해석은 forecast.test.ts가 검증)
    // 응답 해석은 forecast.test.ts가 검증한다. 여기서는 서버를 호출하는지만 본다.
    const { calls } = stubFetch(json({}))
    // when: 게이트웨이로 Forecast 요약을 읽는다
    await createHttpGateway().forecast.summary({ year: 2026 }).catch(() => undefined)
    // then: GET /api/v1/forecast/summary?year=2026을 부른다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/summary?year=2026' })
  })
})

describe('deals.updatedPeriods over HTTP', () => {
  // 기간 프리셋을 GET /deals/updated-periods로 읽어 today와 key·from·to를 유지한다
  // 테스트 코드: DL-100
  it('requests GET /deals/updated-periods and keeps today, key, from and to', async () => {
    // given: 서버 프리셋 응답
    const body = {
      today: '2026-10-21',
      periods: [
        { key: '2w', from: '2026-10-07', to: '2026-10-21' },
        { key: '1m', from: '2026-09-21', to: '2026-10-21' },
        { key: '2m', from: '2026-08-21', to: '2026-10-21' },
        { key: '3m', from: '2026-07-21', to: '2026-10-21' },
        { key: '6m', from: '2026-04-21', to: '2026-10-21' },
      ],
      upcoming: [
        { key: '1m', from: '2026-10-21', to: '2026-11-21' },
        { key: '2m', from: '2026-10-21', to: '2026-12-21' },
      ],
    }
    const { calls } = stubFetch(json(body))

    // when: updatedPeriods를 호출한다
    const result = await createDealsHttp().updatedPeriods()

    // then: 경로가 맞고 결과가 응답과 같다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals/updated-periods' })
    expect(result).toEqual(body)
  })

  // 알 수 없는 key는 버리고 upcoming을 옮긴다
  // 테스트 코드: DL-100
  it('updatedPeriods maps upcoming and drops unknown keys', async () => {
    // given: 모르는 key가 섞인 응답
    const body = {
      today: '2026-10-21',
      periods: [{ key: '2w', from: '2026-10-07', to: '2026-10-21' }],
      upcoming: [
        { key: '1m', from: '2026-10-21', to: '2026-11-21' },
        { key: '9m', from: '2026-10-21', to: '2027-07-21' },
        { key: '2m', from: '2026-10-21', to: '2026-12-21' },
      ],
    }
    stubFetch(json(body))

    // when: updatedPeriods를 호출한다
    const result = await createDealsHttp().updatedPeriods()

    // then: 아는 key만 남는다
    expect(result.upcoming).toEqual([
      { key: '1m', from: '2026-10-21', to: '2026-11-21' },
      { key: '2m', from: '2026-10-21', to: '2026-12-21' },
    ])
  })
})

describe('deals.years over HTTP', () => {
  // earliest_year를 earliestYear로 바꾼다
  // 테스트 코드: DL-100
  it('maps GET /deals/years earliest_year to earliestYear', async () => {
    // given: 연도 기준 응답
    const { calls } = stubFetch(json({ earliest_year: 2019 }))

    // when: years를 호출한다
    const result = await createDealsHttp().years()

    // then: earliestYear가 값이다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals/years' })
    expect(result).toEqual({ earliestYear: 2019 })
  })

  // Deal이 없으면 null을 유지한다
  // 테스트 코드: DL-100
  it('keeps null when there is no deal', async () => {
    // given: earliest_year가 null인 응답
    stubFetch(json({ earliest_year: null }))

    // when: years를 호출한다
    const result = await createDealsHttp().years()

    // then: earliestYear가 null이다
    expect(result).toEqual({ earliestYear: null })
  })

  // 허용되지 않으면 서버 문구를 보인다
  // 테스트 코드: DL-100
  it('shows the server message when the request is not allowed', async () => {
    // given: 401 응답
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: years를 호출한다 → 서버 문구가 오류 메시지이다
    await expect(createDealsHttp().years()).rejects.toMatchObject({ status: 401, message: '로그인이 필요합니다.' })
  })
})

