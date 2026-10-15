import { useState } from 'react'
import { useUpdateDeal } from '../../../data/deals'
import type { DealDetail } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import { InlineContactBlock } from './InlineContactBlock'
import { useDealPatch } from './useDealPatch'

interface CardProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 고객 연락처 카드: 회사·담당자·직급·이메일·전화를 클릭해 그 자리에서 고친다. 고객은 필수라 비울 수 없다. */
export function CustomerCard({ deal, canWrite, onNotice }: CardProps) {
  const { save } = useDealPatch(deal.code, onNotice)
  return (
    <section aria-labelledby="dd-customer" className="dd-card">
      <h2 id="dd-customer">고객</h2>
      <InlineContactBlock
        kind="customer"
        label="고객"
        noun="고객사"
        contact={deal.customer}
        canWrite={canWrite}
        onSave={(draft) => save({ customer: draft }, '고객 연락처가 저장되었습니다.')}
      />
    </section>
  )
}

/** 활성 파트너 카드. 비활성(이전) 파트너는 접어서 본다. 교체/추가/제거는 History에 남는다. 파트너는 선택이라 제거(확인 후)할 수 있다. */
export function PartnerCard({ deal, canWrite, onNotice }: CardProps) {
  const update = useUpdateDeal()
  const { save } = useDealPatch(deal.code, onNotice)
  const [removing, setRemoving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const active = deal.activePartner
  const past = deal.partnerHistory.filter((link) => !link.active)

  async function remove() {
    setError(null)
    try {
      await update.mutateAsync({ code: deal.code, patch: { partner: null } })
      setRemoving(false)
      onNotice('파트너가 제거되었습니다.')
    } catch (caught) {
      setRemoving(false)
      setError(caught)
    }
  }

  return (
    <section aria-labelledby="dd-partner" className="dd-card">
      <h2 id="dd-partner">파트너</h2>
      <InlineContactBlock
        kind="partner"
        label="파트너"
        noun="파트너"
        contact={active}
        canWrite={canWrite}
        sessionHint={
          active
            ? `기존 활성 파트너(${active.company} ${active.name})는 이력으로 남고 비활성이 됩니다.`
            : '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.'
        }
        onSave={(draft, change) =>
          save(
            { partner: draft },
            change === 'detail' ? '파트너 연락처가 저장되었습니다.' : active ? '파트너가 교체되었습니다.' : '파트너가 추가되었습니다.',
          )
        }
      />
      {canWrite && active && (
        <div className="dd-row">
          <button type="button" disabled={update.isPending} onClick={() => setRemoving(true)}>
            파트너 제거
          </button>
        </div>
      )}
      <ErrorBanner error={error} format={messageOf} />
      {removing && active && (
        <ConfirmDialog
          title="파트너 제거"
          message={`파트너 ${active.company} ${active.name}을(를) 제거합니다. 제거한 파트너는 이전 파트너 이력에 남습니다.`}
          confirmLabel="제거"
          danger
          busy={update.isPending}
          onConfirm={() => void remove()}
          onCancel={() => setRemoving(false)}
        />
      )}
      {past.length > 0 && (
        <details className="dd-history-old">
          <summary>이전 파트너 이력 ({past.length})</summary>
          <ul>
            {past.map((link) => (
              <li key={`${link.contact.id}-${link.linkedAt}`}>
                {link.contact.company} {link.contact.name} ({link.linkedAt.slice(0, 10)} ~ {link.unlinkedAt?.slice(0, 10) ?? ''})
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
