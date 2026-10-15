import { useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useNavigate } from 'react-router'
import { mockControl } from '../../gateway'

/** 배지 옆 메뉴(계획 4.5): 데이터 초기화, 최초 설정 다시 시작, 저장소 장애 시뮬레이션, 지연 끄기. 목업 전용. */
export function MockPanel() {
  const panelId = useId()
  const [open, setOpen] = useState(false)
  return (
    <div className="mock-panel">
      <button type="button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)}>
        목업 메뉴
      </button>
      {open && <MockControls id={panelId} onDone={() => setOpen(false)} />}
    </div>
  )
}

function MockControls({ id, onDone }: { id: string; onDone: () => void }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [storageFailure, setStorageFailure] = useState(() => mockControl.isStorageFailure())
  const [latencyOn, setLatencyOn] = useState(() => mockControl.isLatencyOn())
  const [message, setMessage] = useState('')

  const reset = async () => {
    mockControl.resetData()
    await client.invalidateQueries()
    setMessage('데이터를 처음 상태로 되돌렸습니다.')
  }
  const restartSetup = () => {
    mockControl.restartSetup()
    client.clear()
    onDone()
    void navigate('/setup')
  }

  return (
    <div id={id} className="mock-panel-body" role="group" aria-label="목업 설정">
      <button type="button" onClick={() => void reset()}>
        데이터 초기화
      </button>
      <button type="button" onClick={restartSetup}>
        최초 설정 다시 시작
      </button>
      <label className="mock-toggle">
        <input
          type="checkbox"
          checked={storageFailure}
          onChange={(e) => {
            mockControl.setStorageFailure(e.target.checked)
            setStorageFailure(e.target.checked)
          }}
        />
        저장소 장애 시뮬레이션
      </label>
      <label className="mock-toggle">
        <input
          type="checkbox"
          checked={!latencyOn}
          onChange={(e) => {
            mockControl.setLatency(!e.target.checked)
            setLatencyOn(!e.target.checked)
          }}
        />
        지연 끄기
      </label>
      {message && <p role="status" className="hint">{message}</p>}
      <p className="hint">이 화면은 실제 연동이 아닙니다(가상 데이터).</p>
    </div>
  )
}
