import { useState } from 'react'
import { useSaveSetupStorage, useTestSetupStorage } from '../../data/setup'
import { directoryErrorMessage } from '../../shared/directory/messages'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'
import { Notice } from '../../shared/ui/Notice'

/** 2단계: 첨부 파일을 저장할 서버 디렉터리. 검증 문구는 서버(mock)가 준다. 저장 전에 쓰기 테스트를 해 볼 수 있다. */
export function StorageStep({ onBack }: { onBack: () => void }) {
  const save = useSaveSetupStorage()
  const test = useTestSetupStorage()
  const [path, setPath] = useState('')
  const [tested, setTested] = useState(false)
  const busy = save.isPending || test.isPending

  function runTest() {
    save.reset()
    setTested(false)
    test.mutate(path, { onSuccess: () => setTested(true) })
  }

  return (
    <form
      className="setup-card"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        test.reset()
        setTested(false)
        save.mutate(path)
      }}
    >
      <h2>파일 저장 위치</h2>
      <p className="hint">Deal 첨부 파일이 저장될 서버의 절대 경로를 입력합니다. 예: /data/neoine-sales/files</p>
      <p className="hint">나중에 Admin &gt; Settings &gt; 외부연동에서 바꿀 수 있습니다. 위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다.</p>
      <ErrorBanner error={save.error ?? test.error} format={directoryErrorMessage} />
      {tested && (
        <Notice kind="success" onClose={() => setTested(false)}>
          쓰기 테스트에 성공했습니다.
        </Notice>
      )}
      <TextField label="저장 경로" name="storage_path" value={path} onChange={setPath} />
      <div className="actions">
        <button type="button" onClick={onBack}>
          AD 서버 다시 등록
        </button>
        <button type="button" disabled={busy} onClick={runTest}>
          쓰기 테스트
        </button>
        <button type="submit" className="primary" disabled={busy}>
          저장 위치 등록
        </button>
      </div>
    </form>
  )
}
