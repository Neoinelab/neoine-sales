import { useCodeSet } from '../../data/codes'
import type { Code } from '../model/types'
import './ui.css'

function CodeBadge({ code, fallback, kind }: { code: Code | undefined; fallback: string; kind: 'status' | 'forecast' }) {
  return (
    <span className={`badge ${kind}`} data-outcome={kind === 'forecast' ? (code?.outcome ?? 'open') : undefined}>
      {code?.name ?? fallback}
    </span>
  )
}

/** Status 코드 배지. 이름은 현재 코드표에서 찾고(이름 변경 즉시 반영), 로딩 중·모르는 key면 key를 보인다. */
export function StatusBadge({ statusKey }: { statusKey: string }) {
  const codes = useCodeSet().data
  return <CodeBadge kind="status" code={codes?.statuses.find((c) => c.key === statusKey)} fallback={statusKey} />
}

/** Forecast 코드 배지. `data-outcome`(open/won/lost)으로 Won·Lost 색을 구분한다. */
export function ForecastBadge({ forecastKey }: { forecastKey: string }) {
  const codes = useCodeSet().data
  return <CodeBadge kind="forecast" code={codes?.forecasts.find((c) => c.key === forecastKey)} fallback={forecastKey} />
}
