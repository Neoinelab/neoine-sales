import { describe, expect, it } from 'vitest'
import type { SeedFactory } from '..'
import { seedVendorId } from '../../fixtures/vendors'
import { buildSampleSeed } from '../../fixtures/sampleSeed'
import { SNAPSHOT_COMMIT_NAME, SNAPSHOT_PERIOD, SNAPSHOT_TAKEN_AT } from '../../fixtures/forecastSnapshot'
import { USER_ID } from '../seed/ids'
import { dealInput, expectApiError, mockAs } from '../testing'
import { snapshotNotFoundMessage } from './forecastSnapshots'

/** Fake의 스냅숏 규칙은 서버(`GET /forecast/snapshots*`)와 같다(FC-R36). 이 테스트가 그 규칙을 고정한다. */

describe('forecast.snapshots (목록)', () => {
  it('저장된 스냅숏의 기준 월과 생성 시각을 돌려준다', async () => {
    // given: 2026-09 스냅숏이 있는 Fake
    const { gateway } = await mockAs('kim')

    // when: 스냅숏 목록을 읽는다
    const list = await gateway.forecast.snapshots()

    // then: 기준 월과 생성 시각이 나온다
    expect(list).toEqual([{ period: SNAPSHOT_PERIOD, takenAt: SNAPSHOT_TAKEN_AT }])
  })

  it('기준 월 최근 순으로 돌려준다', async () => {
    // given: 2026-07, 2026-09, 2025-12 스냅숏
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

    // when: 목록을 읽는다
    const periods = (await gateway.forecast.snapshots()).map((s) => s.period)

    // then: 2026-09, 2026-07, 2025-12 순이다
    expect(periods).toEqual(['2026-09', '2026-07', '2025-12'])
  })

  it('저장된 스냅숏이 없으면 빈 목록이다', async () => {
    // given: 스냅숏이 없는 시드
    const { gateway } = await mockAs('kim', { seed: (clock) => ({ ...buildSampleSeed(clock), forecastSnapshots: [] }) })

    // when: 목록을 읽는다
    const list = await gateway.forecast.snapshots()

    // then: 비어 있다
    expect(list).toEqual([])
  })

  it.each(['root', 'kim', 'park', 'lee', 'jung', 'han'] as const)('시드 사용자 모두 목록을 읽을 수 있다 (%s)', async (login) => {
    // given: 해당 사용자로 로그인한 Fake
    const { gateway } = await mockAs(login)

    // when: 목록을 읽는다
    const list = await gateway.forecast.snapshots()

    // then: 스냅숏 1건이 보인다
    expect(list).toHaveLength(1)
  })

  it('로그인이 필요하다', async () => {
    // given: 로그인하지 않은 Fake
    const { gateway } = await mockAs(null)

    // when·then: 목록을 읽으면 401이다
    await expectApiError(gateway.forecast.snapshots(), 401)
  })
})

describe('forecast.snapshotSummary', () => {
  it('basis snapshot, 생성 시각을 asOf로, 기준 월을 담는다', async () => {
    // given: 2026-09 스냅숏이 있는 Fake
    const { gateway } = await mockAs('kim')

    // when: 2026 Q3 요약을 읽는다
    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: basis·asOf·기준 월·조건이 나온다
    expect(summary.basis).toBe('snapshot')
    expect(summary.asOf).toBe(SNAPSHOT_TAKEN_AT)
    expect(summary.snapshotPeriod).toBe(SNAPSHOT_PERIOD)
    expect(summary.query).toEqual({ year: 2026, quarter: 3 })
  })

  it('열은 저장된 코드 목록이다: 저장 당시 이름, 저장 order 순, Lost 없음, Deal 없던 코드도 0건 열', async () => {
    // given: Most Likely 셀이 없는 스냅숏
    const { gateway } = await mockAs('kim')

    // when: 2026 Q3 요약을 읽는다
    const { columns, totalRow } = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: Most Likely도 0건 열로 있고 commit은 저장 당시 이름이다
    expect(columns.map((c) => [c.key, c.name, c.outcome, c.order])).toEqual([
      ['pipeline', 'Pipeline', 'open', 1],
      ['best', 'Best', 'open', 2],
      ['most_likely', 'Most Likely', 'open', 3],
      ['commit', SNAPSHOT_COMMIT_NAME, 'open', 4],
      ['won', 'Won', 'won', 5],
    ])
    expect(totalRow.cells.most_likely).toEqual({ count: 0, amount: 0 })
  })

  it('저장 뒤 현재 코드가 바뀌어도 열은 저장 당시 목록이다', async () => {
    // given: 저장된 열에 없는 코드를 현재 코드로 추가하고 commit 이름을 바꾼 Fake
    const { gateway } = await mockAs('root')
    await gateway.codes.create({ kind: 'forecast', name: 'Verbal', probabilityHint: null })
    const commit = (await gateway.codes.list('forecast')).find((c) => c.key === 'commit')
    if (!commit) throw new Error('commit 코드가 있어야 합니다.')
    await gateway.codes.rename(commit.id, '확정')

    // when: 스냅숏 요약과 실시간 요약을 읽는다
    const snapshot = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026 })
    const live = await gateway.forecast.summary({ year: 2026 })

    // then: 스냅숏 열에는 새 코드가 없고 옛 이름이며, 실시간 열은 현재 코드를 따른다
    expect(snapshot.columns.map((c) => c.key)).not.toContain('verbal')
    expect(snapshot.columns.find((c) => c.key === 'commit')?.name).toBe(SNAPSHOT_COMMIT_NAME)
    expect(live.columns.map((c) => c.key)).toContain('verbal')
    expect(live.columns.find((c) => c.key === 'commit')?.name).toBe('확정')
  })

  it('기간을 바꿔도 열이 같고 셀이 없는 기간은 행 없이 0 합계다', async () => {
    // given: 2026-09 스냅숏
    const { gateway } = await mockAs('kim')

    // when: Q3와 셀이 없는 2031년 요약을 읽는다
    const q3 = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })
    const empty = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2031 })

    // then: 열이 같고 행이 없으며 합계가 0이다
    expect(empty.columns).toEqual(q3.columns)
    expect(empty.rows).toEqual([])
    expect(empty.totalRow.total).toEqual({ count: 0, amount: 0 })
  })

  it('분기의 저장된 월 셀을 담당자별로 더하고 Lost는 뺀다', async () => {
    // given: 2026-09 스냅숏(kim: pipeline·commit·won·lost, park: best)
    const { gateway } = await mockAs('kim')

    // when: 2026 Q3 요약을 읽는다
    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: 행은 kim·park이고 셀·합계가 저장값이며 Lost 금액은 없다
    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([
      [USER_ID.kim, '김영업'],
      [USER_ID.park, '박영업'],
    ])
    const [kim, park] = summary.rows
    expect(kim?.cells).toEqual({
      pipeline: { count: 2, amount: 200_000_000 },
      best: { count: 0, amount: 0 },
      most_likely: { count: 0, amount: 0 },
      commit: { count: 1, amount: 50_000_000 },
      won: { count: 1, amount: 700_000_000 },
    })
    expect(kim?.total).toEqual({ count: 3, amount: 250_000_000 })
    expect(park?.total).toEqual({ count: 1, amount: 30_000_000 })
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계' })
    expect(summary.totalRow.total).toEqual({ count: 4, amount: 280_000_000 })
    expect(summary.totalRow.cells.won).toEqual({ count: 1, amount: 700_000_000 })
  })

  it('요청한 월·분기·연도의 셀만 모은다', async () => {
    // given: 2026-09 스냅숏
    const { gateway } = await mockAs('kim')

    // when: 8월, Q4, 2026년 전체를 읽는다
    const august = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, month: 8 })
    const q4 = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 4 })
    const year = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026 })

    // then: 각 기간의 셀만 합쳐진다
    expect(august.totalRow.total).toEqual({ count: 2, amount: 200_000_000 })
    expect(q4.totalRow.total).toEqual({ count: 1, amount: 5_000_000 })
    expect(year.totalRow.total).toEqual({ count: 5, amount: 285_000_000 })
  })

  it('담당자 조건은 그 담당자 행만 남긴다', async () => {
    // given: 2026-09 스냅숏
    const { gateway } = await mockAs('kim')

    // when: park 조건으로 읽는다
    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, ownerId: USER_ID.park })

    // then: park 행만 있고 합계는 park 값이다
    expect(summary.rows.map((r) => r.ownerId)).toEqual([USER_ID.park])
    expect(summary.totalRow.total).toEqual({ count: 1, amount: 30_000_000 })
  })

  it('저장 뒤 Deal이 바뀌어도 스냅숏은 그대로이고 실시간 요약은 바뀐다', async () => {
    // given: Deal을 추가하기 전의 스냅숏 요약
    const { gateway } = await mockAs('kim')
    const before = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // when: 2026-08에 commit Deal을 추가하고 두 요약을 다시 읽는다
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '스냅숏 뒤 Deal', revenueDate: '2026-08-20', forecastKey: 'commit', revenueAmount: 9_000_000 }))
    const after = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })
    const live = await gateway.forecast.summary({ year: 2026, quarter: 3 })

    // then: 스냅숏은 같고, 실시간은 live 기준에 현재 코드 이름이다
    expect(after.rows).toEqual(before.rows)
    expect(after.totalRow).toEqual(before.totalRow)
    expect(live.basis).toBe('live')
    expect(live.snapshotPeriod).toBeNull()
    expect(live.columns.find((c) => c.key === 'commit')?.name).toBe('Commit')
  })

  it('퇴사 담당자는 "(퇴사)" 이름으로 재직자 다음에 나온다', async () => {
    // given: 퇴사자의 7월 셀을 추가한 스냅숏
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

    // when: 2026 Q3 요약을 읽는다
    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: 퇴사자가 마지막이고 이름에 "(퇴사)"가 붙는다
    expect(summary.rows.map((r) => r.ownerName).at(-1)).toMatch(/\(퇴사\)$/)
    expect(summary.rows.slice(0, -1).every((r) => !r.ownerName.endsWith('(퇴사)'))).toBe(true)
  })

  it('행 순서는 이름의 문자 코드 순이고 이름이 같으면 사용자 id 순이다 (로캘 비교가 아니다)', async () => {
    // given: kim을 "Bob", park을 "alice"로 바꾼 사용자 정보 (문자 코드로는 "B" < "a", 로캘 비교로는 반대)
    const seed: SeedFactory = (clock) => renameUsers(buildSampleSeed(clock), { [USER_ID.kim]: 'Bob', [USER_ID.park]: 'alice' })
    const { gateway } = await mockAs('kim', { seed })

    // when: 2026 Q3 요약을 읽는다
    const summary = await gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: 문자 코드 순으로 Bob, alice다
    expect(summary.rows.map((r) => r.ownerName)).toEqual(['Bob', 'alice'])

    // given: 두 사람의 이름이 같은 사용자 정보
    const sameName: SeedFactory = (clock) => renameUsers(buildSampleSeed(clock), { [USER_ID.kim]: '동명', [USER_ID.park]: '동명' })
    const same = await mockAs('kim', { seed: sameName })

    // when: 다시 읽는다
    const tied = await same.gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 3 })

    // then: id 오름차순이다
    expect(tied.rows.map((r) => r.ownerId)).toEqual([USER_ID.kim, USER_ID.park])
  })

  it('없는 기준 월과 형식이 틀린 기준 월은 기준 월이 담긴 문구의 404다', async () => {
    // given: 2026-09 스냅숏만 있는 Fake
    const { gateway } = await mockAs('kim')

    // when·then: 없거나 형식이 틀린 기준 월을 읽으면 404이고 문구 끝에 보낸 기준 월이 붙는다
    for (const period of ['2026-08', '2027-01', '2026-9', 'abc', '2026-13']) {
      await expectApiError(gateway.forecast.snapshotSummary(period, { year: 2026 }), 404, snapshotNotFoundMessage(period))
    }
  })

  it('Vendor 조건은 서버처럼 422 request-validation이다 (스냅숏에는 Vendor가 없다)', async () => {
    // given: Vendor 조건
    const { gateway } = await mockAs('kim')
    const query = { year: 2026, vendorId: seedVendorId('Silverfort') }

    // when·then: 스냅숏 요약에 보내면 422이고 문구는 서버의 요청 형식 오류다
    const error = await expectApiError(gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, query), 422, '요청 형식이 올바르지 않습니다')
    expect(error.problem?.type).toMatch(/validation$/)
  })

  it('Quarter와 월을 함께 주면 422다', async () => {
    // given: 2026-09 스냅숏
    const { gateway } = await mockAs('kim')

    // when·then: quarter=1&month=1로 읽으면 안내 문구의 422이다
    await expectApiError(
      gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026, quarter: 1, month: 1 }),
      422,
      'Quarter와 월은 함께 선택할 수 없습니다.',
    )
  })

  it('쿼리 오류가 기준 월 404보다 먼저 판정된다', async () => {
    // given: 없는 기준 월
    const { gateway } = await mockAs('kim')

    // when·then: 없는 기준 월에 Quarter와 월을 함께 주면 404가 아니라 422다
    await expectApiError(
      gateway.forecast.snapshotSummary('1999-01', { year: 2026, quarter: 1, month: 1 }),
      422,
      'Quarter와 월은 함께 선택할 수 없습니다.',
    )
  })

  it('로그인이 필요하다', async () => {
    // given: 로그인하지 않은 Fake
    const { gateway } = await mockAs(null)

    // when·then: 요약을 읽으면 401이다
    await expectApiError(gateway.forecast.snapshotSummary(SNAPSHOT_PERIOD, { year: 2026 }), 401)
  })
})

function renameUsers(data: ReturnType<typeof buildSampleSeed>, names: Record<number, string>): ReturnType<typeof buildSampleSeed> {
  for (const user of data.users) {
    const name = names[user.id]
    if (name !== undefined) user.name = name
  }
  return data
}
