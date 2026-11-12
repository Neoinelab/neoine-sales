// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { arrangement, chooseView, dragTile, tileOrder, viewRadio } from '../../../test/reportLayout'
import { openView, setupReportClock } from '../../../test/reportScreen'
import { SAVED_SAMPLES, VENDOR_CHART, savedReport } from '../../../test/savedReports'

// 지금 정책에서는 볼 수 있는 리포트는 모두 고칠 수 있어(`canEditReport` = `canViewReport`) 수정 권한이 없는 보기 사용자가 없다.
// 수정 권한이 없는 사람이 저장 요청을 보내지 않는 규칙은 판정 함수를 거짓으로 바꿔 확인한다.
vi.mock('../../../shared/model/permissions', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../shared/model/permissions')>()),
  canEditReport: () => false,
}))

setupReportClock()

const NOTE = '보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다'
const REPORT = savedReport({ id: 51, name: '읽기 전용 배치', chart: VENDOR_CHART, layout: { view: 'both', order: ['table', 'chart'], arrange: 'stacked' } })
const layoutRequests = () => mockControl.savedReportRequests().filter((r) => r.op === 'layout')

describe('수정 권한이 없는 사람의 보기 화면', () => {
  async function open() {
    const rendered = await openView(REPORT.id, { savedReports: [...SAVED_SAMPLES, REPORT] })
    await screen.findByRole('table', { name: '조회 결과' })
    return rendered
  }

  // 테스트 코드: RS-102
  it('보기 방식과 배치가 저장되지 않는다는 안내를 보인다', async () => {
    // when: 수정 권한이 없는 사용자로 보기 화면을 연다
    await open()

    // then: 안내가 보인다
    expect(screen.getByText(NOTE)).toBeVisible()
  })

  // 테스트 코드: RS-102
  it('보기 방식은 화면에서만 바뀌고 요청을 보내지 않는다', async () => {
    // given: 수정 권한이 없는 보기 화면
    const { user } = await open()

    // when: 보기 방식을 표만으로 바꾼다
    await chooseView(user, '표만')

    // then: 화면은 바뀌고 배치 저장 요청과 저장 상태 표시가 없다
    expect(viewRadio('표만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '차트 타일' })).not.toBeInTheDocument()
    expect(layoutRequests()).toEqual([])
    expect(screen.queryByText('배치 저장 중…')).not.toBeInTheDocument()
    expect(screen.queryByText('배치를 저장했습니다')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-102
  it('타일 이동은 화면에서만 바뀌고 요청을 보내지 않는다', async () => {
    // given: 수정 권한이 없는 보기 화면
    await open()

    // when: 표 타일을 차트 타일 오른쪽에 놓는다
    dragTile('표', '차트', 'right')

    // then: 순서와 한 줄 배치가 바뀌고 배치 저장 요청이 없다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(layoutRequests()).toEqual([])
  })

  // 테스트 코드: RS-102
  it('편집 링크가 없다', async () => {
    // when: 수정 권한이 없는 사용자로 보기 화면을 연다
    await open()

    // then: 편집 링크가 없다
    expect(screen.queryByRole('link', { name: '편집' })).not.toBeInTheDocument()
  })
})
