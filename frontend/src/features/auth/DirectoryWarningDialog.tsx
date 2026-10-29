import { useNavigate } from 'react-router'
import { useDirectoryWarning } from '../../data/auth'
import { Modal } from '../../shared/ui/Modal'

/** AD 대신 저장된 비밀번호로 로그인한 admin에게 로그인 직후 한 번 보이는 경고. 경고는 로그인 응답에서만 오고 메모리에만 둔다. */
export function DirectoryWarningDialog() {
  const { warning, dismiss } = useDirectoryWarning()
  const navigate = useNavigate()
  if (warning === null) return null
  return (
    <Modal
      title="AD 연결 경고"
      onClose={dismiss}
      footer={
        <>
          <button type="button" onClick={dismiss}>
            닫기
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => {
              dismiss()
              void navigate('/admin/integrations')
            }}
          >
            외부연동 설정으로 이동
          </button>
        </>
      }
    >
      <p>{warning.message}</p>
    </Modal>
  )
}
