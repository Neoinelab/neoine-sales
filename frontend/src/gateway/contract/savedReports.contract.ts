/**
 * 저장 리포트 계약. mock과 실제 서버가 같은 모양·같은 권한으로 답해야 한다.
 * 호출마다 고유한 이름을 쓰고 만든 것은 admin으로 치운다. 역할을 바꿀 때는 그 역할의 `make`를 다시 부른다(mock은 세션이 하나).
 */

import { describe, expect, it } from 'vitest'
import type { ReportChartInput, ReportLayout, ReportQueryInput, SavedReportInput } from '../../shared/model/reportTypes'
import { expectRejects, NO_SUCH_ID, unique, type ContractRole, type MakeGateway } from './support'

const DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.amount', group: false, aggregate: 'sum', label: '금액 합계', sort: 'desc' },
  ],
  conditions: [{ field: 'deal.amount', operator: 'gte', value: 1_500_000 }],
  combine: 'and',
  rowLimit: 1000,
}

const OTHER_DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.code', group: false },
    { field: 'action.action', group: false },
  ],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

const NOT_FOUND = '리포트를 찾을 수 없습니다.'

/** DEFINITION(0: Vendor 그룹, 1: 금액 합계)에 맞는 세로 막대 차트. */
const CHART: ReportChartInput = {
  kind: 'bar',
  category: 0,
  series: null,
  values: [1],
  swap: false,
  title: 'Vendor별 금액',
  legend: 'bottom',
  dataLabels: true,
  categoryAxisTitle: 'Vendor',
  valueAxisTitle: '금액',
  valueMin: 0,
  valueMax: 12.5,
  secondaryAxis: false,
  histogram: null,
  showTotal: false,
  comboSeries: null,
}

/** 서버의 기본 배치와 시험용 배치. */
const DEFAULT_LAYOUT: ReportLayout = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' }
const SIDE_LAYOUT: ReportLayout = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }
const TABLE_LAYOUT: ReportLayout = { view: 'table', order: ['table', 'chart'], arrange: 'stacked' }

const input = (over: Partial<SavedReportInput> = {}): SavedReportInput => ({
  name: unique('rpt'),
  description: '계약 시험',
  visibility: 'public',
  definition: DEFINITION,
  chart: null,
  layout: DEFAULT_LAYOUT,
  ...over,
})

export function savedReportsContract(make: MakeGateway): void {
  /** 해당 역할로 리포트를 만들고 id를 돌려준다. */
  async function createAs(role: ContractRole, over: Partial<SavedReportInput> = {}) {
    const { reports } = await make(role)
    return reports.create(input(over))
  }
  async function cleanup(...ids: number[]): Promise<void> {
    const { reports } = await make('admin')
    for (const id of ids) await reports.remove(id).catch(() => undefined)
  }

  describe('저장 리포트 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('%s 역할이 리포트를 저장하면 자기가 만든 사람이고 revision 1이다', async (role) => {
      // given: 역할별 로그인과 앞뒤 공백이 있는 이름·설명
      const gateway = await make(role)
      const me = await gateway.auth.me()
      const body = input({ name: `  ${unique('rpt')}  `, description: '  설명  ' })

      // when: 리포트를 저장한다
      const created = await gateway.reports.create(body)

      // then: revision 1, 공백이 지워진 이름·설명, 만든 사람과 최종 수정자가 나다
      expect(created).toMatchObject({ revision: 1, visibility: 'public', description: '설명', entities: ['deal'] })
      expect(created.name).toBe(body.name.trim())
      expect(created.owner.id).toBe(me.id)
      expect(created.updatedBy.id).toBe(me.id)
      expect(created.definition).toEqual(DEFINITION)
      expect(created.generatedSql.length).toBeGreaterThan(0)
      expect(created.createdAt).toBeTruthy()
      await cleanup(created.id)
    })

    it('Action 필드를 쓰는 리포트의 데이터는 Deal과 Actions로 목록에 나온다', async () => {
      // given: Action 컬럼을 쓰는 정의로 저장한 리포트
      const created = await createAs('sales', { definition: OTHER_DEFINITION })

      // when: 목록을 읽는다
      const { reports } = await make('sales')
      const listed = (await reports.list()).find((r) => r.id === created.id)

      // then: 데이터가 deal, action이다
      expect(listed?.entities).toEqual(['deal', 'action'])
      await cleanup(created.id)
    })

    it('빈 이름·긴 이름·긴 설명·알 수 없는 공개 범위는 422로 거절한다', async () => {
      // given: 로그인한 sales(빈 이름·긴 이름·긴 설명·알 수 없는 공개 범위는 422로 거절한다)
      const { reports } = await make('sales')

      // when: 빈 이름, 101자 이름, 1,001자 설명, 알 수 없는 공개 범위로 각각 저장한다
      const empty = await expectRejects(reports.create(input({ name: '   ' })), 422)
      const long = await expectRejects(reports.create(input({ name: 'a'.repeat(101) })), 422)
      const description = await expectRejects(reports.create(input({ description: 'a'.repeat(1001) })), 422)
      const visibility = await expectRejects(reports.create(input({ visibility: 'shared' as 'public' })), 422)

      // then: 모두 422 validation이다
      for (const error of [empty, long, description, visibility]) expect(error.kind).toBe('validation')
    })

    it('가장 긴 이름(100자)과 설명(1,000자)은 받는다', async () => {
      // given: 로그인한 sales와 100자 이름
      const { reports } = await make('sales')
      const name = unique('r').padEnd(100, 'x')

      // when: 100자 이름과 1,000자 설명으로 저장한다
      const created = await reports.create(input({ name, description: 'd'.repeat(1000) }))

      // then: 길이가 그대로 저장된다
      expect(created.name).toHaveLength(100)
      expect(created.description).toHaveLength(1000)
      await cleanup(created.id)
    })

    it('규칙을 어긴 정의는 저장하지 않고 위반을 모두 알린다', async () => {
      // given: 로그인한 sales와 지금 저장된 리포트 수, 카탈로그에 없는 필드 둘을 쓰는 정의
      const { reports } = await make('sales')
      const before = (await reports.list()).length
      const broken: ReportQueryInput = {
        columns: [{ field: 'deal.nope', group: false }, { field: 'deal.nada', group: false }],
        conditions: [],
        combine: 'and',
        rowLimit: 100,
      }

      // when: 그 정의로 저장한다
      const error = await expectRejects(reports.create(input({ definition: broken })), 422)

      // then: 422 invalid-report이고 위반이 둘이며 리포트 수가 그대로다
      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toHaveLength(2)
      expect((await reports.list()).length).toBe(before)
    })

    it('누가 만들었든 대소문자만 다른 같은 이름은 409로 거절한다', async () => {
      // given: sales가 저장한 리포트
      const name = unique('Rpt')
      const first = await createAs('sales', { name })
      const sales = await make('sales')
      const user = await make('user')

      // when: sales와 user가 대소문자만 다른 이름으로 저장한다
      const duplicate = await expectRejects(sales.reports.create(input({ name: name.toUpperCase() })), 409)
      const other = await expectRejects(user.reports.create(input({ name: name.toLowerCase() })), 409)

      // then: 모두 409 already-exists다
      expect(duplicate.kind).toBe('already-exists')
      expect(other.kind).toBe('already-exists')
      await cleanup(first.id)
    })

    it('남의 비공개 리포트 이름도 409로 거절한다', async () => {
      // given: sales가 저장한 비공개 리포트
      const name = unique('Priv')
      const hidden = await createAs('sales', { name, visibility: 'private' })
      const user = await make('user')

      // when: user가 같은 이름으로 저장한다
      const error = await expectRejects(user.reports.create(input({ name })), 409)

      // then: 409 already-exists다
      expect(error.kind).toBe('already-exists')
      await cleanup(hidden.id)
    })

    it('목록은 최근 수정 순이고 남의 비공개는 보이지 않으며 admin에게는 보인다', async () => {
      // given: sales의 리포트 둘과 비공개 리포트 하나
      const older = await createAs('sales')
      const newer = await createAs('sales')
      const hidden = await createAs('sales', { visibility: 'private' })

      // when: sales·user·admin이 각각 목록을 읽는다
      const asSales = (await (await make('sales')).reports.list()).map((r) => r.id)
      const asUser = (await (await make('user')).reports.list()).map((r) => r.id)
      const asAdmin = (await (await make('admin')).reports.list()).map((r) => r.id)

      // then: 최근 것이 먼저이고 user에게는 비공개가 없으며 admin에게는 있다
      expect(asSales.indexOf(newer.id)).toBeLessThan(asSales.indexOf(older.id))
      expect(asSales).toContain(hidden.id)
      expect(asUser).toEqual(expect.arrayContaining([older.id, newer.id]))
      expect(asUser).not.toContain(hidden.id)
      expect(asAdmin).toContain(hidden.id)
      await cleanup(older.id, newer.id, hidden.id)
    })

    it.each([
      ['sales', 'user'],
      ['user', 'sales'],
    ] as const)('남의 비공개 리포트는 모든 요청에서 없는 id와 같은 404다 (만든 사람 %s, 보는 사람 %s)', async (owner, viewer) => {
      // given: 비공개 리포트와 다른 역할의 사용자
      const created = await createAs(owner, { visibility: 'private' })
      const { reports } = await make(viewer)
      const body = { ...input(), revision: 1 }

      // when: 상세·덮어쓰기·삭제·복제·실행을 요청하고, 없는 id도 읽는다
      const errors = [
        await expectRejects(reports.get(created.id), 404),
        await expectRejects(reports.update(created.id, body), 404),
        await expectRejects(reports.remove(created.id), 404),
        await expectRejects(reports.copy(created.id, { name: unique('c'), description: '', visibility: 'public' }), 404),
        await expectRejects(reports.run(created.id), 404),
      ]
      const missing = await expectRejects(reports.get(NO_SUCH_ID), 404)

      // then: 모두 404 not-found이고 문구가 없는 id와 같다
      for (const error of errors) {
        expect(error.kind).toBe('not-found')
        expect(error.message).toBe(missing.message)
      }
      expect(missing.message).toBe(NOT_FOUND)
      await cleanup(created.id)
    })

    it('admin은 남의 비공개 리포트를 보고 고치고 지운다', async () => {
      // given: sales의 비공개 리포트
      const created = await createAs('sales', { visibility: 'private' })
      const { reports } = await make('admin')

      // when: admin이 열고, 공개로 고치고, 지운다
      const seen = await reports.get(created.id)
      const changed = await reports.update(created.id, { ...input({ name: seen.name, visibility: 'public' }), revision: seen.revision })
      await reports.remove(created.id)

      // then: 열리고 만든 사람은 그대로이며 지운 뒤에는 404다
      expect(seen.id).toBe(created.id)
      expect(changed.visibility).toBe('public')
      expect(changed.owner.id).toBe(created.owner.id)
      await expectRejects(reports.get(created.id), 404)
    })

    it('없는 리포트는 숨긴 리포트와 같은 404 문구다', async () => {
      // given: 로그인한 sales(없는 리포트는 숨긴 리포트와 같은 404 문구다)
      const { reports } = await make('sales')

      // when·then: 없는 id의 상세·삭제·실행이 모두 같은 404 문구다
      await expectRejects(reports.get(NO_SUCH_ID), 404, NOT_FOUND)
      await expectRejects(reports.remove(NO_SUCH_ID), 404, NOT_FOUND)
      await expectRejects(reports.run(NO_SUCH_ID), 404, NOT_FOUND)
    })

    it('다른 역할도 공개 리포트를 고치고 복제하지만 지우거나 공개 범위를 바꿀 수 없다', async () => {
      // given: sales의 공개 리포트와 user 로그인
      const created = await createAs('sales')
      const { reports } = await make('user')
      const me = await (await make('user')).auth.me()

      // when: user가 정의를 고치고, 공개 범위를 바꾸려 하고, 지우려 하고, 복제한다
      const edited = await reports.update(created.id, { ...input({ name: created.name, description: '다른 사람이 고침', definition: OTHER_DEFINITION }), revision: created.revision })
      const visibility = await expectRejects(
        reports.update(created.id, { ...input({ name: created.name, visibility: 'private' }), revision: edited.revision }),
        403,
      )
      const deletion = await expectRejects(reports.remove(created.id), 403)
      const copy = await reports.copy(created.id, { name: unique('copy'), description: '복제', visibility: 'private' })

      // then: 고치기·복제는 되고 공개 범위 변경·삭제는 403이다
      expect(edited).toMatchObject({ description: '다른 사람이 고침', revision: 2 })
      expect(edited.owner.id).toBe(created.owner.id)
      expect(edited.updatedBy.id).toBe(me.id)
      expect(edited.definition).toEqual(OTHER_DEFINITION)
      expect(visibility.kind).toBe('forbidden')
      expect(deletion.kind).toBe('forbidden')
      expect(copy).toMatchObject({ revision: 1, visibility: 'private', description: '복제' })
      expect(copy.owner.id).toBe(me.id)
      expect(copy.definition).toEqual(OTHER_DEFINITION)
      await cleanup(created.id, copy.id)
    })

    it('만든 사람은 공개 범위를 바꾸고 공개·비공개 리포트를 지운다', async () => {
      // given: sales의 공개·비공개 리포트
      const first = await createAs('sales')
      const second = await createAs('sales', { visibility: 'private' })
      const { reports } = await make('sales')

      // when: 공개 범위를 비공개로 바꾸고 둘 다 지운다
      const changed = await reports.update(first.id, { ...input({ name: first.name, visibility: 'private' }), revision: 1 })
      await reports.remove(first.id)
      await reports.remove(second.id)

      // then: 바뀌고 둘 다 404로 사라진다
      expect(changed.visibility).toBe('private')
      await expectRejects(reports.get(first.id), 404)
      await expectRejects(reports.get(second.id), 404)
    })

    it('덮어쓰면 이름·설명·정의가 바뀌고 revision이 오르며 만든 사람은 그대로다', async () => {
      // given: sales의 리포트
      const created = await createAs('sales')
      const { reports } = await make('sales')
      const name = unique('renamed')

      // when: 이름·설명·정의를 바꿔 덮어쓴다
      const updated = await reports.update(created.id, { name, description: '', visibility: 'public', definition: OTHER_DEFINITION, chart: null, layout: DEFAULT_LAYOUT, revision: created.revision })
      const reread = await reports.get(created.id)

      // then: revision 2, 만든 사람 그대로, 다시 읽어도 같다
      expect(updated).toMatchObject({ id: created.id, name, description: '', revision: 2, entities: ['deal', 'action'] })
      expect(updated.owner.id).toBe(created.owner.id)
      expect(reread.definition).toEqual(OTHER_DEFINITION)
      expect(reread.revision).toBe(2)
      await cleanup(created.id)
    })

    it('낡은 revision은 409 invalid-state로 거절하고 아무것도 바꾸지 않는다', async () => {
      // given: 한 번 덮어써 revision 2가 된 리포트
      const created = await createAs('sales')
      const { reports } = await make('sales')
      await reports.update(created.id, { ...input({ name: created.name, description: '먼저 저장' }), revision: 1 })

      // when: revision 1로 다시 덮어쓴다
      const stale = await expectRejects(reports.update(created.id, { ...input({ name: created.name, description: '늦은 저장' }), revision: 1 }), 409)
      const reread = await reports.get(created.id)

      // then: 409 invalid-state이고 먼저 저장한 값이 남는다
      expect(stale.kind).toBe('invalid-state')
      expect(reread).toMatchObject({ description: '먼저 저장', revision: 2 })
      await cleanup(created.id)
    })

    it('다른 리포트의 이름으로 바꾸는 덮어쓰기는 거절하고 자기 이름의 대소문자 변경은 된다', async () => {
      // given: sales의 리포트 둘
      const first = await createAs('sales')
      const second = await createAs('sales')
      const { reports } = await make('sales')

      // when: 둘째를 첫째 이름(대문자)으로 덮어쓰고, 자기 이름을 대문자로 덮어쓴다
      const error = await expectRejects(reports.update(second.id, { ...input({ name: first.name.toUpperCase() }), revision: 1 }), 409)
      const keepsName = await reports.update(second.id, { ...input({ name: second.name.toUpperCase() }), revision: 1 })

      // then: 앞은 409 already-exists, 뒤는 revision 2로 저장된다
      expect(error.kind).toBe('already-exists')
      expect(keepsName.revision).toBe(2)
      await cleanup(first.id, second.id)
    })

    it('편집자가 만든 사람의 다른 리포트 이름으로 바꾸면 409로 거절한다', async () => {
      // given: sales의 리포트 둘과 user 로그인
      const first = await createAs('sales')
      const second = await createAs('sales')
      const { reports } = await make('user')

      // when: user가 둘째를 첫째 이름으로 덮어쓴다
      const error = await expectRejects(reports.update(second.id, { ...input({ name: first.name }), revision: 1 }), 409)

      // then: 409 already-exists다
      expect(error.kind).toBe('already-exists')
      await cleanup(first.id, second.id)
    })

    it('복제하면 원본 정의에 새 만든 사람, revision 1이고 같은 이름은 거절한다', async () => {
      // given: Action 정의의 sales 리포트와 admin 로그인
      const created = await createAs('sales', { definition: OTHER_DEFINITION })
      const { reports } = await make('admin')
      const me = await (await make('admin')).auth.me()
      const name = unique('copy')

      // when: 복제하고, 같은 이름(대문자)으로 다시 복제한다
      const copy = await reports.copy(created.id, { name, description: '', visibility: 'public' })
      const duplicate = await expectRejects(reports.copy(created.id, { name: name.toUpperCase(), description: '', visibility: 'public' }), 409)

      // then: 첫 복제는 원본 정의에 admin 소유이고 둘째는 409 already-exists다
      expect(copy.id).not.toBe(created.id)
      expect(copy).toMatchObject({ name, revision: 1, definition: OTHER_DEFINITION })
      expect(copy.owner.id).toBe(me.id)
      expect(duplicate.kind).toBe('already-exists')
      await cleanup(created.id, copy.id)
    })

    it('저장 리포트의 실행 결과는 조회와 같은 모양이다', async () => {
      // given: sales의 리포트와 user 로그인
      const created = await createAs('sales')
      const { reports } = await make('user')

      // when: 저장 리포트를 실행하고 같은 정의를 직접 조회한다
      const run = await reports.run(created.id)
      const query = await reports.query(DEFINITION)

      // then: 컬럼·행 수·합계 유무·행 제한이 같다
      expect(run.columns.map((c) => [c.field, c.group, c.aggregate])).toEqual(query.columns.map((c) => [c.field, c.group, c.aggregate]))
      expect(run.rows.length).toBe(query.rows.length)
      expect(run.totals === null).toBe(query.totals === null)
      expect(run.rowLimit).toBe(1000)
      await cleanup(created.id)
    })

    it('삭제하면 모든 사람에게서 사라진다', async () => {
      // given: user의 리포트와 admin 로그인
      const created = await createAs('user')
      const { reports } = await make('admin')

      // when: 지운다
      await reports.remove(created.id)

      // then: 상세가 404이고 목록에도 없다
      await expectRejects(reports.get(created.id), 404)
      expect((await reports.list()).map((r) => r.id)).not.toContain(created.id)
    })

    // 테스트 코드: RC-105
    it('저장 리포트의 차트를 정규화해 보관하고 목록에 종류를 보이며 읽을 수 없음 안내는 없다', async () => {
      // given: sales 역할로 로그인한 계약 게이트웨이
      const { reports } = await make('sales')

      // when: 차트와 함께 리포트를 저장한다
      const created = await reports.create(input({ chart: { ...CHART, title: '  Vendor별 금액  ' } }))

      // then: 응답과 재조회의 차트가 정규화된 값이고 chartProblem이 null이며 목록 chartKind가 bar다
      expect(created.chart).toEqual(CHART)
      expect(created.chartProblem).toBeNull()
      expect((await reports.get(created.id)).chart).toEqual(CHART)
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBe('bar')
      await cleanup(created.id)
    })

    // 테스트 코드: RC-105
    it('차트 없이 저장하면 차트와 목록의 차트 종류가 null이다', async () => {
      // given: sales 역할로 로그인한 계약 게이트웨이
      const { reports } = await make('sales')

      // when: 차트 없이 리포트를 저장한다
      const created = await reports.create(input())

      // then: 차트·chartProblem이 null이고 목록 chartKind가 null이다
      expect(created.chart).toBeNull()
      expect(created.chartProblem).toBeNull()
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBeNull()
      await cleanup(created.id)
    })

    // 테스트 코드: RC-105
    it('차트만 바꿔 덮어쓰면 revision이 오르고 null로 덮어쓰면 차트가 지워진다', async () => {
      // given: 막대 차트가 있는 리포트
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      // when: 꺾은선 차트로 덮어쓰고 차트 없이 다시 덮어쓴다
      const changed = await reports.update(created.id, { ...input({ name: created.name, chart: { ...CHART, kind: 'line', title: '추이' } }), revision: created.revision })
      const cleared = await reports.update(created.id, { ...input({ name: created.name, chart: null }), revision: changed.revision })

      // then: revision 2·새 차트, revision 3·차트 null이고 목록 chartKind가 null이다
      expect(changed).toMatchObject({ revision: 2, chart: { kind: 'line', title: '추이' } })
      expect(cleared).toMatchObject({ revision: 3, chart: null })
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBeNull()
      await cleanup(created.id)
    })

    // 테스트 코드: RC-105
    it('범주가 그룹 컬럼이 아니면 위치·문구와 함께 거절하고 저장하지 않는다', async () => {
      const { reports } = await make('sales')
      // given: 저장된 리포트 수
      const before = (await reports.list()).length

      // when: 값 컬럼을 범주로 한 차트로 저장한다
      const error = await expectRejects(reports.create(input({ chart: { ...CHART, category: 1 } })), 422)

      // then: invalid-report이고 `["chart","category"]` chart-category-invalid 문구가 서버와 같으며 목록 수가 그대로다
      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toEqual([{ location: ['chart', 'category'], code: 'chart-category-invalid', message: '범주 열은 그룹핑한 컬럼이어야 합니다' }])
      expect((await reports.list()).length).toBe(before)
    })

    // 테스트 코드: RC-105
    it('그룹핑 없는 정의의 막대 차트는 서버 문구로 거절한다', async () => {
      // given: sales 역할로 로그인한 계약 게이트웨이
      const { reports } = await make('sales')

      // when: 그룹핑 없는 정의와 막대 차트로 저장한다
      const error = await expectRejects(reports.create(input({ definition: OTHER_DEFINITION, chart: CHART })), 422)

      // then: invalid-report이고 `["chart"]` chart-needs-grouping "(히스토그램 제외)" 문구다
      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toEqual([{ location: ['chart'], code: 'chart-needs-grouping', message: '그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)' }])
    })

    // 테스트 코드: RC-105
    it('바뀐 정의에 맞지 않는 차트로 덮어쓰면 거절하고 저장 내용을 유지한다', async () => {
      // given: 막대 차트가 있는 리포트
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      // when: 그룹핑 없는 정의와 이전 차트로 덮어쓴다
      const error = await expectRejects(reports.update(created.id, { ...input({ name: created.name, definition: OTHER_DEFINITION, chart: CHART }), revision: created.revision }), 422)

      // then: invalid-report이고 리포트는 revision 1과 이전 차트 그대로다
      expect(error.kind).toBe('invalid-report')
      expect(await reports.get(created.id)).toMatchObject({ revision: 1, chart: CHART })
      await cleanup(created.id)
    })

    // 테스트 코드: RC-105
    it('복제하면 차트가 정의와 함께 복사되고 목록에도 종류가 나온다', async () => {
      // given: 막대 차트가 있는 리포트
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      // when: 복제한다
      const copy = await reports.copy(created.id, { name: unique('copy'), description: '', visibility: 'public' })

      // then: 복사본 차트가 원본과 같고 목록 chartKind가 bar다
      expect(copy.chart).toEqual(CHART)
      expect((await reports.list()).find((r) => r.id === copy.id)?.chartKind).toBe('bar')
      await cleanup(created.id, copy.id)
    })

    // 테스트 코드: RC-105
    it('그룹 컬럼이 3개인 정의는 히스토그램도 막대도 chart-too-many-groups 하나로 거절하고 저장하지 않는다', async () => {
      // given: 그룹 컬럼 3개 + 집계 1개의 정의와 저장된 리포트 수
      const { reports } = await make('sales')
      const before = (await reports.list()).length
      const definition: ReportQueryInput = {
        columns: [{ field: 'deal.vendor', group: true }, { field: 'deal.status', group: true }, { field: 'deal.forecast', group: true }, { field: 'deal.amount', group: false, aggregate: 'sum' }],
        conditions: [],
        combine: 'and',
        rowLimit: 100,
      }

      // when: 히스토그램과 막대 차트로 각각 저장한다
      const histogram = await expectRejects(reports.create(input({ definition, chart: { ...CHART, kind: 'histogram', category: null, values: [3] } })), 422)
      const bar = await expectRejects(reports.create(input({ definition, chart: { ...CHART, values: [3] } })), 422)

      // then: 둘 다 `["chart"]` chart-too-many-groups 위반 하나이고 저장되지 않는다
      const expected = [{ location: ['chart'], code: 'chart-too-many-groups', message: '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다' }]
      expect(histogram.problem?.reportErrors).toEqual(expected)
      expect(bar.problem?.reportErrors).toEqual(expected)
      expect((await reports.list()).length).toBe(before)
    })

    // 테스트 코드: RC-105
    it('구간을 생략한 히스토그램은 자동 구간으로 저장되고 막대의 옵션은 기본값으로 읽힌다', async () => {
      // given: 그룹핑 없는 정의와 구간 설정이 null인 히스토그램
      const { reports } = await make('sales')
      const definition: ReportQueryInput = { columns: [{ field: 'deal.code', group: false }, { field: 'deal.amount', group: false }], conditions: [], combine: 'and', rowLimit: 100 }
      const histogram: ReportChartInput = { ...CHART, kind: 'histogram', category: null, values: [1], histogram: null }

      // when: 히스토그램 리포트와 막대 리포트를 저장한다
      const hist = await reports.create(input({ definition, chart: histogram }))
      const bar = await reports.create(input({ chart: CHART }))

      // then: 히스토그램은 auto 구간(나머지 null)이고 막대의 구간·합계·계열 설정은 null·false·null이다
      expect(hist.chart?.histogram).toEqual({ binMode: 'auto', binCount: null, binWidth: null, overflow: null, underflow: null })
      expect(bar.chart).toMatchObject({ histogram: null, showTotal: false, comboSeries: null })
      await cleanup(hist.id, bar.id)
    })

    // 테스트 코드: RC-105
    it('계열 설정을 생략한 콤보는 첫 값 막대와 보조 축 꺾은선으로 채워지고 보조 축 여부를 계산한다', async () => {
      // given: 값 열 2개의 정의와 계열 설정 없이 보조 축을 켠 콤보
      const { reports } = await make('sales')
      const definition: ReportQueryInput = {
        columns: [{ field: 'deal.vendor', group: true }, { field: 'deal.amount', group: false, aggregate: 'sum' }, { field: 'deal.users', group: false, aggregate: 'sum' }],
        conditions: [],
        combine: 'and',
        rowLimit: 100,
      }
      const combo: ReportChartInput = { ...CHART, kind: 'combo', values: [1, 2], secondaryAxis: true, comboSeries: null }

      // when: 콤보 리포트를 저장한다
      const created = await reports.create(input({ definition, chart: combo }))

      // then: 첫 값은 묶은 세로 막대, 둘째는 보조 축 꺾은선이고 보조 축 여부는 계열에서 계산한 true다
      expect(created.chart?.comboSeries).toEqual([{ type: 'column', secondary: false }, { type: 'line', secondary: true }])
      expect(created.chart?.secondaryAxis).toBe(true)
      expect(created.chart?.showTotal).toBe(false)
      await cleanup(created.id)
    })

    // 테스트 코드: RS-005
    it('빈 이름·긴 이름·긴 설명·NUL·알 수 없는 공개 범위는 서버 문구의 422 validation이다', async () => {
      // given: 로그인한 sales(빈 이름·긴 이름·긴 설명·NUL·알 수 없는 공개 범위는 서버 문구의 422 validation이다)
      const { reports } = await make('sales')
      // when: 빈 이름, 101자 이름, 1,001자 설명, 이름의 NUL, 설명의 NUL, 알 수 없는 공개 범위로 각각 저장한다
      const cases: [Partial<SavedReportInput>, string][] = [
        [{ name: '  ' }, '리포트 이름을 입력하세요.'],
        [{ name: 'a'.repeat(101) }, '리포트 이름은 100자 이내로 입력하세요.'],
        [{ description: 'a'.repeat(1001) }, '설명은 1,000자 이내로 입력하세요.'],
        [{ name: 'a\0b' }, '리포트 이름에는 NUL 문자를 쓸 수 없습니다'],
        [{ description: 'a\0b' }, '설명에는 NUL 문자를 쓸 수 없습니다'],
        [{ visibility: 'all' as 'public' }, '공개 범위는 public 또는 private입니다.'],
        [{ visibility: 'Public' as 'public' }, '공개 범위는 public 또는 private입니다.'],
      ]
      const errors = []
      for (const [over] of cases) errors.push(await expectRejects(reports.create(input(over)), 422))
      // then: 모두 422 validation이고 문구가 차례로 서버 문구다(NUL은 빈 이름·길이 문구가 아니다)
      expect(errors.map((e) => e.kind)).toEqual(cases.map(() => 'validation'))
      expect(errors.map((e) => e.message)).toEqual(cases.map(([, message]) => message))
    })

    // 테스트 코드: RS-021
    it('덮어쓰기는 404, 422, 403(공개 범위), 409 순서로 판정한다', async () => {
      // given: sales의 비공개 리포트 P와 revision이 2인 공개 리포트 R, 틀린 정의
      const hiddenReport = await createAs('sales', { visibility: 'private' })
      const publicReport = await createAs('sales')
      const owner = await make('sales')
      const bumped = await owner.reports.update(publicReport.id, { ...input({ name: publicReport.name }), revision: 1 })
      const wrongDefinition: ReportQueryInput = { columns: [{ field: 'deal.nope', group: false }], conditions: [], combine: 'and', rowLimit: 100 }
      const { reports } = await make('user')
      // when: user가 P를 틀린 정의·낡은 revision으로 덮어쓴다
      const hidden = await expectRejects(reports.update(hiddenReport.id, { ...input({ name: hiddenReport.name, definition: wrongDefinition }), revision: 99 }), 404)
      // then: 404 not-found다
      expect(hidden.kind).toBe('not-found')
      // when: R을 틀린 정의·다른 공개 범위·낡은 revision으로 덮어쓴다
      const invalid = await expectRejects(reports.update(publicReport.id, { ...input({ name: publicReport.name, visibility: 'private', definition: wrongDefinition }), revision: 1 }), 422)
      // then: 422 invalid-report다
      expect(invalid.kind).toBe('invalid-report')
      // when: R을 맞는 정의·다른 공개 범위·낡은 revision으로 덮어쓴다
      const visibility = await expectRejects(reports.update(publicReport.id, { ...input({ name: publicReport.name, visibility: 'private' }), revision: 1 }), 403)
      // then: 409가 아니라 공개 범위 403이다
      expect(visibility.kind).toBe('forbidden')
      // when: 같은 공개 범위·낡은 revision으로 덮어쓴다
      const stale = await expectRejects(reports.update(publicReport.id, { ...input({ name: publicReport.name }), revision: 1 }), 409)
      // then: 409 invalid-state이고 리포트는 바뀌지 않았다
      expect(stale.kind).toBe('invalid-state')
      expect(await reports.get(publicReport.id)).toMatchObject({ revision: bumped.revision, name: publicReport.name })
      await cleanup(hiddenReport.id, publicReport.id)
    })

    it('로그인하지 않은 방문자는 모든 메서드가 401이다', async () => {
      // given: 로그아웃한 게이트웨이
      const gateway = await make('user')
      await gateway.auth.logout()

      // when·then: 목록·상세·만들기·실행이 모두 401이다
      await expectRejects(gateway.reports.list(), 401)
      await expectRejects(gateway.reports.get(1), 401)
      await expectRejects(gateway.reports.create(input()), 401)
      await expectRejects(gateway.reports.run(1), 401)
    })

    describe('결과 배치', () => {
      it('저장한 배치를 그대로 다시 읽는다', async () => {
        // given: 로그인한 sales(저장한 배치를 그대로 다시 읽는다)
        const { reports } = await make('sales')

        // when: CHART_SIDE 배치로 저장하고 다시 읽는다
        const created = await reports.create(input({ layout: SIDE_LAYOUT }))

        // then: 응답과 상세의 배치가 같다
        expect(created.layout).toEqual(SIDE_LAYOUT)
        expect((await reports.get(created.id)).layout).toEqual(SIDE_LAYOUT)
        await cleanup(created.id)
      })

      it('기본 배치로 저장하면 기본 배치로 읽힌다', async () => {
        // given: 로그인한 sales(기본 배치로 저장하면 기본 배치로 읽힌다)
        const { reports } = await make('sales')

        // when: 기본 배치로 저장한다
        const created = await reports.create(input())

        // then: 기본 배치다
        expect(created.layout).toEqual(DEFAULT_LAYOUT)
        await cleanup(created.id)
      })

      it('덮어쓰기는 배치를 바꾸고 저장된 배치를 그대로 보내면 유지한다', async () => {
        // given: CHART_SIDE 배치의 리포트
        const { reports } = await make('sales')
        const created = await reports.create(input({ layout: SIDE_LAYOUT }))

        // when: 저장된 배치로 덮어쓰고, 이어서 TABLE_ONLY로 덮어쓴다
        const same = await reports.update(created.id, { ...input({ name: created.name, layout: created.layout }), revision: created.revision })
        const replaced = await reports.update(created.id, { ...input({ name: created.name, layout: TABLE_LAYOUT }), revision: same.revision })

        // then: 앞은 배치가 그대로, 뒤는 TABLE_ONLY에 revision 3이다
        expect(same.layout).toEqual(SIDE_LAYOUT)
        expect(replaced).toMatchObject({ revision: 3, layout: TABLE_LAYOUT })
        await cleanup(created.id)
      })

      it('복제본은 원본의 배치를 가진다', async () => {
        // given: CHART_SIDE 배치의 sales 리포트와 user 로그인
        const created = await createAs('sales', { layout: SIDE_LAYOUT })
        const { reports } = await make('user')

        // when: 복제한다
        const copy = await reports.copy(created.id, { name: unique('copy'), description: '', visibility: 'public' })

        // then: 복제본의 배치가 원본과 같다
        expect(copy.layout).toEqual(SIDE_LAYOUT)
        await cleanup(created.id, copy.id)
      })

      it('배치만 저장하면 revision과 최종 수정자만 바뀌고 정의·차트는 그대로다', async () => {
        // given: 차트가 있는 sales의 공개 리포트와 user 로그인
        const created = await createAs('sales', { chart: CHART })
        const { reports } = await make('user')
        const me = await (await make('user')).auth.me()

        // when: user가 배치만 저장한다
        const saved = await reports.saveReportLayout(created.id, { layout: SIDE_LAYOUT, revision: created.revision })
        const reread = await reports.get(created.id)

        // then: revision 2, 배치·최종 수정자만 바뀌고 정의·SQL·차트·만든 사람은 그대로다
        expect(saved).toMatchObject({ revision: 2, layout: SIDE_LAYOUT, name: created.name, visibility: 'public', chart: CHART })
        expect(saved.definition).toEqual(DEFINITION)
        expect(saved.generatedSql).toBe(created.generatedSql)
        expect(saved.owner.id).toBe(created.owner.id)
        expect(saved.updatedBy.id).toBe(me.id)
        expect(reread).toEqual(saved)
        await cleanup(created.id)
      })

      it('직전 응답의 revision으로 배치를 이어 저장하면 모두 된다', async () => {
        // given: 새 리포트
        const { reports } = await make('sales')
        const created = await reports.create(input())

        // when: 직전 응답의 revision으로 세 번 저장한다
        const first = await reports.saveReportLayout(created.id, { layout: SIDE_LAYOUT, revision: created.revision })
        const second = await reports.saveReportLayout(created.id, { layout: TABLE_LAYOUT, revision: first.revision })
        const third = await reports.saveReportLayout(created.id, { layout: DEFAULT_LAYOUT, revision: second.revision })

        // then: revision이 2, 3, 4이고 마지막 배치가 저장된다
        expect([first.revision, second.revision, third.revision]).toEqual([2, 3, 4])
        expect((await reports.get(created.id)).layout).toEqual(DEFAULT_LAYOUT)
        await cleanup(created.id)
      })

      it('낡은 revision의 배치 저장은 409 invalid-state이고 배치는 그대로다', async () => {
        // given: 배치를 한 번 저장해 revision 2가 된 리포트
        const { reports } = await make('sales')
        const created = await reports.create(input({ layout: SIDE_LAYOUT }))
        await reports.saveReportLayout(created.id, { layout: TABLE_LAYOUT, revision: 1 })

        // when: revision 1로 다시 저장한다
        const stale = await expectRejects(reports.saveReportLayout(created.id, { layout: DEFAULT_LAYOUT, revision: 1 }), 409)

        // then: 409 invalid-state이고 저장된 배치가 남는다
        expect(stale.kind).toBe('invalid-state')
        expect(await reports.get(created.id)).toMatchObject({ revision: 2, layout: TABLE_LAYOUT })
        await cleanup(created.id)
      })

      it('남의 비공개 리포트의 배치 저장은 없는 id와 같은 404다', async () => {
        // given: sales의 비공개 리포트와 user 로그인
        const created = await createAs('sales', { visibility: 'private' })
        const { reports } = await make('user')

        // when: 비공개 리포트와 없는 id에 배치를 저장한다
        const hidden = await expectRejects(reports.saveReportLayout(created.id, { layout: TABLE_LAYOUT, revision: 1 }), 404)
        const missing = await expectRejects(reports.saveReportLayout(NO_SUCH_ID, { layout: TABLE_LAYOUT, revision: 1 }), 404)

        // then: 둘 다 404이고 문구가 같다
        expect(hidden.kind).toBe('not-found')
        expect(hidden.message).toBe(missing.message)
        expect(hidden.message).toBe(NOT_FOUND)
        await cleanup(created.id)
      })

      it('admin은 남의 비공개 리포트의 배치도 저장한다', async () => {
        // given: sales의 비공개 리포트와 admin 로그인
        const created = await createAs('sales', { visibility: 'private' })
        const { reports } = await make('admin')

        // when: 배치를 저장한다
        const saved = await reports.saveReportLayout(created.id, { layout: TABLE_LAYOUT, revision: 1 })

        // then: 저장되고 만든 사람은 그대로다
        expect(saved).toMatchObject({ revision: 2, layout: TABLE_LAYOUT })
        expect(saved.owner.id).toBe(created.owner.id)
        await cleanup(created.id)
      })

      it.each([
        ['view', { ...DEFAULT_LAYOUT, view: 'grid' }],
        ['order', { ...DEFAULT_LAYOUT, order: ['table', 'table'] }],
        ['arrange', { ...DEFAULT_LAYOUT, arrange: 'row' }],
      ] as const)('%s이 틀린 배치는 그 위치와 함께 422로 거절하고 저장하지 않는다', async (field, layout) => {
        // given: CHART_SIDE 배치의 리포트
        const { reports } = await make('sales')
        const created = await reports.create(input({ layout: SIDE_LAYOUT }))

        // when: 틀린 배치로 배치 저장과 만들기를 한다
        const onSave = await expectRejects(reports.saveReportLayout(created.id, { layout: layout as unknown as ReportLayout, revision: 1 }), 422)
        const onCreate = await expectRejects(reports.create(input({ layout: layout as unknown as ReportLayout })), 422)

        // then: 둘 다 [layout, 항목] 위치의 invalid-report이고 리포트는 그대로다
        expect(onSave.kind).toBe('invalid-report')
        expect(onSave.problem?.reportErrors?.map((e) => e.location)).toEqual([['layout', field]])
        expect(onCreate.problem?.reportErrors?.map((e) => e.location)).toEqual([['layout', field]])
        expect(await reports.get(created.id)).toMatchObject({ revision: 1, layout: SIDE_LAYOUT })
        await cleanup(created.id)
      })
    })
  })
}
