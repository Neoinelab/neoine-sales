import type { ReactNode } from 'react'
import { useVendors } from '../../../data/vendors'
import { formatDate } from '../../../shared/format'
import type { DealDetail, PocState, QuoteSubmitted } from '../../../shared/model/types'
import { USERS_MESSAGE, USERS_REQUIRED_MESSAGE } from '../form/formState'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

const QUOTE_TEXT: Record<QuoteSubmitted, string> = { YES: '제출', NO: '미제출' }
const POC_TEXT: Record<PocState, string> = { YES: '완료', ING: '진행 중', NO: '하지 않음' }
const NONE = { value: '', label: '선택 안 함' }
const QUOTE_OPTIONS = [NONE, { value: 'YES', label: 'YES' }, { value: 'NO', label: 'NO' }]
const POC_OPTIONS = [NONE, { value: 'YES', label: 'YES' }, { value: 'ING', label: 'ING' }, { value: 'NO', label: 'NO' }]

interface DealFactsProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 단계(YES/ING/NO)와 날짜를 따로 클릭해 고치는 쌍의 날짜 표시. 쓰기 권한이 없고 값도 없으면 아무것도 그리지 않는다. */
function dateDisplay(date: string | null, canWrite: boolean): ReactNode {
  if (date) return ` (${date})`
  return canWrite ? <span className="dd-muted"> 일자 입력</span> : null
}

/** Deal 정보 타일의 항목 행(Vendor·Solution·Users·견적·POC·구매절차·등록일). 값을 클릭해 그 자리에서 고친다. */
export function DealFacts({ deal, canWrite, onNotice }: DealFactsProps) {
  const { save } = useDealPatch(deal.code, onNotice)
  const vendors = useVendors().data ?? []
  const vendorOptions = [NONE, ...vendors.map((v) => ({ value: v.id, label: v.name }))]
  const currentVendor = vendors.find((v) => v.id === deal.vendor?.id)
  const solutionOptions = [NONE, ...(currentVendor?.solutions ?? []).map((s) => ({ value: s.id, label: s.name }))]
  const { quote, poc } = deal

  async function saveProcurement(text: string) {
    const value = text.trim()
    if (value !== deal.procurement) await save({ procurement: value }, '구매절차가 변경되었습니다.')
  }

  /** Vendor가 바뀌면 Solution은 항상 비운다(서버 규칙). 원래 Solution이 있었을 때만 그 사실을 알린다. */
  async function saveVendor(vendorId: string) {
    if (vendorId === (deal.vendor?.id ?? '')) return
    const message = deal.solution
      ? 'Vendor가 변경되었습니다. Solution은 비워졌습니다.'
      : 'Vendor가 변경되었습니다.'
    await save({ vendorId: vendorId || null, solutionId: null }, message)
  }

  async function saveSolution(solutionId: string) {
    if (solutionId === (deal.solution?.id ?? '')) return
    await save({ vendorId: deal.vendor?.id ?? null, solutionId: solutionId || null }, 'Solution이 변경되었습니다.')
  }

  async function saveUsers(text: string) {
    const raw = text.trim()
    if (raw === '') throw new Error(USERS_REQUIRED_MESSAGE)
    if (!/^\d+$/.test(raw)) throw new Error(USERS_MESSAGE)
    const users = Number(raw)
    if (users !== deal.users) await save({ users }, 'Users가 변경되었습니다.')
  }

  async function saveQuote(patch: Partial<typeof quote>, message: string) {
    await save({ quote: { ...quote, ...patch } }, message)
  }

  async function savePoc(patch: Partial<typeof poc>, message: string) {
    await save({ poc: { ...poc, ...patch } }, message)
  }

  const facts: Array<[string, ReactNode]> = [
    [
      'Vendor',
      <InlineEdit
        key="vendor"
        label="Vendor"
        canEdit={canWrite}
        kind="select"
        options={vendorOptions}
        display={deal.vendor?.name ?? '—'}
        initial={deal.vendor?.id ?? ''}
        onSave={saveVendor}
      />,
    ],
    [
      'Solution',
      <InlineEdit
        key="solution"
        label="Solution"
        canEdit={canWrite && deal.vendor !== null}
        kind="select"
        options={solutionOptions}
        display={deal.solution?.name ?? '—'}
        initial={deal.solution?.id ?? ''}
        onSave={saveSolution}
      />,
    ],
    [
      'Users',
      <InlineEdit
        key="users"
        label="Users"
        canEdit={canWrite}
        kind="number"
        display={String(deal.users)}
        initial={String(deal.users)}
        onSave={saveUsers}
      />,
    ],
    [
      '견적',
      <>
        <InlineEdit
          label="견적 제출여부"
          canEdit={canWrite}
          kind="select"
          options={QUOTE_OPTIONS}
          display={quote.submitted === null ? '—' : QUOTE_TEXT[quote.submitted]}
          initial={quote.submitted ?? ''}
          onSave={(text) => saveQuote({ submitted: text === 'YES' || text === 'NO' ? text : null }, '견적 제출여부가 변경되었습니다.')}
        />
        <InlineEdit
          label="견적 제출일"
          canEdit={canWrite}
          kind="date"
          display={dateDisplay(quote.submittedDate, canWrite)}
          initial={quote.submittedDate ?? ''}
          onSave={(text) => saveQuote({ submittedDate: text || null }, '견적 제출일이 변경되었습니다.')}
        />
      </>,
    ],
    [
      'POC',
      <>
        <InlineEdit
          label="POC 여부"
          canEdit={canWrite}
          kind="select"
          options={POC_OPTIONS}
          display={poc.state === null ? '—' : `${poc.state} · ${POC_TEXT[poc.state]}`}
          initial={poc.state ?? ''}
          onSave={(text) => savePoc({ state: text === 'YES' || text === 'ING' || text === 'NO' ? text : null }, 'POC 여부가 변경되었습니다.')}
        />
        <InlineEdit
          label="POC 완료일"
          canEdit={canWrite}
          kind="date"
          display={dateDisplay(poc.completedDate, canWrite)}
          initial={poc.completedDate ?? ''}
          onSave={(text) => savePoc({ completedDate: text || null }, 'POC 완료일이 변경되었습니다.')}
        />
      </>,
    ],
    [
      '구매절차',
      <InlineEdit
        key="procurement"
        label="구매절차"
        canEdit={canWrite}
        display={deal.procurement || '—'}
        initial={deal.procurement}
        onSave={saveProcurement}
      />,
    ],
    ['등록일', <span key="created" className="kv-static">{formatDate(deal.createdAt)}</span>],
  ]
  return (
    <>
      {facts.map(([label, value]) => (
        <div key={label} className="kv-row">
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </>
  )
}
