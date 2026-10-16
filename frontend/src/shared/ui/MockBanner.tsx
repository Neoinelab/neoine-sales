import { gatewayMode } from '../../gateway/mode'
import { MockPanel } from './MockPanel'

/**
 * 모든 화면(로그인·최초 설정 포함) 맨 위에 고정되는 목업 표시. App이 한 번만 그린다.
 * mock 모드에서만 그린다(http 모드에서는 배너도 MockPanel도 없다). P8에서 MockPanel과 함께 삭제한다.
 */
export function MockBanner() {
  if (gatewayMode() !== 'mock') return null
  return (
    <div className="mock-banner" role="region" aria-label="목업 안내">
      <strong className="mock-badge">UI 목업(메모리 저장)</strong>
      <span className="mock-banner-text">
        입력한 내용은 메모리에만 저장되며 새로고침하면 초기화됩니다.
      </span>
      <MockPanel />
    </div>
  )
}
