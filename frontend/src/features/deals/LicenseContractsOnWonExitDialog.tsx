import { Modal } from '../../shared/ui/Modal'

interface LicenseContractsOnWonExitDialogProps {
  /** 이 Deal의 라이선스 계약 건수(1 이상). */
  count: number
  onDelete: () => void
  onKeep: () => void
  onCancel: () => void
}

/**
 * Won을 벗어나는 변경에서 Deal의 라이선스 계약을 함께 지울지 묻는다.
 * 삭제는 계약과 첨부 파일을 복구할 수 없게 지우고, 유지는 계약을 그대로 두며, 취소는 변경 자체를 하지 않는다.
 */
export function LicenseContractsOnWonExitDialog({ count, onDelete, onKeep, onCancel }: LicenseContractsOnWonExitDialogProps) {
  return (
    <Modal
      title="라이선스 계약 처리"
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            취소
          </button>
          <button type="button" onClick={onKeep}>
            유지
          </button>
          <button type="button" className="danger" onClick={onDelete}>
            삭제
          </button>
        </>
      }
    >
      <p>이 Deal의 라이선스 계약 {count}건도 삭제할까요?</p>
      <p className="hint">삭제하면 계약과 첨부 파일이 함께 지워지며 복구할 수 없습니다. 유지하면 계약은 그대로 남습니다.</p>
    </Modal>
  )
}

/** 서버 `WON_EXIT_BLOCKED`와 같은 문구. */
export const WON_EXIT_BLOCKED_MESSAGE =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'

/** 발급 상태 계약이 있는 Deal은 Won을 벗어날 수 없다는 안내. 요청은 보내지 않는다. */
export function WonExitBlockedDialog({ onClose }: { onClose: () => void }) {
  return (
    <Modal
      title="라이선스 계약 처리"
      onClose={onClose}
      footer={
        <button type="button" className="primary" onClick={onClose}>
          확인
        </button>
      }
    >
      <p>{WON_EXIT_BLOCKED_MESSAGE}</p>
    </Modal>
  )
}
