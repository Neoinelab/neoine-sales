/**
 * 테스트 전용 Forecast 월말 스냅숏. 2026-09 기준 월 하나, 2026-10-01 00:05 생성.
 * 셀 값은 시드 Deal과 무관한 고정값이라 실시간 요약과 다르다. 스냅숏 당시 이름('확정(당시)')도 현재
 * 코드 이름('Commit')과 다르다. 저장된 열 목록은 기본 Forecast 코드 6개(Lost 포함)이고, most_likely는
 * 셀이 없지만 저장된 열이라 0건 열로 보인다.
 *
 *   2026 Q3 (7~9월): kim  pipeline 2건 2억(8월), commit 1건 5천만(9월), won 1건 7억(9월)
 *                    park best 1건 3천만(9월)
 *                    kim  lost 3건 9.99억(8월) -> 어디에도 보이지 않는다
 *   2026 Q4 (11월):  kim  pipeline 1건 5백만
 */

import type { ForecastSnapshotColumnRecord, ForecastSnapshotRecord } from '../fake/store'
import { USER_ID } from '../fake/seed/ids'

export const SNAPSHOT_PERIOD = '2026-09'
export const SNAPSHOT_TAKEN_AT = '2026-10-01T00:05:00+09:00'
export const SNAPSHOT_COMMIT_NAME = '확정(당시)'

type Cell = ForecastSnapshotRecord['cells'][number]

/** 저장 당시의 Forecast 코드 목록(order 순). */
export const SNAPSHOT_COLUMNS: ForecastSnapshotColumnRecord[] = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'best', name: 'Best', outcome: 'open', order: 2 },
  { key: 'most_likely', name: 'Most Likely', outcome: 'open', order: 3 },
  { key: 'commit', name: SNAPSHOT_COMMIT_NAME, outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
  { key: 'lost', name: 'Lost', outcome: 'lost', order: 6 },
]

const cell = (c: Pick<Cell, 'revenueMonth' | 'ownerId' | 'forecastKey' | 'count' | 'amount'>): Cell => ({
  revenueYear: 2026,
  ...c,
})

export function seedForecastSnapshots(): ForecastSnapshotRecord[] {
  return [
    {
      period: SNAPSHOT_PERIOD,
      takenAt: SNAPSHOT_TAKEN_AT,
      columns: SNAPSHOT_COLUMNS.map((c) => ({ ...c })),
      cells: [
        cell({ revenueMonth: 8, ownerId: USER_ID.kim, forecastKey: 'pipeline', count: 2, amount: 200_000_000 }),
        cell({ revenueMonth: 9, ownerId: USER_ID.kim, forecastKey: 'commit', count: 1, amount: 50_000_000 }),
        cell({ revenueMonth: 9, ownerId: USER_ID.kim, forecastKey: 'won', count: 1, amount: 700_000_000 }),
        cell({ revenueMonth: 8, ownerId: USER_ID.kim, forecastKey: 'lost', count: 3, amount: 999_000_000 }),
        cell({ revenueMonth: 9, ownerId: USER_ID.park, forecastKey: 'best', count: 1, amount: 30_000_000 }),
        cell({ revenueMonth: 11, ownerId: USER_ID.kim, forecastKey: 'pipeline', count: 1, amount: 5_000_000 }),
      ],
    },
  ]
}
