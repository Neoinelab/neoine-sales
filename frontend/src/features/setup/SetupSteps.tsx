export type StepNo = 1 | 2 | 3

const STEPS: readonly { no: StepNo; label: string }[] = [
  { no: 1, label: '1. AD 서버 등록' },
  { no: 2, label: '2. 파일 저장 위치' },
  { no: 3, label: '3. 관리자 등록' },
]

/** 3단계 진행 표시. 현재 단계는 aria-current="step", 끝낸 단계는 "완료"를 붙인다. */
export function SetupSteps({ current, done }: { current: StepNo; done: readonly boolean[] }) {
  return (
    <ol className="setup-steps" aria-label="설정 단계">
      {STEPS.map((step, index) => (
        <li key={step.no} aria-current={step.no === current ? 'step' : undefined} data-done={done[index] ? 'true' : undefined}>
          <span>{step.label}</span>
          {done[index] && <span className="badge">완료</span>}
        </li>
      ))}
    </ol>
  )
}
