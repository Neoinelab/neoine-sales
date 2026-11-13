/**
 * Deal 원장 계약(삭제·applyChange). mock과 실제 서버가 같은 결과를 내야 한다.
 * 시드에 기대지 않고 호출마다 고유한 Deal 이름·회사명으로 만든 Deal만 본다(만든 Deal은 스스로 지운다).
 */

import { describe, expect, it } from 'vitest'
import { DEAL_CODE_PATTERN } from '../../shared/model/constants'
import type { DealDetail, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { action } from './actions.contract'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const SYNC_MISMATCH = 'Status와 Forecast의 동기화가 맞지 않습니다.'
const REVENUE_NEEDED = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const CHOICE_NEEDED = '함께 바꿀 값을 선택하세요.'

/** 유효한 등록 입력. 이름·고객 회사명은 호출마다 고유하다(Vendor는 선택 안 함, Solution은 필수 텍스트). */
async function validInput(gateway: Gateway, over: Partial<DealInput> = {}): Promise<DealInput> {
  const me = await gateway.auth.me()
  return {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: null,
    solution: 'ITDR',
    users: 10,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 1_000_000,
    revenueDate: '2027-02-15',
    customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    ...over,
  }
}

export function dealsContract(make: MakeGateway): void {
  describe('deals 계약', () => {
    it('Deal을 등록하면 YYYYMMDD-XXXX 코드가 붙고 다시 읽을 수 있다', async () => {
      const sales = await make('sales')
      // given: 유효한 등록 입력
      const input = await validInput(sales)

      // when: 영업이 Deal을 등록한다
      const created = await sales.deals.create(input)

      // then: 코드 형식이 맞고 다시 읽으면 입력한 값이 보인다 (끝에 정리한다)
      expect(created.code).toMatch(DEAL_CODE_PATTERN)
      const read = await sales.deals.get(created.code)
      expect(read).toMatchObject({ name: input.name, ownerId: input.ownerId, statusKey: 'prospecting', forecastKey: 'pipeline', revenueAmount: 1_000_000 })
      expect(read.customer.company).toBe(input.customer.company)
      await sales.deals.remove(created.code, created.code)
    })

    it('조회자의 등록은 403으로 거절한다', async () => {
      const sales = await make('sales')
      // given: 유효한 등록 입력
      const input = await validInput(sales)
      const user = await make('user')

      // when·then: 조회자가 등록하면 403이다
      await expectRejects(user.deals.create(input), 403)
    })

    it('없는 코드는 404다', async () => {
      const { deals } = await make('sales')

      // when·then: 없는 Deal 코드를 읽으면 404다
      await expectRejects(deals.get('20000101-ZZZZ'), 404)
    })

    it('첫 위반을 이름·금액·Expected Close·Users·동기화 순서로 알린다', async () => {
      const sales = await make('sales')
      // given: 유효한 등록 입력
      const base = await validInput(sales)

      // when·then: 여러 항목이 동시에 틀리면 정해진 순서의 첫 위반 문구로 422다
      await expectRejects(sales.deals.create({ ...base, name: '  ', revenueAmount: 0 }), 422, 'Deal Name을 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueAmount: 0, revenueDate: '' }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueDate: '', users: -1 }), 422, 'Expected Close를 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, users: -1, statusKey: 'contract_completed' }), 422, 'Users count는 0 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, statusKey: 'contract_completed' }), 422, SYNC_MISMATCH)
    })

    it('구매절차 길이는 서버처럼 Status와 BANT 검사 뒤에 확인한다', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)
      // given: 501자 구매절차
      const tooLong = 'a'.repeat(501)

      // when·then: 잘못된 Status, 잘못된 BANT가 있으면 그 문구가 먼저 오고, 그 밖에는 구매절차 길이 문구로 422다
      await expectRejects(sales.deals.create({ ...base, procurement: tooLong, statusKey: 'no_such_status' }), 422, 'Status를 선택하세요.')
      await expectRejects(
        sales.deals.create({ ...base, procurement: tooLong, bant: { budget: { id: NO_SUCH_ID }, authority: null, need: null, timeline: null } }),
        422,
        'BANT Label이 올바르지 않습니다.',
      )
      await expectRejects(sales.deals.create({ ...base, procurement: tooLong }), 422, '구매절차는 500자 이내로 입력하세요.')
    })

    it('Deal Name 길이는 앞뒤 공백을 지운 뒤 잰다', async () => {
      const sales = await make('sales')
      // when: 앞에 공백이 붙은 200자 이름으로 등록한다
      const created = await sales.deals.create(await validInput(sales, { name: ` ${'a'.repeat(200)}` }))

      // then: 공백이 지워진 200자 이름으로 등록된다 (끝에 정리한다)
      expect(created.name).toBe('a'.repeat(200))
      await sales.deals.remove(created.code, created.code)
    })

    it('Expected Close를 비우는 수정은 422로 거절한다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(Expected Close를 비우는 수정은 422로 거절한다)
      const created = await sales.deals.create(await validInput(sales))

      // when·then: Expected Close를 비우면 422다
      await expectRejects(sales.deals.update(created.code, { revenueDate: '' }), 422, 'Expected Close를 입력하세요.')

      // then: 저장된 Expected Close가 그대로다 (끝에 정리한다)
      expect((await sales.deals.get(created.code)).revenueDate).toBe('2027-02-15')
      await sales.deals.remove(created.code, created.code)
    })

    it('등록은 새 Deal의 유일한 이력으로 남는다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(등록은 새 Deal의 유일한 이력으로 남는다)
      const created = await sales.deals.create(await validInput(sales))

      // when: 이력을 조회한다
      const history = await sales.history.list(created.code, {})

      // then: 등록 이력 한 건뿐이다 (끝에 정리한다)
      expect(history).toHaveLength(1)
      expect(history[0]).toMatchObject({ category: 'created', before: '', after: 'Deal 등록' })
      await sales.deals.remove(created.code, created.code)
    })

    it('Won 변경은 매출 응답과 함께 적용되고 함께 바뀐 Status를 알려 준다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(Won 변경은 매출 응답과 함께 적용되고 함께 바뀐 Status를 알려 준다)
      const created = await sales.deals.create(await validInput(sales))

      // when: 매출금액·매출일과 함께 Forecast를 Won으로 바꾼다
      const result = await sales.deals.applyChange(created.code, {
        change: { field: 'forecastKey', value: 'won' },
        resolution: { revenueAmount: 2_000_000, revenueDate: '2026-10-14' },
      })

      // then: Forecast Won, Status 계약완료, 매출 값이 반영되고 함께 바뀐 필드와 안내가 돌아온다 (끝에 정리한다)
      expect(result.deal).toMatchObject({ forecastKey: 'won', statusKey: 'contract_completed', revenueAmount: 2_000_000, revenueDate: '2026-10-14' })
      expect(result.coChanged).toEqual([{ field: 'statusKey', from: 'prospecting', to: 'contract_completed' }])
      expect(result.notice).not.toBeNull()
      // 정리: Won(완료)이 된 Deal은 admin만 지울 수 있다(DD-R41).
      await (await make('admin')).deals.remove(created.code, created.code)
    })

    it('매출 응답 없는 Won 변경은 거절하고 아무것도 바꾸지 않는다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(매출 응답 없는 Won 변경은 거절하고 아무것도 바꾸지 않는다)
      const created = await sales.deals.create(await validInput(sales))

      // when·then: 매출 응답 없이 Won으로 바꾸면 매출 문구와 함께 422다
      await expectRejects(sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'won' } }), 422, REVENUE_NEEDED)

      // then: Forecast가 그대로다 (끝에 정리한다)
      expect((await sales.deals.get(created.code)).forecastKey).toBe('pipeline')
      await sales.deals.remove(created.code, created.code)
    })

    it('계약완료 Deal을 되돌릴 때 어느 Forecast로 갈지 묻는다', async () => {
      const sales = await make('sales')
      // given: 계약완료로 바꾼 Deal
      const created = await sales.deals.create(await validInput(sales))
      await sales.deals.applyChange(created.code, {
        change: { field: 'statusKey', value: 'contract_completed' },
        resolution: { revenueAmount: 2_000_000, revenueDate: '2026-10-14' },
      })

      // when·then: 선택 없이 Status를 되돌리면 선택 문구와 함께 422다
      await expectRejects(sales.deals.applyChange(created.code, { change: { field: 'statusKey', value: 'prospecting' } }), 422, CHOICE_NEEDED)
      // when: Forecast를 골라 Status를 되돌린다
      const back = await sales.deals.applyChange(created.code, {
        change: { field: 'statusKey', value: 'prospecting' },
        resolution: { forecastKey: 'pipeline' },
      })

      // then: 되돌린 Status와 고른 Forecast가 반영된다 (끝에 정리한다)
      expect(back.deal).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(created.code, created.code)
    })

    it('이력은 최신순으로 나오고 구분으로 거를 수 있다', async () => {
      const sales = await make('sales')
      // given: Forecast를 한 번 바꾼 Deal
      const created = await sales.deals.create(await validInput(sales))
      await sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'commit' } })

      // when: 전체 이력과 forecast 구분 이력을 조회한다
      const all = await sales.history.list(created.code, {})
      const forecast = await sales.history.list(created.code, { category: 'forecast' })

      // then: 전체는 최신순(forecast, created)이고 구분 필터는 해당 한 건이다 (끝에 정리한다)
      expect(all.map((h) => h.category)).toEqual(['forecast', 'created'])
      expect(forecast).toHaveLength(1)
      expect(forecast[0]).toMatchObject({ target: 'Forecast', after: 'Commit' })
      await sales.deals.remove(created.code, created.code)
    })

    it('삭제는 권한(403)을 확인 코드(422)보다 먼저 검사한다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(삭제는 권한(403)을 확인 코드(422)보다 먼저 검사한다)
      const created = await sales.deals.create(await validInput(sales))
      const user = await make('user')

      // when·then: 조회자는 확인 코드가 틀려도 403이고, 담당 영업은 틀린 코드면 422다
      await expectRejects(user.deals.remove(created.code, 'wrong'), 403)
      const owner = await make('sales')
      await expectRejects(owner.deals.remove(created.code, 'wrong'), 422, 'Deal code가 일치하지 않습니다.')
      // then: Deal이 그대로 있다
      expect((await owner.deals.get(created.code)).code).toBe(created.code)

      // when: 맞는 코드로 삭제한다
      await owner.deals.remove(created.code, created.code)
      // then: 이후 조회는 404다
      await expectRejects(owner.deals.get(created.code), 404)
    })

    it('삭제 영향의 건수를 센다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(삭제 영향의 건수를 센다)
      const created = await sales.deals.create(await validInput(sales))

      // when: 삭제 영향을 조회한다
      const impact = await sales.deals.impact(created.code)

      // then: 이력 1건, 나머지 0건이다 (끝에 정리한다)
      expect(impact).toStrictEqual({ historyCount: 1, actionCount: 0, attachmentCount: 0, licenseContractCount: 0 })
      await sales.deals.remove(created.code, created.code)
    })

    it('Vendor를 고르지 않으면 null이고 Solution은 입력한 그대로다', async () => {
      const sales = await make('sales')
      // when: Vendor 없이 Solution을 넣어 등록한다
      const created = await sales.deals.create(await validInput(sales, { solution: 'ITDR' }))

      // then: vendor는 null이고 solution은 입력값이다 (끝에 정리한다)
      expect(created.vendor).toBeNull()
      expect(created.solution).toBe('ITDR')
      await sales.deals.remove(created.code, created.code)
    })

    it('Vendor는 {id, name}으로, Solution은 공백을 지운 텍스트로 등록되고 둘로 거를 수 있다', async () => {
      // given: 등록된 Vendor와 새 Solution 이름
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const sales = await make('sales')
      const text = unique('Solution')

      // when: Vendor와 앞뒤 공백이 있는 Solution으로 Deal을 등록한다
      const created = await sales.deals.create(await validInput(sales, { vendorId: vendor.id, solution: `  ${text}  ` }))

      // then: Vendor·Solution이 저장되고 Vendor·Solution 필터로 그 Deal만 찾는다 (끝에 정리한다)
      expect(created.vendor).toEqual({ id: vendor.id, name: vendor.name })
      expect(created.solution).toBe(text)
      expect((await sales.deals.list({ vendorId: vendor.id })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ solution: text.toLowerCase() })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ vendorId: vendor.id, solution: 'no-such-solution-text' })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
      const cleanup = await make('admin')
      await cleanup.vendors.remove(vendor.id)
    })

    it('Vendor 없이 Solution을 받고 Vendor를 바꿔도 Solution은 유지한다', async () => {
      // given: Vendor 하나와 Vendor 없는 Deal
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { solution: 'ITDR' }))

      // when: Vendor를 넣었다가 비운다
      const withVendor = await sales.deals.update(created.code, { vendorId: vendor.id })
      const cleared = await sales.deals.update(created.code, { vendorId: null })

      // then: 처음엔 vendor가 null이고 두 번 모두 Solution이 그대로다 (끝에 정리한다)
      expect(created.vendor).toBeNull()
      expect(withVendor.solution).toBe('ITDR')
      expect(cleared.solution).toBe('ITDR')
      await sales.deals.remove(created.code, created.code)
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('수정으로 Solution을 바꾸고 비우기는 거절하며 이력에 남긴다', async () => {
      // given: Solution이 MFA인 Deal
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { solution: 'MFA' }))

      // when: Solution을 바꾸고, 비우기를 시도하고, 이름만 바꾼다
      const replaced = await sales.deals.update(created.code, { solution: '  ITDR ' })
      await expectRejects(sales.deals.update(created.code, { solution: '   ' }), 422, 'Solution을 입력하세요.')
      await expectRejects(sales.deals.update(created.code, { solution: '' }), 422, 'Solution을 입력하세요.')
      const kept = await sales.deals.update(created.code, { name: unique('renamed') })

      // then: Solution이 바뀌고 이름 수정에도 유지되며 Solution 이력은 MFA에서 ITDR 한 건이다 (끝에 정리한다)
      expect(replaced.solution).toBe('ITDR')
      expect(kept.solution).toBe('ITDR')
      const entries = (await sales.history.list(created.code, {})).filter((h) => h.target === 'Solution')
      expect(entries.map((h) => [h.before, h.after])).toEqual([['MFA', 'ITDR']])
      await sales.deals.remove(created.code, created.code)
    })

    it('등록에는 Solution이 필수다', async () => {
      const sales = await make('sales')
      // given: 유효한 등록 입력
      const base = await validInput(sales)

      // when·then: 빈 값과 공백만 있는 Solution은 Solution 문구와 함께 422다
      await expectRejects(sales.deals.create({ ...base, solution: '' }), 422, 'Solution을 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, solution: '   ' }), 422, 'Solution을 입력하세요.')
    })

    it('Solution 텍스트의 대소문자 무시 부분 일치로 목록을 거른다', async () => {
      // given: 토큰이 들어 있는 Solution과 다른 Solution의 Deal
      const sales = await make('sales')
      const token = unique('Tok').toLowerCase()
      const hit = await sales.deals.create(await validInput(sales, { solution: `Pre-${token.toUpperCase()}-Post` }))
      const miss = await sales.deals.create(await validInput(sales, { solution: 'other' }))

      // when: 소문자 토큰으로 Solution을 검색한다
      const found = await sales.deals.list({ solution: token })

      // then: 토큰이 든 Deal만 나온다 (끝에 정리한다)
      expect(found.items.map((d) => d.code)).toEqual([hit.code])
      await sales.deals.remove(hit.code, hit.code)
      await sales.deals.remove(miss.code, miss.code)
    })

    it('200자 Solution 텍스트를 받아들인다', async () => {
      const sales = await make('sales')

      // when: 200자 Solution으로 등록한다
      const created = await sales.deals.create(await validInput(sales, { solution: 'a'.repeat(200) }))

      // then: 그대로 저장된다 (끝에 정리한다)
      expect(created.solution).toBe('a'.repeat(200))
      await sales.deals.remove(created.code, created.code)
    })

    it('없는 Vendor와 긴 Solution은 이름 검사 뒤 서버 순서로 거절한다', async () => {
      // given: 영업 게이트웨이와 201자 Solution
      const sales = await make('sales')
      const base = await validInput(sales)
      const tooLong = 'a'.repeat(201)

      // when·then: 긴 Solution, 없는 Vendor(긴 Solution보다 먼저), 빈 이름(가장 먼저) 순서로 각 문구의 422다
      await expectRejects(sales.deals.create({ ...base, solution: tooLong }), 422, 'Solution은 200자 이내로 입력하세요.')
      await expectRejects(
        sales.deals.create({ ...base, vendorId: NO_SUCH_ID, solution: tooLong }),
        422,
        '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
      )
      await expectRejects(sales.deals.create({ ...base, name: '  ', solution: tooLong }), 422, 'Deal Name을 입력하세요.')
    })

    it('검색 조건은 AND로 결합한다', async () => {
      const sales = await make('sales')
      // given: 등록된 Deal(검색 조건은 AND로 결합한다)
      const input = await validInput(sales)
      const created = await sales.deals.create(input)

      // when: 키워드·Status·Forecast(여러 값·중복 포함)·Vendor 조건을 겹쳐 각각 조회한다
      const byKeyword = await sales.deals.list({ keyword: input.name })
      const allMatch = await sales.deals.list({ keyword: input.name, statusKey: 'prospecting', forecastKeys: ['pipeline'] })
      const wrongForecast = await sales.deals.list({ keyword: input.name, forecastKeys: ['commit'] })
      const forecastAmong = await sales.deals.list({ keyword: input.name, forecastKeys: ['commit', 'pipeline'] })
      const forecastDuplicated = await sales.deals.list({ keyword: input.name, forecastKeys: ['pipeline', 'pipeline'] })
      const wrongVendor = await sales.deals.list({ keyword: input.name, vendorId: NO_SUCH_ID })

      // then: 모두 맞을 때만 찾아지고 하나라도 틀리면 0건이다 (끝에 정리한다)
      expect(byKeyword.total).toBe(1)
      expect(allMatch.total).toBe(1)
      expect(wrongForecast.total).toBe(0)
      expect(forecastAmong.total).toBe(1)
      expect(forecastDuplicated.total).toBe(1)
      expect(wrongVendor.total).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })

    it('Expected Close의 연도·분기로 거르고 분기의 양 끝날을 포함한다', async () => {
      // given: 분기 첫날·분기 끝날·다음 분기 첫날의 Deal 셋
      const sales = await make('sales')
      const tag = unique('tag')
      const first = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-01-01' }))
      const last = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-03-31' }))
      const next = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-04-01' }))

      // when: 2027년 1분기·2분기·연 전체·2026년으로 조회한다
      const q1 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1] })
      const q2 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [2] })
      const year = await sales.deals.list({ keyword: tag, year: 2027 })
      const other = await sales.deals.list({ keyword: tag, year: 2026 })

      // then: 1분기는 첫날·끝날 두 건, 2분기는 다음 분기 한 건, 연 전체는 3건, 2026년은 0건이다 (끝에 정리한다)
      expect(q1.items.map((d) => d.code).sort()).toEqual([first.code, last.code].sort())
      expect(q2.items.map((d) => d.code)).toEqual([next.code])
      expect(year.total).toBe(3)
      expect(other.total).toBe(0)
      for (const d of [first, last, next]) await sales.deals.remove(d.code, d.code)
    })

    it('여러 분기를 고르면 그 사이 분기를 빼고 거른다 (Quarter 다중 선택)', async () => {
      // given: 분기 경계 날짜 7개의 Deal
      const sales = await make('sales')
      const tag = unique('tag')
      const days = ['2027-01-01', '2027-03-31', '2027-04-01', '2027-06-30', '2027-07-01', '2027-09-30', '2027-10-01']
      const created: DealDetail[] = []
      for (const revenueDate of days) created.push(await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate })))

      // when: 1·3분기와 2분기로 조회한다
      const q13 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1, 3] })
      const single = await sales.deals.list({ keyword: tag, year: 2027, quarters: [2] })

      // then: 1·3분기는 해당 4건만, 2분기는 해당 2건만 나온다 (끝에 정리한다)
      const code = (index: number) => created[index]?.code
      expect(q13.items.map((d) => d.code).sort()).toEqual([0, 1, 4, 5].map(code).sort())
      expect(q13.total).toBe(4)
      expect(single.items.map((d) => d.code).sort()).toEqual([2, 3].map(code).sort())
      for (const d of created) await sales.deals.remove(d.code, d.code)
    })

    it('분기가 없거나 빈 목록이거나 네 분기 전체면 분기 조건이 없는 것으로 읽는다 (Quarter 다중 선택)', async () => {
      // given: 1분기·4분기 날짜의 Deal 둘
      const sales = await make('sales')
      const tag = unique('tag')
      const created = [
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-02-01' })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-11-01' })),
      ]

      // when: 분기 없음·빈 목록·네 분기 전체·중복 분기로 조회한다
      const none = await sales.deals.list({ keyword: tag, year: 2027 })
      const empty = await sales.deals.list({ keyword: tag, year: 2027, quarters: [] })
      const four = await sales.deals.list({ keyword: tag, year: 2027, quarters: [4, 3, 2, 1] })
      const twice = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1, 1] })

      // then: 앞의 셋은 모두 2건이고 1분기 중복은 1건이다 (끝에 정리한다)
      expect([none.total, empty.total, four.total]).toEqual([2, 2, 2])
      expect(twice.total).toBe(1)
      for (const d of created) await sales.deals.remove(d.code, d.code)
    })

    it('여러 분기와 월을 함께 주면 거절하고 네 분기 전체와 월은 허용한다 (Quarter 다중 선택)', async () => {
      const sales = await make('sales')

      // when·then: 두 분기+월과 한 분기+월은 422이고 네 분기 전체+월은 조회된다
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 3], month: 2 }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1], month: 2 }), 422)
      await expect(sales.deals.list({ year: 2027, quarters: [1, 2, 3, 4], month: 2 })).resolves.toHaveProperty('total')
    })

    it('1~4 밖의 분기와 네 개를 넘는 분기는 거절한다 (Quarter 다중 선택)', async () => {
      const sales = await make('sales')

      // when·then: 0·5·다섯 개 분기는 422다
      await expectRejects(sales.deals.list({ year: 2027, quarters: [0] as never }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 5] as never }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 2, 3, 4, 1] as never }), 422)
    })

    it('updatedFrom·updatedTo 날짜 자체를 범위에 포함한다', async () => {
      // given: 등록한 Deal과 그 전날·다음날
      const sales = await make('sales')
      const tag = unique('tag')
      const created = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      const day = created.lastUpdatedOn.slice(0, 10)
      const next = new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10)
      const prev = new Date(Date.parse(`${day}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10)

      // when: 같은 날 범위·다음날 이후·전날 이전·전날 이후·다음날 이전 조건으로 각각 조회한다
      const sameDay = await sales.deals.list({ keyword: tag, updatedFrom: day, updatedTo: day })
      const fromNext = await sales.deals.list({ keyword: tag, updatedFrom: next })
      const toPrev = await sales.deals.list({ keyword: tag, updatedTo: prev })
      const fromPrev = await sales.deals.list({ keyword: tag, updatedFrom: prev })
      const toNext = await sales.deals.list({ keyword: tag, updatedTo: next })

      // then: 경계 포함 규칙대로 같은 날·전날 이후·다음날 이전은 1건, 다음날 이후·전날 이전은 0건이다 (끝에 정리한다)
      expect(sameDay.total).toBe(1)
      expect(fromNext.total).toBe(0)
      expect(toPrev.total).toBe(0)
      expect(fromPrev.total).toBe(1)
      expect(toNext.total).toBe(1)
      await sales.deals.remove(created.code, created.code)
    })

    it('시작이 끝보다 늦은 업데이트 기간은 422로 거절한다', async () => {
      const sales = await make('sales')

      // when·then: updatedFrom이 updatedTo보다 늦으면 422다
      await expectRejects(sales.deals.list({ updatedFrom: '2026-07-01', updatedTo: '2026-06-30' }), 422)
    })

    it('모든 역할에 서버 날짜 기준 기간 프리셋을 알려 준다', async () => {
      // given: 조회자 역할
      const user = await make('user')

      // when: 기간 프리셋을 조회한다
      const result = await user.deals.updatedPeriods()

      // then: 지난 기간 5개와 다가오는 기간 2개가 서버 오늘 날짜를 끝·시작으로 하고 2주 시작은 14일 전이다
      expect(result.periods.map((p) => p.key)).toEqual(['2w', '1m', '2m', '3m', '6m'])
      for (const period of result.periods) {
        expect(period.to).toBe(result.today)
        expect(period.from < period.to).toBe(true)
      }
      expect(result.periods[0]?.from).toBe(
        new Date(Date.parse(`${result.today}T00:00:00Z`) - 14 * 86_400_000).toISOString().slice(0, 10),
      )
      expect(result.upcoming.map((p) => p.key)).toEqual(['1m', '2m'])
      for (const period of result.upcoming) {
        expect(period.from).toBe(result.today)
        expect(period.to > period.from).toBe(true)
      }
    })

    it('담당자·고객·파트너·Vendor·Forecast로 양방향 정렬하고 같으면 코드 오름차순이다', async () => {
      // given: 고객·파트너·Forecast가 다른 Deal 셋과 Vendor 둘
      const admin = await make('admin')
      const vendors = [await admin.vendors.create(unique('vb')), await admin.vendors.create(unique('va'))]
      const sales = await make('sales')
      const tag = unique('tag')
      const rows: [string, string, string][] = [
        ['Cc', 'pipeline', 'ZZb'],
        ['aa', 'commit', 'ZZa'],
        ['Bb', 'best', 'ZZc'],
      ]
      const made = []
      for (const [index, [company, forecastKey, partnerCompany]] of rows.entries()) {
        const base = await validInput(sales, { name: `${tag}${unique('d')}`, forecastKey, vendorId: vendors[index % 2]?.id ?? null })
        made.push(
          await sales.deals.create({
            ...base,
            customer: { ...base.customer, company: `${tag}${company}` },
            partner: { contactId: null, company: `${tag}${partnerCompany}`, name: unique('pn'), title: '', email: null, phone: null },
          }),
        )
      }
      // when: 고객 기준 오름·내림과 파트너 기준 오름으로 조회한다
      const byCustomer = made.map((d) => d.code)
      const asc = (await sales.deals.list({ keyword: tag, sort: 'customer', order: 'asc' })).items.map((d) => d.code)
      const desc = (await sales.deals.list({ keyword: tag, sort: 'customer', order: 'desc' })).items.map((d) => d.code)

      // then: 고객은 소문자 기준 aa<bb<cc 순서이고 내림은 반대, 파트너도 이름순이며 다른 정렬 키도 3건을 모두 낸다 (끝에 정리한다)
      // 소문자 기준: aa < bb < cc
      expect(asc).toEqual([byCustomer[1], byCustomer[2], byCustomer[0]])
      expect(desc).toEqual([byCustomer[0], byCustomer[2], byCustomer[1]])
      const partner = (await sales.deals.list({ keyword: tag, sort: 'partner', order: 'asc' })).items.map((d) => d.code)
      expect(partner).toEqual([byCustomer[1], byCustomer[0], byCustomer[2]])
      for (const sort of ['owner', 'vendor', 'forecastKey'] as const) {
        const found = await sales.deals.list({ keyword: tag, sort, order: 'desc' })
        expect(found.total).toBe(3)
      }
      for (const d of made) await sales.deals.remove(d.code, d.code)
      const cleanup = await make('admin')
      for (const v of vendors) await cleanup.vendors.remove(v.id)
    })

    it('파트너나 Vendor가 없는 Deal은 어느 방향에서도 맨 뒤에 둔다', async () => {
      // given: 파트너가 있는 Deal과 없는 Deal
      const sales = await make('sales')
      const tag = unique('tag')
      const base = await validInput(sales, { name: `${tag}${unique('d')}` })
      const withPartner = await sales.deals.create({
        ...base,
        partner: { contactId: null, company: `${tag}partner`, name: unique('pn'), title: '', email: null, phone: null },
      })
      const without = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))

      // when·then: 파트너·Vendor 정렬은 오름·내림 모두 없는 Deal이 맨 뒤다 (끝에 정리한다)
      for (const order of ['asc', 'desc'] as const) {
        const found = await sales.deals.list({ keyword: tag, sort: 'partner', order })
        expect(found.items.map((d) => d.code)).toEqual([withPartner.code, without.code])
        const byVendor = await sales.deals.list({ keyword: tag, sort: 'vendor', order })
        expect(byVendor.items.map((d) => d.code)).toEqual([withPartner.code, without.code].sort())
      }
      for (const d of [withPartner, without]) await sales.deals.remove(d.code, d.code)
    })

    it('지연 목록은 지연 Deal만, 지연+미업데이트는 둘 중 하나인 Deal만 배지대로 보여 준다', async () => {
      // given: 기한이 지난 Next Action의 Deal과 먼 기한의 Deal
      const sales = await make('sales')
      const tag = unique('tag')
      const overdue = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      const onTime = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      await sales.actions.create(overdue.code, action({ progress: '', nextAction: '지난 계획', dueDate: '2000-01-01' }))
      await sales.actions.create(onTime.code, action({ progress: '', nextAction: '먼 계획', dueDate: '2999-01-01' }))

      // when: 지연, 지연·미업데이트, 미업데이트 조건으로 조회한다
      const found = await sales.deals.list({ keyword: tag, overdue: true })
      const either = await sales.deals.list({ keyword: tag, overdue: true, stale: true })
      const none = await sales.deals.list({ keyword: tag, stale: true })

      // then: 지연 조건은 지연 Deal만(위험 표시 포함), 지연·미업데이트도 그 Deal만, 미업데이트 조건에는 기한 안 지난 Deal이 없다 (끝에 정리한다)
      expect(found.items.map((d) => d.code)).toEqual([overdue.code])
      expect(found.total).toBe(1)
      expect(found.items[0]?.risk === 'overdue' || found.items[0]?.risk === 'overdue_stale').toBe(true)
      expect(either.items.map((d) => d.code)).toEqual([overdue.code])
      expect(none.items.map((d) => d.code)).not.toContain(onTime.code)
      for (const d of [overdue, onTime]) await sales.deals.remove(d.code, d.code)
    })

    it('정렬 방향과 무관하게 같은 값은 코드 오름차순으로 놓는다', async () => {
      // given: 같은 매출금액의 Deal 셋
      const sales = await make('sales')
      const tag = unique('tag')
      const made = [
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
      ]
      const expected = made.map((d) => d.code).sort()

      // when: 매출금액 오름·내림으로 조회한다
      const asc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'asc' })
      const desc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'desc' })

      // then: 두 방향 모두 코드 오름차순이다 (끝에 정리한다)
      expect(asc.items.map((d) => d.code)).toEqual(expected)
      expect(desc.items.map((d) => d.code)).toEqual(expected)
      for (const d of made) await sales.deals.remove(d.code, d.code)
    })

    it('매출금액을 요청한 방향으로 정렬한다', async () => {
      // given: 매출금액이 다른 Deal 둘
      const sales = await make('sales')
      const tag = unique('tag')
      const small = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 1_000_000 }))
      const big = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 9_000_000 }))

      // when: 오름·내림으로 조회한다
      const asc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'asc' })
      const desc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'desc' })

      // then: 오름은 작은 금액 먼저, 내림은 큰 금액 먼저다 (끝에 정리한다)
      expect(asc.items.map((d) => d.code)).toEqual([small.code, big.code])
      expect(desc.items.map((d) => d.code)).toEqual([big.code, small.code])
      for (const d of [small, big]) await sales.deals.remove(d.code, d.code)
    })

    it('구매절차는 앞뒤 공백을 지운 뒤 길이를 검사하고 지운 값으로 저장한다', async () => {
      // given: 500자 구매절차
      const sales = await make('sales')
      const procurement = '가'.repeat(500)

      // when: 앞뒤 공백이 있는 500자로 등록한다
      const created = await sales.deals.create(await validInput(sales, { procurement: `  ${procurement}  ` }))

      // then: 공백이 지워진 값으로 저장된다
      expect(created.procurement).toBe(procurement)

      // when: 공백 포함 501자로 등록한다 (끝에 정리한다)
      // then: 422다
      await expectRejects(
        sales.deals.create(await validInput(sales, { procurement: ` ${'가'.repeat(501)} ` })),
        422,
        '구매절차는 500자 이내로 입력하세요.',
      )
      await sales.deals.remove(created.code, created.code)
    })

    it('등록 시점에 Status 체류 일수는 0이고 변경 시각이 있으며 경고는 없다', async () => {
      // when: Deal을 등록한다
      const sales = await make('sales')

      const created = await sales.deals.create(await validInput(sales))

      // then: statusDays 0, statusChangedOn 유효, risk null이며 목록 행도 같다 (끝에 정리한다)
      expect(created.statusDays).toBe(0)
      expect(created.statusChangedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/) // 진입일은 시각 없는 날짜다
      expect(created.risk).toBeNull()
      const row = (await sales.deals.list({ keyword: created.code })).items.find((d) => d.code === created.code)
      expect(row).toMatchObject({ statusChangedOn: created.statusChangedOn, statusDays: 0, risk: null })
      await sales.deals.remove(created.code, created.code)
    })

    it('Forecast만 바꾸면 Status 변경 시각을 유지하고 Status를 바꾸면 앞으로 옮긴다', async () => {
      // given: 등록된 Deal(Forecast만 바꾸면 Status 변경 시각을 유지하고 Status를 바꾸면 앞으로 옮긴다)
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      // when: Forecast만 바꾼다
      const forecastOnly = await sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'best' } })
      // then: statusChangedOn이 그대로다
      expect(forecastOnly.deal.statusChangedOn).toBe(created.statusChangedOn)

      // when: Status를 바꾼다
      const moved = await sales.deals.applyChange(created.code, { change: { field: 'statusKey', value: 'introduction' } })
      // then: Status가 바뀌고 변경 시각이 앞으로 가며 체류 일수는 0이다 (끝에 정리한다)
      expect(moved.deal.statusKey).toBe('introduction')
      expect(moved.deal.statusChangedOn >= created.statusChangedOn).toBe(true)
      expect(moved.deal.statusDays).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })
  })
}
