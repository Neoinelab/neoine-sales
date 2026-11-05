import { useEffect, useId, useRef, useState } from 'react'
import { usePermissions } from '../../data/auth'
import { useEndContract, useIssueContract, useRemoveContract, useRenewContract, useUpdateContract } from '../../data/licenseContracts'
import { userLabel } from '../../shared/model/period'
import type { InspectionCycle, LicenseContract, LicenseContractFields } from '../../shared/model/types'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Modal } from '../../shared/ui/Modal'
import { SelectField, TextArea, TextField } from '../../shared/ui/fields'
import { messageOf } from '../deals/detail/detailHelpers'
import { ContractAttachments } from './ContractAttachments'
import { INSPECTION_LABELS, STATUS_LABELS, isIssuedStatus } from './contractLabels'
import { currentLicenseValues, draftEnd, parseAmount, startError, startLicenseDraft, type LicenseDraft } from './licenseDraft'
import { LicenseFields } from './LicenseFields'

interface ContractEditDialogProps {
  contract: LicenseContract
  /** 서버 시계의 오늘('YYYY-MM-DD'). 발급 시작일 기본값. */
  today: string
  /** 저장·발급·갱신·종료·삭제가 성공했을 때. 호출처가 알림을 보이고 대화상자를 닫는다. */
  onDone: (message: string) => void
  onClose: () => void
}

const INSPECTIONS = Object.keys(INSPECTION_LABELS) as InspectionCycle[]

type Confirming = 'end' | 'remove' | null

/** Deal에서 오는 값(읽기 전용) 한 줄. */
function DealValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="contract-deal-value">
      <span className="contract-edit-label">{label}</span>
      <span>{value === '' ? '-' : value}</span>
    </div>
  )
}

/**
 * 계약 수정 대화상자. 고객사명·Vendor·제품명·파트너사·담당영업은 Deal 값이라 읽기 전용이고, 계약 칸(기술담당·점검주기·Note)만 고친다.
 * 라이선스 칸은 상태 옆 발급·갱신 버튼을 눌러야 활성화되며 저장할 때 서버가 종료일을 계산해 반영한다. 계약 종료·삭제(admin)는 확인 뒤 바로 반영된다.
 * 첨부는 올리는 즉시 반영된다. 서버 거절(409·422 등)은 대화상자 안 알림으로 보이고 닫히지 않는다.
 */
export function ContractEditDialog({ contract, today, onDone, onClose }: ContractEditDialogProps) {
  const { canWrite, isAdmin } = usePermissions()
  const update = useUpdateContract()
  const issue = useIssueContract()
  const renew = useRenewContract()
  const end = useEndContract()
  const remove = useRemoveContract()
  const [fields, setFields] = useState<LicenseContractFields>({ techOwner: contract.techOwner, inspection: contract.inspection, note: contract.note })
  const [license, setLicense] = useState<LicenseDraft | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<Confirming>(null)
  const startRef = useRef<HTMLInputElement | null>(null)
  const statusId = useId()
  const dealId = useId()
  const mode = license?.mode
  // 칸이 활성화(disabled 해제)된 렌더 뒤에 시작일 칸으로 포커스를 옮긴다.
  useEffect(() => {
    if (mode) startRef.current?.focus()
  }, [mode])
  const set = (patch: Partial<LicenseContractFields>) => setFields((prev) => ({ ...prev, ...patch }))

  const shown = license ?? currentLicenseValues(contract)
  const issued = isIssuedStatus(contract.status)
  const busy = update.isPending || issue.isPending || renew.isPending || end.isPending || remove.isPending
  const startMessage = license && submitted ? startError(license.start) : undefined
  const amountMessage = license && submitted && parseAmount(license.amount) === null ? '기간을 1~99 사이의 숫자로 입력하세요.' : undefined

  async function run(action: () => Promise<unknown>, message: string) {
    setError(null)
    try {
      await action()
      onDone(message)
    } catch (caught) {
      setConfirming(null)
      setError(messageOf(caught))
    }
  }

  function save() {
    setSubmitted(true)
    if (license === null) {
      void run(() => update.mutateAsync({ id: contract.id, fields }), '계약을 수정했습니다.')
      return
    }
    const amount = parseAmount(license.amount)
    if (draftEnd(license) === null || amount === null) return
    const input = { ...fields, start: license.start, term: { amount, unit: license.unit } }
    if (license.mode === 'issue') void run(() => issue.mutateAsync({ id: contract.id, input }), '라이센스를 발급했습니다.')
    else void run(() => renew.mutateAsync({ id: contract.id, input }), '라이센스를 갱신했습니다.')
  }

  return (
    <Modal
      title={`계약 수정 - ${contract.dealName}`}
      wide
      onClose={onClose}
      footer={
        <>
          {isAdmin && (
            <button type="button" className="danger contract-delete-button" disabled={busy} onClick={() => setConfirming('remove')}>
              삭제
            </button>
          )}
          <button type="button" onClick={onClose}>
            취소
          </button>
          {canWrite && (
            <button type="button" className="primary" disabled={busy} onClick={save}>
              저장
            </button>
          )}
        </>
      }
    >
      <div role="group" aria-labelledby={dealId} className="contract-deal-values">
        <h3 id={dealId} className="contract-deal-heading">
          Deal 정보
        </h3>
        <div className="contract-edit-grid">
          <DealValue label="고객사명" value={contract.customer} />
          <DealValue label="Vendor" value={contract.vendor?.name ?? ''} />
          <DealValue label="제품명" value={contract.product} />
          <DealValue label="파트너사" value={contract.partner ?? ''} />
          <DealValue label="담당영업" value={userLabel(contract.salesOwner)} />
        </div>
      </div>
      <div className="contract-edit-license">
        <div role="group" aria-labelledby={statusId} className="contract-edit-status">
          <span id={statusId} className="contract-edit-label">
            상태
          </span>
          <span className="contract-status-cell">
            <span className="badge contract-status" data-status={contract.status}>
              {STATUS_LABELS[contract.status]}
            </span>
            {canWrite &&
              contract.status !== 'ended' &&
              (license ? (
                <span className="hint">{license.mode === 'issue' ? '저장하면 발급(신규)됩니다' : '저장하면 발급(갱신)됩니다'}</span>
              ) : (
                <button
                  type="button"
                  className="contract-license-button"
                  disabled={!contract.dealIsWon}
                  onClick={() => setLicense(startLicenseDraft(contract, issued ? 'renew' : 'issue', today))}
                >
                  {issued ? '라이센스 갱신' : '라이센스 발급'}
                </button>
              ))}
            {canWrite && contract.status !== 'ended' && !license && !contract.dealIsWon && (
              <span className="hint">Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.</span>
            )}
            {canWrite && contract.status !== 'ended' && (
              <button type="button" className="contract-license-button" disabled={busy} onClick={() => setConfirming('end')}>
                계약 종료
              </button>
            )}
          </span>
        </div>
      </div>
      <LicenseFields
        {...shown}
        end={draftEnd(shown)}
        disabled={!license}
        startError={startMessage}
        amountError={amountMessage}
        startRef={startRef}
        onChange={(patch) => setLicense((prev) => (prev ? { ...prev, ...patch } : prev))}
      />
      <div className="contract-edit-grid">
        <TextField label="기술담당" name="techOwner" value={fields.techOwner} disabled={!canWrite} onChange={(techOwner) => set({ techOwner })} />
        <SelectField
          label="점검주기"
          name="inspection"
          value={fields.inspection}
          disabled={!canWrite}
          onChange={(inspection) => set({ inspection: inspection as InspectionCycle })}
        >
          {INSPECTIONS.map((cycle) => (
            <option key={cycle} value={cycle}>
              {INSPECTION_LABELS[cycle]}
            </option>
          ))}
        </SelectField>
      </div>
      <TextArea label="Note" name="note" value={fields.note} disabled={!canWrite} onChange={(note) => set({ note })} />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <ContractAttachments contractId={contract.id} />
      {confirming === 'end' && (
        <ConfirmDialog
          title="계약 종료 확인"
          message={`Deal ${contract.dealName}의 계약을 종료합니다. 종료한 계약은 다시 발급·갱신할 수 없습니다.`}
          confirmLabel="종료"
          busy={end.isPending}
          onConfirm={() => void run(() => end.mutateAsync(contract.id), '계약을 종료했습니다.')}
          onCancel={() => setConfirming(null)}
        />
      )}
      {confirming === 'remove' && (
        <ConfirmDialog
          title="계약 삭제"
          message={`Deal ${contract.dealName}의 계약과 첨부 파일을 삭제합니다. 삭제한 계약은 복구할 수 없습니다.`}
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          onConfirm={() => void run(() => remove.mutateAsync(contract.id), '계약을 삭제했습니다.')}
          onCancel={() => setConfirming(null)}
        />
      )}
    </Modal>
  )
}
