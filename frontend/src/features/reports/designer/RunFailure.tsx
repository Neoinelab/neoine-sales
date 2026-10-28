import type { ReportRunFailure } from '../../../shared/model/reportTypes'

/** 조회 실패 알림에 보일 위반 한 줄(위치 이름 + 서버 문구). */
export interface SummaryItem {
  key: string
  where: string | null
  message: string
}

/** 조회 실패 알림: 위반이면 "고칠 곳 N개" 목록, 그 밖의 실패는 서버 문구. 작성 탭의 조회 버튼 아래에 보인다. */
export function RunFailure({ failure, summary }: { failure: ReportRunFailure; summary: readonly SummaryItem[] }) {
  if (failure.kind !== 'invalid' || failure.issues.length === 0) {
    return (
      <p role="alert" className="error">
        {failure.message}
      </p>
    )
  }
  if (summary.length === 0) return null
  return (
    <div role="alert" className="report-summary">
      <strong>고칠 곳 {summary.length}개</strong>
      <ul>
        {summary.map((item) => (
          <li key={item.key}>
            {item.where ? `${item.where}: ` : ''}
            {item.message}
          </li>
        ))}
      </ul>
    </div>
  )
}
