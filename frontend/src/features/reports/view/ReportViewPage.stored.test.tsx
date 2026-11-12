// 보기·편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import '../designer/ReportEditPage'
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { setupReportClock } from '../../../test/reportScreen'
import { MINE_PUBLIC, brokenStoredReport } from '../../../test/savedReports'

setupReportClock()

const STORED_INVALID = '저장된 리포트 정의를 읽을 수 없습니다.'
const NOT_FOUND_TEXT = '리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.'
const BROKEN = brokenStoredReport({ id: 20, name: '읽을 수 없는 정의' })

describe('저장 정의를 읽을 수 없는 리포트', () => {
  // 테스트 코드: RS-066
  it('목록에는 남고 보기·편집 화면은 서버 문구의 오류 배너만 보인다', async () => {
    // given: 저장 정의를 읽을 수 없는 내 리포트와 정상 리포트
    const savedReports = [MINE_PUBLIC, BROKEN]
    // when: 목록을 연다
    await renderAt('/reports', { savedReports })
    // then: 깨진 리포트 행이 있다
    expect(await screen.findByRole('link', { name: BROKEN.name })).toBeVisible()
  })

  // 테스트 코드: RS-066
  it('보기 화면은 오류 배너만 보이고 찾을 수 없음 안내나 실행 요청이 없다', async () => {
    // when: 보기 화면을 연다 (전제: 저장 정의를 읽을 수 없는 내 리포트)
    await renderAt(`/reports/${BROKEN.id}`, { savedReports: [BROKEN] })
    // then: 서버 문구의 오류 배너가 보이고 찾을 수 없음 안내와 실행 요청은 없다
    expect(await screen.findByText(STORED_INVALID)).toBeVisible()
    expect(screen.queryByText(NOT_FOUND_TEXT)).not.toBeInTheDocument()
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toEqual([])
  })

  // 테스트 코드: RS-066
  it('편집 화면은 오류 배너만 보이고 설계가 실리지 않는다', async () => {
    // when: 편집 화면을 연다 (전제: 저장 정의를 읽을 수 없는 내 리포트)
    await renderAt(`/reports/${BROKEN.id}/edit`, { savedReports: [BROKEN] })
    // then: 서버 문구의 오류 배너가 보이고 설계 편집 화면과 찾을 수 없음 안내는 없다
    expect(await screen.findByText(STORED_INVALID)).toBeVisible()
    expect(screen.queryByText(NOT_FOUND_TEXT)).not.toBeInTheDocument()
    expect(screen.queryByRole('tablist', { name: '리포트 디자이너' })).not.toBeInTheDocument()
    expect(mockControl.reportQueries()).toEqual([])
  })
})
