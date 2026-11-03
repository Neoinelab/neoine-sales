import type { ReportResult } from '../../../shared/model/reportTypes'
import { defaultChart } from './chartDraft'
import type { ChartEditSource } from './chartSource'
import { chartHeaderOf } from './chartHeaders'
import { fieldByKey } from '../designer/state/columnRules'

const NEEDS_GROUPING = '그룹핑한 결과로 차트를 만들 수 있습니다'
const HISTOGRAM_ONLY = '그룹핑이 없으면 히스토그램만 만들 수 있습니다'
const TOO_MANY_GROUPS = '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다'

/**
 * 차트가 아직 없을 때의 타일 본문(차트 만들기 버튼과 안내). Chart.js를 쓰지 않으므로 차트 청크 밖에 있다
 * (차트를 만들기 전에는 Chart.js 청크를 받지 않는다).
 */
export function ChartEmpty({ source, result }: { source: ChartEditSource; result: ReportResult | null }) {
  const { columns, catalog, dispatch } = source
  const created = defaultChart(columns, chartHeaderOf(source, result), (field) => fieldByKey(catalog, field)?.type === 'number')
  const groups = columns.filter((c) => c.group).length
  return (
    <>
      {source.problem && <p className="hint">{source.problem}</p>}
      <div className="report-chart-empty">
        <button type="button" disabled={created === null} onClick={() => created && dispatch({ type: 'createChart', chart: created })}>
          차트 만들기
        </button>
        {groups === 0 && <p className="hint">{created === null ? NEEDS_GROUPING : HISTOGRAM_ONLY}</p>}
        {groups > 2 && <p className="hint">{TOO_MANY_GROUPS}</p>}
        {groups > 0 && groups <= 2 && <p className="hint">그룹핑 컬럼은 범주(와 계열)로, 나머지 컬럼은 값으로 차트를 그립니다.</p>}
      </div>
    </>
  )
}
