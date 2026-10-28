// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { arrangement, chooseView, dragTile, tileOrder, viewRadio } from '../../../test/reportLayout'
import { openView, setupReportClock } from '../../../test/reportScreen'
import { SAVED_SAMPLES, VENDOR_CHART, savedReport } from '../../../test/savedReports'

// 지금 정책에서는 볼 수 있는 리포트는 모두 고칠 수 있어(`canEditReport` = `canViewReport`) 수정 권한이 없는 보기 사용자가 없다.
// 계획 AC23(수정 권한이 없는 사람은 저장 요청을 보내지 않는다)은 판정 함수를 거짓으로 바꿔 확인한다.
vi.mock('../../../shared/model/permissions', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../shared/model/permissions')>()),
  canEditReport: () => false,
}))

setupReportClock()

const NOTE = '보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다'
const REPORT = savedReport({ id: 51, name: '읽기 전용 배치', chart: VENDOR_CHART, layout: { view: 'both', order: ['table', 'chart'], arrange: 'stacked' } })
const layoutRequests = () => mockControl.savedReportRequests().filter((r) => r.op === 'layout')

describe('수정 권한이 없는 사람의 보기 화면 (AC23)', () => {
  async function open() {
    const rendered = await openView(REPORT.id, { savedReports: [...SAVED_SAMPLES, REPORT] })
    await screen.findByRole('table', { name: '조회 결과' })
    return rendered
  }

  it('shows the note that the view and the layout are not saved', async () => {
    await open()

    expect(screen.getByText(NOTE)).toBeVisible()
  })

  it('changes the view on the screen without sending any request', async () => {
    const { user } = await open()

    await chooseView(user, '표만')

    expect(viewRadio('표만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '차트 타일' })).not.toBeInTheDocument()
    expect(layoutRequests()).toEqual([])
    expect(screen.queryByText('배치 저장 중…')).not.toBeInTheDocument()
    expect(screen.queryByText('배치를 저장했습니다')).not.toBeInTheDocument()
  })

  it('moves the tiles on the screen without sending any request', async () => {
    await open()

    dragTile('표', '차트', 'right')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(layoutRequests()).toEqual([])
  })

  it('does not offer the edit link', async () => {
    await open()

    expect(screen.queryByRole('link', { name: '편집' })).not.toBeInTheDocument()
  })
})
