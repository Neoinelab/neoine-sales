import { useState } from 'react'
import { useDealImpact, useRemoveDeal } from '../../../data/deals'
import type { DealDetail } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import './detail.css'

interface DeleteDealDialogProps {
  deal: DealDetail
  onCancel: () => void
  /** 삭제 성공 후(상세 화면을 떠나기 위해) 호출. */
  onDeleted: (message: string) => void
}

/** Deal 삭제 확인: 연쇄 삭제 건수를 안내하고 Deal code를 정확히 입력해야 `삭제`가 켜진다. */
export function DeleteDealDialog({ deal, onCancel, onDeleted }: DeleteDealDialogProps) {
  const impact = useDealImpact(deal.code, true).data
  const remove = useRemoveDeal()
  const [typed, setTyped] = useState('')
  const [error, setError] = useState<unknown>(null)
  const mismatch = typed !== '' && typed !== deal.code

  async function confirm() {
    setError(null)
    try {
      await remove.mutateAsync({ code: deal.code, confirmCode: typed })
      onDeleted(`Deal ${deal.code}이(가) 삭제되었습니다.`)
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <ConfirmDialog
      title="Deal 삭제"
      message={
        impact
          ? `삭제하면 Deal History ${impact.historyCount}건, Action ${impact.actionCount}건, 첨부 파일 ${impact.attachmentCount}개와 파일 저장 디렉터리가 함께 삭제되며 복구할 수 없습니다.`
          : '삭제 대상 건수를 확인하는 중입니다. 삭제하면 Deal History, Action, 첨부 파일이 함께 삭제되며 복구할 수 없습니다.'
      }
      confirmLabel="삭제"
      danger
      busy={remove.isPending}
      confirmDisabled={typed !== deal.code}
      onConfirm={() => void confirm()}
      onCancel={onCancel}
    >
      <p>
        계속하려면 Deal code <code>{deal.code}</code>를 입력하세요.
      </p>
      <label className="field">
        <span>Deal code 확인</span>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
      </label>
      {mismatch && (
        <p role="alert" className="field-error">
          Deal code가 일치하지 않습니다.
        </p>
      )}
      <ErrorBanner error={error} format={messageOf} />
    </ConfirmDialog>
  )
}
