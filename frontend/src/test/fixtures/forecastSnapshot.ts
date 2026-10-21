/**
 * 테스트 전용 Forecast 월말 스냅숏(P6 R2). 2026-09 기준 월 하나, 2026-10-01 00:05 생성.
 * 셀 값은 시드 Deal과 무관한 고정값이라 실시간 요약과 다르다. 스냅숏 당시 이름('확정(당시)')도 현재
 * 코드 이름('Commit')과 다르다. most_likely는 스냅숏에 셀이 없어 스냅숏의 열이 아니다(열은 셀에서 만든다).
 *
 *   2026 Q3 (7~9월): kim  pipeline 2건 2억(8월), commit 1건 5천만(9월), won 1건 7억(9월)
 *                    park best 1건 3천만(9월)
 *                    kim  lost 3건 9.99억(8월) -> 어디에도 보이지 않는다
 *   2026 Q4 (11월):  kim  pipeline 1건 5백만
 */

import type { ForecastSnapshotRecord } from '../fake/store'
import { USER_ID } from '../fake/seed/ids'

export const SNAPSHOT_PERIOD = '2026-09'
export const SNAPSHOT_TAKEN_AT = '2026-10-01T00:05:00+09:00'
export const SNAPSHOT_COMMIT_NAME = '확정(당시)'

type Cell = ForecastSnapshotRecord['cells'][number]

const cell = (c: Pick<Cell, 'revenueMonth' | 'ownerId' | 'forecastKey' | 'count' | 'amount'> & Partial<Cell>): Cell => {
  const meta: Record<string, Pick<Cell, 'forecastName' | 'forecastOutcome' | 'forecastOrder'>> = {
    pipeline: { forecastName: 'Pipeline', forecastOutcome: 'open', forecastOrder: 1 },
    best: { forecastName: 'Best', forecastOutcome: 'open', forecastOrder: 2 },
    commit: { forecastName: SNAPSHOT_COMMIT_NAME, forecastOutcome: 'open', forecastOrder: 4 },
    won: { forecastName: 'Won', forecastOutcome: 'won', forecastOrder: 5 },
    lost: { forecastName: 'Lost', forecastOutcome: 'lost', forecastOrder: 6 },
  }
  const base = meta[c.forecastKey]
  if (!base) throw new RangeError(`스냅숏 시드에 없는 Forecast key: ${c.forecastKey}`)
  return { revenueYear: 2026, ...base, ...c }
}

export function seedForecastSnapshots(): ForecastSnapshotRecord[] {
  return [
    {
      period: SNAPSHOT_PERIOD,
      takenAt: SNAPSHOT_TAKEN_AT,
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
