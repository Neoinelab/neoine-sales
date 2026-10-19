import { useApplyDealChange } from '../../../data/deals'
import { useCodeSet } from '../../../data/codes'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { useToday } from '../../../data/today'
import { formatDateTime, formatRelativeTime } from '../../../shared/format'
import { isValidAmount, parseAmount } from '../../../shared/model/money'
import type { DealChange, DealDetail } from '../../../shared/model/types'
import { AmountText } from '../../../shared/ui/AmountText'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { RiskBadge } from '../../../shared/ui/RiskBadge'
import { toResolution } from './detailHelpers'
import { DealFacts } from './DealFacts'
import { DealIdentityRows } from './DealIdentityRows'
import { InlineEdit } from './InlineEdit'
import './detail.css'

interface SummaryBarProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** Deal 정보 타일: Deal code·Owner와 항상 최신 Status/Forecast/금액/Expected Close/Next Action. 쓰기 권한이 있으면 값을 클릭해 바로 고친다(동기화 팝업 포함). */
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
      <section aria-labelledby="dd-info" className="dd-card">
        <h2 id="dd-info">Deal 정보</h2>
        <dl className="kv-grid">
          <DealIdentityRows deal={deal} canWrite={canWrite} onNotice={onNotice} />
          <div className="kv-row">
            <dt>Status</dt>
            <dd>
              <InlineEdit
                label="Status"
                canEdit={canWrite && codes !== undefined}
                kind="select"
                options={statusOptions}
                display={<StatusBadge statusKey={deal.statusKey} />}
                initial={deal.statusKey}
                onSave={(value) => changeCode('statusKey', value)}
              />
              <span className="dd-muted" title={formatDateTime(deal.statusChangedAt)}>{`${deal.statusDays}일째`}</span>
            </dd>
          </div>
          <div className="kv-row">
            <dt>Forecast</dt>
            <dd>
              <InlineEdit
                label="Forecast"
                canEdit={canWrite && codes !== undefined}
                kind="select"
                options={forecastOptions}
                display={<ForecastBadge forecastKey={deal.forecastKey} />}
                initial={deal.forecastKey}
                onSave={(value) => changeCode('forecastKey', value)}
              />
            </dd>
          </div>
          <div className="kv-row">
            <dt>금액</dt>
            <dd>
              <InlineEdit
                label="금액"
                inputLabel="금액(KRW)"
                canEdit={canWrite}
                kind="number"
                display={<AmountText amount={deal.revenueAmount} />}
                initial={String(deal.revenueAmount)}
                onSave={saveAmount}
              />
            </dd>
          </div>
          <div className="kv-row">
            <dt>Expected Close</dt>
            <dd>
              <InlineEdit
                label="Expected Close"
                canEdit={canWrite}
                kind="date"
                display={<span>{deal.revenueDate}</span>}
                initial={deal.revenueDate}
                onSave={saveDate}
              />
            </dd>
          </div>
          <div className="kv-row">
            <dt>Next Action</dt>
            <dd>
              {deal.nextAction ? (
                <>
                  <span className="kv-static">{deal.nextAction.text}</span>
                  <span className="dd-muted">Due {deal.nextAction.dueDate}</span>
                </>
              ) : (
                <span className="kv-static dd-muted">없음</span>
              )}
              <RiskBadge risk={deal.risk} />
            </dd>
          </div>
          <div className="kv-row">
            <dt>최종 업데이트</dt>
            <dd>
              <span className="kv-static" title={deal.lastUpdatedAt}>
                {formatRelativeTime(deal.lastUpdatedAt, now)}
              </span>
            </dd>
          </div>
          <DealFacts deal={deal} canWrite={canWrite} onNotice={onNotice} />
        </dl>
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
