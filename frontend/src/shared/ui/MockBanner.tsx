import { MockPanel } from './MockPanel'

/**
 * 모든 화면(로그인·최초 설정 포함) 맨 위에 고정되는 목업 표시. App이 한 번만 그린다.
 * 실제 연동으로 전환할 때 MockPanel과 함께 삭제한다.
 */
export function MockBanner() {
  return (
    <div className="mock-banner" role="region" aria-label="목업 안내">
      <strong className="mock-badge">UI 목업(가상 데이터)</strong>
      <span className="mock-banner-text">
        입력한 내용은 저장되지 않으며 새로고침하면 처음 상태로 돌아갑니다.
      </span>
      <MockPanel />
    </div>
  )
}
