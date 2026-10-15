import { useApplyDealChange } from '../../../data/deals'
import { useCodeSet } from '../../../data/codes'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { useToday } from '../../../data/today'
import { formatRelativeTime } from '../../../shared/format'
import { isValidAmount, parseAmount } from '../../../shared/model/money'
import type { DealChange, DealDetail } from '../../../shared/model/types'
import { AmountText } from '../../../shared/ui/AmountText'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { RiskBadge } from '../../../shared/ui/RiskBadge'
import { toResolution } from './detailHelpers'
import { DealFacts } from './DealFacts'
import { InlineEdit } from './InlineEdit'
import './detail.css'

interface SummaryBarProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 상단 현재값 바: 항상 최신 Status/Forecast/금액/Expected Close/Next Action. 쓰기 권한이 있으면 값을 클릭해 바로 고친다(동기화 팝업 포함). */
export function SummaryBar({ deal, canWrite, onNotice }: SummaryBarProps) {
  const codes = useCodeSet().data
  const { now } = useToday()
  const applyChange = useApplyDealChange()
  const { request, dialogs } = useSyncedChange(deal)

  async function changeCode(field: 'statusKey' | 'forecastKey', value: string) {
    if (value === (field === 'statusKey' ? deal.statusKey : deal.forecastKey)) return
    const applied = await request({ field, value })
    if (applied === null) return
    const result = await applyChange.mutateAsync({
      code: deal.code,
      request: { change: { field, value }, resolution: toResolution(applied) },
    })
    const list = field === 'statusKey' ? codes?.statuses : codes?.forecasts
    const name = list?.find((c) => c.key === value)?.name ?? value
    onNotice(result.notice ?? `${field === 'statusKey' ? 'Status' : 'Forecast'}가 '${name}'(으)로 변경되었습니다.`)
  }

  async function changeValue(change: DealChange, message: string) {
    const result = await applyChange.mutateAsync({ code: deal.code, request: { change } })
    onNotice(result.notice ?? message)
  }

  async function saveAmount(text: string) {
    const amount = parseAmount(text)
    if (amount === null || !isValidAmount(amount)) throw new Error('매출금액은 1원 이상의 정수로 입력하세요.')
    await changeValue({ field: 'revenueAmount', value: amount }, '금액이 변경되었습니다.')
  }

  async function saveDate(text: string) {
    if (text === '') throw new Error('Expected Close를 입력하세요.')
    await changeValue({ field: 'revenueDate', value: text }, 'Expected Close가 변경되었습니다.')
  }

  const forecast = codes?.forecasts.find((c) => c.key === deal.forecastKey)
  const statusOptions = (codes?.statuses ?? []).map((c) => ({ value: c.key, label: c.name }))
  const forecastOptions = (codes?.forecasts ?? []).map((c) => ({ value: c.key, label: c.name }))

  return (
    <>
      <section aria-label="현재 값" className="dd-card">
        <div className="dd-fields">
          <div className="dd-kv">
            <span className="dd-k">Status</span>
            <span className="dd-v">
              <InlineEdit
                label="Status"
                canEdit={canWrite && codes !== undefined}
                kind="select"
                options={statusOptions}
                display={<StatusBadge statusKey={deal.statusKey} />}
                initial={deal.statusKey}
                onSave={(value) => changeCode('statusKey', value)}
              />
            </span>
          </div>
          <div className="dd-kv">
            <span className="dd-k">Forecast</span>
            <span className="dd-v">
              <InlineEdit
                label="Forecast"
                canEdit={canWrite && codes !== undefined}
                kind="select"
                options={forecastOptions}
                display={<ForecastBadge forecastKey={deal.forecastKey} />}
                initial={deal.forecastKey}
                onSave={(value) => changeCode('forecastKey', value)}
              />
            </span>
          </div>
          <div className="dd-kv">
            <span className="dd-k">금액</span>
            <span className="dd-v">
              <InlineEdit
                label="금액"
                inputLabel="금액(KRW)"
                canEdit={canWrite}
                kind="number"
                display={<AmountText amount={deal.revenueAmount} />}
                initial={String(deal.revenueAmount)}
                onSave={saveAmount}
              />
            </span>
          </div>
          <div className="dd-kv">
            <span className="dd-k">Expected Close</span>
            <span className="dd-v">
              <InlineEdit
                label="Expected Close"
                canEdit={canWrite}
                kind="date"
                display={<span>{deal.revenueDate}</span>}
                initial={deal.revenueDate}
                onSave={saveDate}
              />
            </span>
          </div>
          <div className="dd-kv">
            <span className="dd-k">Next Action</span>
            <span className="dd-v">
              {deal.nextAction ? (
                <>
                  <span>{deal.nextAction.text}</span>
                  <span className="dd-muted">Due {deal.nextAction.dueDate}</span>
                  <RiskBadge risk={deal.risk} />
                </>
              ) : (
                <span className="dd-muted">없음</span>
              )}
            </span>
          </div>
          <div className="dd-kv">
            <span className="dd-k">최종 업데이트</span>
            <span className="dd-v" title={deal.lastUpdatedAt}>
              {formatRelativeTime(deal.lastUpdatedAt, now)}
            </span>
          </div>
        </div>
        <DealFacts deal={deal} canWrite={canWrite} onNotice={onNotice} />
        {forecast?.outcome === 'won' && (
          <p className="dd-closed" data-outcome="won">
            Won으로 종결된 Deal입니다. 매출금액과 매출일은 확정 값이며, 필요하면 계속 수정할 수 있습니다.
          </p>
        )}
        {forecast?.outcome === 'lost' && (
          <p className="dd-closed" data-outcome="lost">
            Lost로 종결된 Deal입니다. Forecast를 바꾸면 다시 진행 중으로 되돌릴 수 있습니다.
          </p>
        )}
      </section>
      {dialogs}
    </>
  )
}
