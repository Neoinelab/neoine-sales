import { describe, expect, it } from 'vitest'
import type { SeedFactory } from '..'
import { seedVendorId } from '../../fixtures/vendors'
import { buildSampleSeed } from '../../fixtures/sampleSeed'
import { SNAPSHOT_COMMIT_NAME, SNAPSHOT_PERIOD, SNAPSHOT_TAKEN_AT } from '../../fixtures/forecastSnapshot'
import { USER_ID } from '../seed/ids'
import { dealInput, expectApiError, mockAs } from '../testing'
import { SNAPSHOT_NOT_FOUND } from './forecastSnapshots'

/** P6 R2: Fake의 스냅숏 규칙은 서버(`GET /forecast/snapshots*`)와 같다. 이 테스트가 그 규칙을 고정한다. */

describe('forecast.snapshots (목록)', () => {
  it('lists the stored snapshot with its period and creation time', async () => {
    const { gateway } = await mockAs('kim')

    expect(await gateway.forecast.snapshots()).toEqual([{ period: SNAPSHOT_PERIOD, takenAt: SNAPSHOT_TAKEN_AT }])
  })

  it('lists the newest period first', async () => {
    const seed: SeedFactory = (clock) => {
      const data = buildSampleSeed(clock)
      const [first] = data.forecastSnapshots ?? []
      if (!first) throw new Error('샘플 시드에 스냅숏이 있어야 합니다.')
      data.forecastSnapshots = [
        { ...first, period: '2026-07', takenAt: '2026-08-01T00:05:00+09:00' },
        first,
        { ...first, period: '2025-12', takenAt: '2026-01-01T00:05:00+09:00' },
      ]
      return data
    }
    const { gateway } = await mockAs('kim', { seed })

    expect((await gateway.forecast.snapshots()).map((s) => s.period)).toEqual(['2026-09', '2026-07', '2025-12'])
  })

  it('is empty without stored snapshots', async () => {
    const { gateway } = await mockAs('kim', { seed: (clock) => ({ ...buildSampleSeed(clock), forecastSnapshots: [] }) })

    expect(await gateway.forecast.snapshots()).toEqual([])
  })

  it.each(['root', 'kim', 'park', 'lee', 'jung', 'han'] as const)('lets every seed user read the list (%s)', async (login) => {
    const { gateway } = await mockAs(login)

    expect(await gateway.forecast.snapshots()).toHaveLength(1)
  })

  it('needs a login', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.forecast.snapshots(), 401)
  })
})

describe('forecast.snapshotSummary', () => {
  it('has the snapshot basis, the creation time as asOf and the period', async () => {
    const { gateway } = await mockAs('kim')

    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    expect(summary.basis).toBe('snapshot')
    expect(summary.asOf).toBe(SNAPSHOT_TAKEN_AT)
    expect(summary.snapshotPeriod).toBe(SNAPSHOT_PERIOD)
    expect(summary.query).toEqual({ year: 2026, quarter: 3 })
  })

  it('builds the columns from the stored cells: stored names, code order, no Lost, no unused codes', async () => {
    const { gateway } = await mockAs('kim')

    const { columns } = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    expect(columns.map((c) => [c.key, c.name, c.outcome, c.order])).toEqual([
      ['pipeline', 'Pipeline', 'open', 1],
      ['best', 'Best', 'open', 2],
      ['commit', SNAPSHOT_COMMIT_NAME, 'open', 4],
      ['won', 'Won', 'won', 5],
    ])
  })

  it('keeps the same columns whichever period is asked', async () => {
    const { gateway } = await mockAs('kim')

    const q3 = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })
    const empty = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2031 })

    expect(empty.columns).toEqual(q3.columns)
    expect(empty.rows).toEqual([])
    expect(empty.totalRow.total).toEqual({ count: 0, amount: 0 })
  })

  it('sums the stored months of the quarter per owner and leaves Lost out', async () => {
    const { gateway } = await mockAs('kim')

    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([
      [USER_ID.kim, '김영업'],
      [USER_ID.park, '박영업'],
    ])
    const [kim, park] = summary.rows
    expect(kim?.cells).toEqual({
      pipeline: { count: 2, amount: 200_000_000 },
      best: { count: 0, amount: 0 },
      commit: { count: 1, amount: 50_000_000 },
      won: { count: 1, amount: 700_000_000 },
    })
    expect(kim?.total).toEqual({ count: 3, amount: 250_000_000 })
    expect(park?.total).toEqual({ count: 1, amount: 30_000_000 })
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계' })
    expect(summary.totalRow.total).toEqual({ count: 4, amount: 280_000_000 })
    expect(summary.totalRow.cells.won).toEqual({ count: 1, amount: 700_000_000 })
  })

  it('takes only the asked month or quarter', async () => {
    const { gateway } = await mockAs('kim')

    const august = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, month: 8 })
    const q4 = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 4 })
    const year = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026 })

    expect(august.totalRow.total).toEqual({ count: 2, amount: 200_000_000 })
    expect(q4.totalRow.total).toEqual({ count: 1, amount: 5_000_000 })
    expect(year.totalRow.total).toEqual({ count: 5, amount: 285_000_000 })
  })

  it('keeps only the asked owner', async () => {
    const { gateway } = await mockAs('kim')

    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, ownerId: USER_ID.park })

    expect(summary.rows.map((r) => r.ownerId)).toEqual([USER_ID.park])
    expect(summary.totalRow.total).toEqual({ count: 1, amount: 30_000_000 })
  })

  it('does not change when deals change afterwards, while the live summary does', async () => {
    const { gateway } = await mockAs('kim')
    const before = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '스냅숏 뒤 Deal', revenueDate: '2026-08-20', forecastKey: 'commit', revenueAmount: 9_000_000 }))

    const after = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })
    const live = await gateway.forecast.summary({ year: 2026, quarter: 3 })

    expect(after.rows).toEqual(before.rows)
    expect(after.totalRow).toEqual(before.totalRow)
    expect(live.basis).toBe('live')
    expect(live.snapshotPeriod).toBeNull()
    expect(live.columns.find((c) => c.key === 'commit')?.name).toBe('Commit') // 현재 이름, 스냅숏은 당시 이름
  })

  it('orders resigned owners after active ones with the 퇴사 label', async () => {
    const seed: SeedFactory = (clock) => {
      const data = buildSampleSeed(clock)
      const first = data.forecastSnapshots?.[0]
      if (!first) throw new Error('샘플 시드에 스냅숏이 있어야 합니다.')
      const resigned = data.users.find((u) => u.status === 'resigned')
      if (!resigned) throw new Error('샘플 시드에 퇴사자가 있어야 합니다.')
      const template = first.cells.find((c) => c.forecastKey === 'pipeline')
      if (!template) throw new Error('샘플 시드의 pipeline 셀')
      data.forecastSnapshots = [{ ...first, cells: [{ ...template, ownerId: resigned.id, revenueMonth: 7 }, ...first.cells] }]
      return data
    }
    const { gateway } = await mockAs('kim', { seed })

    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    expect(summary.rows.map((r) => r.ownerName).at(-1)).toMatch(/\(퇴사\)$/)
    expect(summary.rows.slice(0, -1).every((r) => !r.ownerName.endsWith('(퇴사)'))).toBe(true)
  })

  it('answers 404 for a period without a snapshot or with a wrong format', async () => {
    const { gateway } = await mockAs('kim')

    for (const period of ['2026-08', '2027-01', '2026-9', 'abc', '2026-13']) {
      await expectApiError(gateway.forecast.snapshotSummary(period, { year: 2026 }), 404, SNAPSHOT_NOT_FOUND)
    }
  })

  it('answers 422 for a vendor condition: a snapshot has no vendor', async () => {
    const { gateway } = await mockAs('kim')
    const query = { year: 2026, vendorId: seedVendorId('Silverfort') }

    await expectApiError(gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, query), 422)
  })

  it('answers 422 when a quarter and a month are asked together', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 1, month: 1 }),
      422,
      'Quarter와 월은 함께 선택할 수 없습니다.',
    )
  })

  it('needs a login', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026 }), 401)
  })
})
