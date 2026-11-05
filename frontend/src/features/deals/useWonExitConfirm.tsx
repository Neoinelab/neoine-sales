import { useCallback, useState, type ReactNode } from 'react'
import { leavesWon, type SyncState } from '../../shared/model/sync'
import { LicenseContractsOnWonExitDialog, WonExitBlockedDialog } from './LicenseContractsOnWonExitDialog'

/** 묻고 난 결과. 취소면 변경을 하지 않는다. 묻지 않았거나 유지이면 deleteLicenseContracts를 보내지 않거나 false로 보낸다. */
export type WonExitDecision = { proceed: false; blocked?: true } | { proceed: true; deleteLicenseContracts?: boolean }

/** 묻기에 필요한 Deal 쪽 값. */
export interface WonExitSubject {
  licenseContractCount: number
  hasIssuedLicenseContract: boolean
}

interface Pending {
  count: number
  resolve: (decision: WonExitDecision) => void
}

/**
 * Won을 벗어나는 변경을 저장하기 전에 라이선스 계약 처리(삭제/유지/취소)를 묻는다.
 * `ask(before, after, deal)`: Won을 벗어나는데 발급 상태 계약이 있으면 안내 대화상자('확인' 하나)만 띄우고 요청 없이 `{ proceed: false }`로 끝난다.
 * 발급 계약이 없고 계약이 1건 이상이면 삭제/유지/취소를 묻고, 그 밖에는 바로 진행(`{ proceed: true }`)한다.
 * 호출한 화면은 돌려받은 `dialog`를 그려야 한다. 요청에는 `deleteLicenseContracts`를 그대로 넘긴다.
 */
export function useWonExitConfirm(onBlockedClose?: () => void): { ask: (before: SyncState, after: SyncState, deal: WonExitSubject) => Promise<WonExitDecision>; dialog: ReactNode } {
  const [pending, setPending] = useState<Pending | null>(null)
  const [blocked, setBlocked] = useState(false)

  const ask = useCallback((before: SyncState, after: SyncState, deal: WonExitSubject): Promise<WonExitDecision> => {
    if (!leavesWon(before, after)) return Promise.resolve({ proceed: true })
    if (deal.hasIssuedLicenseContract) {
      setBlocked(true)
      return Promise.resolve({ proceed: false, blocked: true })
    }
    if (deal.licenseContractCount < 1) return Promise.resolve({ proceed: true })
    return new Promise((resolve) => setPending({ count: deal.licenseContractCount, resolve }))
  }, [])

  function choose(decision: WonExitDecision) {
    pending?.resolve(decision)
    setPending(null)
  }

  const blockedDialog = blocked ? <WonExitBlockedDialog onClose={() => {
        setBlocked(false)
        onBlockedClose?.()
      }} /> : null
  const dialog = pending ? (
    <LicenseContractsOnWonExitDialog
      count={pending.count}
      onDelete={() => choose({ proceed: true, deleteLicenseContracts: true })}
      onKeep={() => choose({ proceed: true, deleteLicenseContracts: false })}
      onCancel={() => choose({ proceed: false })}
    />
  ) : (
    blockedDialog
  )
  return { ask, dialog }
}
