import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { useMe } from '../../../data/auth'
import { useCodeSet } from '../../../data/codes'
import { useDeal } from '../../../data/deals'
import { useLabels } from '../../../data/labels'
import { canDeleteDeal, canWrite as canWriteRole } from '../../../shared/model/permissions'
import '../../../shared/ui/kvGrid.css'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Notice } from '../../../shared/ui/Notice'
import { Tabs } from '../../../shared/ui/Tabs'
import { useDealListPath } from '../../../shared/ui/useDealListPath'
import { useLocationNotice } from '../../../shared/ui/useLocationNotice'
import { ActionsTab } from './ActionsTab'
import { AttachmentsPanel } from './AttachmentsPanel'
import { messageOf } from './detailHelpers'
import { DeleteDealDialog } from './DeleteDealDialog'
import { DealTitle } from './DealTitle'
import { HistoryTab } from './HistoryTab'
import { InfoCards } from './InfoCards'
import { SummaryBar } from './SummaryBar'
import './detail.css'

const TABS = [
  { id: 'info', label: 'Deal 상세' },
  { id: 'actions', label: 'Actions' },
  { id: 'history', label: 'Deal History' },
] as const

/** Deal 상세 `/deals/:dealCode`: 머리(이름) 바로 아래 탭 3개(Deal 상세: Deal 정보·정보 카드·첨부 파일 / Actions / Deal History, 기본은 Deal 상세) · 알림(탭 패널 맨 위) · 삭제. */
export function DealDetailPage() {
  const { dealCode } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const deal = useDeal(dealCode)
  const me = useMe().data ?? null
  const codes = useCodeSet()
  const labels = useLabels()
  const [notice, setNotice] = useLocationNotice()
  const [deleting, setDeleting] = useState(false)
  const [deleted, setDeleted] = useState(false)
  const listPath = useDealListPath()
  const tabParam = params.get('tab')
  // 모르는 값은 Deal 상세 탭이다.
  const tab = tabParam === 'actions' || tabParam === 'history' ? tabParam : 'info'

  if (deleted) return null
  if (deal.isError) {
    return (
      <section className="dd-page">
        <ErrorBanner error={deal.error} format={messageOf} />
        <p>
          <Link to={listPath}>Deal 목록으로</Link>
        </p>
      </section>
    )
  }
  const data = deal.data
  if (!data || !codes.data || !labels.data) return <p role="status">불러오는 중…</p>

  const canWrite = canWriteRole(me?.role)
  const canDelete = me !== null && canDeleteDeal({ id: me.id, role: me.role }, data.ownerId)

  function changeTab(id: string) {
    const next = new URLSearchParams(params)
    if (id === 'actions' || id === 'history') next.set('tab', id)
    else next.delete('tab')
    setParams(next)
  }

  return (
    <div className="dd-page deal-detail">
      <header className="dd-head">
        <DealTitle deal={data} canWrite={canWrite} onNotice={setNotice} />
        <div className="dd-head-actions">
          <Link to={listPath} className="button">
            ← 목록
          </Link>
          {canWrite && (
            <button
              type="button"
              className="danger"
              aria-label="Deal 삭제"
              disabled={!canDelete}
              title={canDelete ? undefined : '본인 Deal 또는 admin만 삭제할 수 있습니다.'}
              onClick={() => setDeleting(true)}
            >
              삭제
            </button>
          )}
        </div>
      </header>
      <Tabs label="상세 탭" tabs={TABS} active={tab} onChange={changeTab}>
        {notice && (
          <Notice kind="success" onClose={() => setNotice(null)}>
            {notice}
          </Notice>
        )}
        {tab === 'info' && (
          <>
            <SummaryBar deal={data} canWrite={canWrite} onNotice={setNotice} />
            <InfoCards deal={data} canWrite={canWrite} onNotice={setNotice} />
            <AttachmentsPanel dealCode={data.code} me={me} canWrite={canWrite} />
          </>
        )}
        {tab === 'history' && <HistoryTab dealCode={data.code} />}
        {tab === 'actions' && (
          <ActionsTab
            deal={data}
            canWrite={canWrite}
            me={me === null ? null : { id: me.id, role: me.role }}
            onNotice={setNotice}
          />
        )}
      </Tabs>
      {deleting && (
        <DeleteDealDialog
          deal={data}
          onCancel={() => setDeleting(false)}
          onDeleted={(message) => {
            setDeleted(true)
            void navigate(listPath, { state: { notice: message } })
          }}
        />
      )}
    </div>
  )
}
