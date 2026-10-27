/**
 * 저장 리포트 계약(Reports 3단계 G4~G6와 AC1~10). mock과 실제 서버가 같은 모양·같은 권한으로 답해야 한다.
 * 호출마다 고유한 이름을 쓰고 만든 것은 admin으로 치운다. 역할을 바꿀 때는 그 역할의 `make`를 다시 부른다(mock은 세션이 하나).
 */

import { describe, expect, it } from 'vitest'
import type { ReportChartInput, ReportQueryInput, SavedReportInput } from '../../shared/model/reportTypes'
import { expectRejects, NO_SUCH_ID, unique, type ContractRole, type MakeGateway } from './support'

const DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.vendor', format: 'name', group: true },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', label: '금액 합계' },
  ],
  conditions: [{ field: 'deal.amount', operator: 'gte', value: 1_500_000 }],
  combine: 'and',
  sort: { column: 1, direction: 'desc' },
  rowLimit: 1000,
}

const OTHER_DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.code', format: 'as_is', group: false },
    { field: 'action.action', format: 'as_is', group: false },
  ],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

const NOT_FOUND = '리포트를 찾을 수 없습니다.'

/** DEFINITION(0: Vendor 그룹, 1: 금액 합계)에 맞는 누적 막대 아닌 세로 막대 차트(Reports 4단계). */
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
}

const input = (over: Partial<SavedReportInput> = {}): SavedReportInput => ({
  name: unique('rpt'),
  description: '계약 시험',
  visibility: 'public',
  definition: DEFINITION,
  chart: null,
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

  describe('saved reports 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('lets %s save a report as its owner at revision 1 (AC1, AC19)', async (role) => {
      const gateway = await make(role)
      const me = await gateway.auth.me()
      const body = input({ name: `  ${unique('rpt')}  `, description: '  설명  ' })

      const created = await gateway.reports.create(body)

      expect(created).toMatchObject({ revision: 1, visibility: 'public', description: '설명', entities: ['deal'] })
      expect(created.name).toBe(body.name.trim())
      expect(created.owner.id).toBe(me.id)
      expect(created.updatedBy.id).toBe(me.id)
      expect(created.definition).toEqual(DEFINITION)
      expect(created.generatedSql.length).toBeGreaterThan(0)
      expect(created.createdAt).toBeTruthy()
      await cleanup(created.id)
    })

    it('lists Deal and Actions as the data of a report that uses an Action field', async () => {
      const created = await createAs('sales', { definition: OTHER_DEFINITION })

      const { reports } = await make('sales')
      const listed = (await reports.list()).find((r) => r.id === created.id)

      expect(listed?.entities).toEqual(['deal', 'action'])
      await cleanup(created.id)
    })

    it('rejects an empty name, a long name, a long description and an unknown visibility with 422 (AC2)', async () => {
      const { reports } = await make('sales')

      const empty = await expectRejects(reports.create(input({ name: '   ' })), 422)
      const long = await expectRejects(reports.create(input({ name: 'a'.repeat(101) })), 422)
      const description = await expectRejects(reports.create(input({ description: 'a'.repeat(1001) })), 422)
      const visibility = await expectRejects(reports.create(input({ visibility: 'shared' as 'public' })), 422)

      for (const error of [empty, long, description, visibility]) expect(error.kind).toBe('validation')
    })

    it('accepts the longest name and description (AC2)', async () => {
      const { reports } = await make('sales')
      const name = unique('r').padEnd(100, 'x')

      const created = await reports.create(input({ name, description: 'd'.repeat(1000) }))

      expect(created.name).toHaveLength(100)
      expect(created.description).toHaveLength(1000)
      await cleanup(created.id)
    })

    it('does not save a report whose definition breaks a rule and lists every violation (AC2)', async () => {
      const { reports } = await make('sales')
      const before = (await reports.list()).length
      const broken: ReportQueryInput = {
        columns: [{ field: 'deal.nope', format: 'as_is', group: false }, { field: 'deal.nada', format: 'as_is', group: false }],
        conditions: [],
        combine: 'and',
        rowLimit: 100,
      }

      const error = await expectRejects(reports.create(input({ definition: broken })), 422)

      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toHaveLength(2)
      expect((await reports.list()).length).toBe(before)
    })

    it('rejects the same name of any report ignoring case, whoever owns it (AC3, G6)', async () => {
      const name = unique('Rpt')
      const first = await createAs('sales', { name })
      const sales = await make('sales')
      const user = await make('user')

      const duplicate = await expectRejects(sales.reports.create(input({ name: name.toUpperCase() })), 409)
      const other = await expectRejects(user.reports.create(input({ name: name.toLowerCase() })), 409)

      expect(duplicate.kind).toBe('already-exists')
      expect(other.kind).toBe('already-exists')
      await cleanup(first.id)
    })

    it('rejects the name of a private report of someone else too (AC3)', async () => {
      const name = unique('Priv')
      const hidden = await createAs('sales', { name, visibility: 'private' })
      const user = await make('user')

      const error = await expectRejects(user.reports.create(input({ name })), 409)

      expect(error.kind).toBe('already-exists')
      await cleanup(hidden.id)
    })

    it('lists newest changes first and tells nobody else private reports (AC4, AC5)', async () => {
      const older = await createAs('sales')
      const newer = await createAs('sales')
      const hidden = await createAs('sales', { visibility: 'private' })

      const asSales = (await (await make('sales')).reports.list()).map((r) => r.id)
      const asUser = (await (await make('user')).reports.list()).map((r) => r.id)
      const asAdmin = (await (await make('admin')).reports.list()).map((r) => r.id)

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
    ] as const)('hides others private reports as not found for every request (%s owner, %s viewer, G4)', async (owner, viewer) => {
      const created = await createAs(owner, { visibility: 'private' })
      const { reports } = await make(viewer)
      const body = { ...input(), revision: 1 }

      const errors = [
        await expectRejects(reports.get(created.id), 404),
        await expectRejects(reports.update(created.id, body), 404),
        await expectRejects(reports.remove(created.id), 404),
        await expectRejects(reports.copy(created.id, { name: unique('c'), description: '', visibility: 'public' }), 404),
        await expectRejects(reports.run(created.id), 404),
      ]
      const missing = await expectRejects(reports.get(NO_SUCH_ID), 404)

      for (const error of errors) {
        expect(error.kind).toBe('not-found')
        expect(error.message).toBe(missing.message)
      }
      expect(missing.message).toBe(NOT_FOUND)
      await cleanup(created.id)
    })

    it('lets an admin see, change and delete the private report of someone else (AC5, AC7, AC9)', async () => {
      const created = await createAs('sales', { visibility: 'private' })
      const { reports } = await make('admin')

      const seen = await reports.get(created.id)
      const changed = await reports.update(created.id, { ...input({ name: seen.name, visibility: 'public' }), revision: seen.revision })
      await reports.remove(created.id)

      expect(seen.id).toBe(created.id)
      expect(changed.visibility).toBe('public')
      expect(changed.owner.id).toBe(created.owner.id)
      await expectRejects(reports.get(created.id), 404)
    })

    it('hides what does not exist the same way (AC5)', async () => {
      const { reports } = await make('sales')

      await expectRejects(reports.get(NO_SUCH_ID), 404, NOT_FOUND)
      await expectRejects(reports.remove(NO_SUCH_ID), 404, NOT_FOUND)
      await expectRejects(reports.run(NO_SUCH_ID), 404, NOT_FOUND)
    })

    it('lets another role edit and copy a public report but not delete it or change its visibility (AC7, AC9, AC10, G4)', async () => {
      const created = await createAs('sales')
      const { reports } = await make('user')
      const me = await (await make('user')).auth.me()

      const edited = await reports.update(created.id, { ...input({ name: created.name, description: '다른 사람이 고침', definition: OTHER_DEFINITION }), revision: created.revision })
      const visibility = await expectRejects(
        reports.update(created.id, { ...input({ name: created.name, visibility: 'private' }), revision: edited.revision }),
        403,
      )
      const deletion = await expectRejects(reports.remove(created.id), 403)
      const copy = await reports.copy(created.id, { name: unique('copy'), description: '복제', visibility: 'private' })

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

    it('lets the owner change the visibility of a public report and delete private or public ones (AC7, AC9)', async () => {
      const first = await createAs('sales')
      const second = await createAs('sales', { visibility: 'private' })
      const { reports } = await make('sales')

      const changed = await reports.update(first.id, { ...input({ name: first.name, visibility: 'private' }), revision: 1 })
      await reports.remove(first.id)
      await reports.remove(second.id)

      expect(changed.visibility).toBe('private')
      await expectRejects(reports.get(first.id), 404)
      await expectRejects(reports.get(second.id), 404)
    })

    it('overwrites name, description and definition, bumps the revision and keeps the owner (AC7)', async () => {
      const created = await createAs('sales')
      const { reports } = await make('sales')
      const name = unique('renamed')

      const updated = await reports.update(created.id, { name, description: '', visibility: 'public', definition: OTHER_DEFINITION, chart: null, revision: created.revision })
      const reread = await reports.get(created.id)

      expect(updated).toMatchObject({ id: created.id, name, description: '', revision: 2, entities: ['deal', 'action'] })
      expect(updated.owner.id).toBe(created.owner.id)
      expect(reread.definition).toEqual(OTHER_DEFINITION)
      expect(reread.revision).toBe(2)
      await cleanup(created.id)
    })

    it('rejects a stale revision with invalid-state and changes nothing (AC8, G5)', async () => {
      const created = await createAs('sales')
      const { reports } = await make('sales')
      await reports.update(created.id, { ...input({ name: created.name, description: '먼저 저장' }), revision: 1 })

      const stale = await expectRejects(reports.update(created.id, { ...input({ name: created.name, description: '늦은 저장' }), revision: 1 }), 409)
      const reread = await reports.get(created.id)

      expect(stale.kind).toBe('invalid-state')
      expect(reread).toMatchObject({ description: '먼저 저장', revision: 2 })
      await cleanup(created.id)
    })

    it('rejects renaming onto another report (AC3)', async () => {
      const first = await createAs('sales')
      const second = await createAs('sales')
      const { reports } = await make('sales')

      const error = await expectRejects(reports.update(second.id, { ...input({ name: first.name.toUpperCase() }), revision: 1 }), 409)
      const keepsName = await reports.update(second.id, { ...input({ name: second.name.toUpperCase() }), revision: 1 })

      expect(error.kind).toBe('already-exists')
      expect(keepsName.revision).toBe(2)
      await cleanup(first.id, second.id)
    })

    it('rejects a duplicate name when an editor renames a report onto one of the owner (AC3)', async () => {
      const first = await createAs('sales')
      const second = await createAs('sales')
      const { reports } = await make('user')

      const error = await expectRejects(reports.update(second.id, { ...input({ name: first.name }), revision: 1 }), 409)

      expect(error.kind).toBe('already-exists')
      await cleanup(first.id, second.id)
    })

    it('copies with the source definition, a new owner and revision 1, and rejects a duplicate name (AC10)', async () => {
      const created = await createAs('sales', { definition: OTHER_DEFINITION })
      const { reports } = await make('admin')
      const me = await (await make('admin')).auth.me()
      const name = unique('copy')

      const copy = await reports.copy(created.id, { name, description: '', visibility: 'public' })
      const duplicate = await expectRejects(reports.copy(created.id, { name: name.toUpperCase(), description: '', visibility: 'public' }), 409)

      expect(copy.id).not.toBe(created.id)
      expect(copy).toMatchObject({ name, revision: 1, definition: OTHER_DEFINITION })
      expect(copy.owner.id).toBe(me.id)
      expect(duplicate.kind).toBe('already-exists')
      await cleanup(created.id, copy.id)
    })

    it('runs the stored definition with the same shape as a query (AC6)', async () => {
      const created = await createAs('sales')
      const { reports } = await make('user')

      const run = await reports.run(created.id)
      const query = await reports.query(DEFINITION)

      expect(run.columns.map((c) => [c.field, c.group, c.aggregate])).toEqual(query.columns.map((c) => [c.field, c.group, c.aggregate]))
      expect(run.rows.length).toBe(query.rows.length)
      expect(run.totals === null).toBe(query.totals === null)
      expect(run.rowLimit).toBe(1000)
      await cleanup(created.id)
    })

    it('deletes physically so the report is gone for everyone (AC9)', async () => {
      const created = await createAs('user')
      const { reports } = await make('admin')

      await reports.remove(created.id)

      await expectRejects(reports.get(created.id), 404)
      expect((await reports.list()).map((r) => r.id)).not.toContain(created.id)
    })

    it('keeps the chart of a saved report, lists its kind and reads no problem (4단계 AC1, AC8, AC18, G3)', async () => {
      const { reports } = await make('sales')

      const created = await reports.create(input({ chart: { ...CHART, title: '  Vendor별 금액  ' } }))

      expect(created.chart).toEqual(CHART)
      expect(created.chartProblem).toBeNull()
      expect((await reports.get(created.id)).chart).toEqual(CHART)
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBe('bar')
      await cleanup(created.id)
    })

    it('saves without a chart as null and lists no chart kind (4단계 AC1, AC9)', async () => {
      const { reports } = await make('sales')

      const created = await reports.create(input())

      expect(created.chart).toBeNull()
      expect(created.chartProblem).toBeNull()
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBeNull()
      await cleanup(created.id)
    })

    it('changes only the chart on overwrite, bumps the revision and clears it with null (4단계 AC1, AC5)', async () => {
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      const changed = await reports.update(created.id, { ...input({ name: created.name, chart: { ...CHART, kind: 'line', title: '추이' } }), revision: created.revision })
      const cleared = await reports.update(created.id, { ...input({ name: created.name, chart: null }), revision: changed.revision })

      expect(changed).toMatchObject({ revision: 2, chart: { kind: 'line', title: '추이' } })
      expect(cleared).toMatchObject({ revision: 3, chart: null })
      expect((await reports.list()).find((r) => r.id === created.id)?.chartKind).toBeNull()
      await cleanup(created.id)
    })

    it('rejects a chart whose category is not a group column with its location and saves nothing (4단계 AC2, AC4)', async () => {
      const { reports } = await make('sales')
      const before = (await reports.list()).length

      const error = await expectRejects(reports.create(input({ chart: { ...CHART, category: 1 } })), 422)

      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors?.[0]?.location).toEqual(['chart', 'category'])
      expect((await reports.list()).length).toBe(before)
    })

    it('rejects a chart for a definition without grouping at the chart location (4단계 AC2, AC4)', async () => {
      const { reports } = await make('sales')

      const error = await expectRejects(reports.create(input({ definition: OTHER_DEFINITION, chart: CHART })), 422)

      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors?.[0]?.location).toEqual(['chart'])
    })

    it('rejects an overwrite whose chart no longer fits the new definition and keeps the stored one (4단계 AC4)', async () => {
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      const error = await expectRejects(reports.update(created.id, { ...input({ name: created.name, definition: OTHER_DEFINITION, chart: CHART }), revision: created.revision }), 422)

      expect(error.kind).toBe('invalid-report')
      expect(await reports.get(created.id)).toMatchObject({ revision: 1, chart: CHART })
      await cleanup(created.id)
    })

    it('copies the chart together with the definition (4단계 AC6)', async () => {
      const { reports } = await make('sales')
      const created = await reports.create(input({ chart: CHART }))

      const copy = await reports.copy(created.id, { name: unique('copy'), description: '', visibility: 'public' })

      expect(copy.chart).toEqual(CHART)
      expect((await reports.list()).find((r) => r.id === copy.id)?.chartKind).toBe('bar')
      await cleanup(created.id, copy.id)
    })

    it('refuses an anonymous visitor (AC1)', async () => {
      const gateway = await make('user')
      await gateway.auth.logout()

      await expectRejects(gateway.reports.list(), 401)
      await expectRejects(gateway.reports.get(1), 401)
      await expectRejects(gateway.reports.create(input()), 401)
      await expectRejects(gateway.reports.run(1), 401)
    })
  })
}
