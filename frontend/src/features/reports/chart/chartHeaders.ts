import type { ReportResult } from '../../../shared/model/reportTypes'
import { columnHeader } from '../designer/format/formatCell'
import { columnName } from '../designer/names'
import type { ChartEditSource } from './chartSource'

/** 컬럼 uid → 차트 설정 화면에 보이는 머리글. 조회한 결과의 머리글을 우선하고, 아직 조회하지 않았으면 설계의 컬럼 이름이다. */
export function chartHeaderOf(source: ChartEditSource, result: ReportResult | null): (uid: number) => string {
  const { columns, catalog, resultColumnUids } = source
  return (uid) => {
    const at = resultColumnUids.indexOf(uid)
    const shown = at < 0 ? undefined : result?.columns.find((c) => c.index === at)
    if (shown) return columnHeader(shown)
    const column = columns.find((c) => c.uid === uid)
    return column ? columnName(column, catalog) : ''
  }
}
