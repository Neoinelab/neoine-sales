// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { lastChart, renderedCharts } from '../../../test/chartMock'
import { arrangement, chooseView, queryTile, tile, tileOrder, viewRadio } from '../../../test/reportLayout'
import { openView, setupReportClock } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
const MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
const open = (reports = [WITH_CHART]) => openView(reports[0]?.id ?? WITH_CHART.id, { savedReports: [...SAVED_SAMPLES, ...reports] })

describe('보기 화면의 차트 타일', () => {
  // 테스트 코드: RC-074
  it('차트가 있는 리포트는 표 타일과 차트 타일을 보이고 설정 패널 없이 차트를 그린다', async () => {
    // when: 차트가 있는 리포트의 보기 화면을 연다
    await open()

    // then: 차트 그림과 표가 보이고 기본 배치(표 → 차트, 두 줄)이며 저장 제목이 반영되고 설정 패널·차트 만들기·삭제·설정 버튼이 없다
    expect(await screen.findByRole('img')).toBeVisible()
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(tileOrder()).toEqual(['표', '차트']) // 저장된 값이 없으면 기본 배치(표 → 차트, 두 줄)
    expect(arrangement()).toBe('stacked')
    expect(lastChart().type).toBe('bar')
    expect(lastChart().options).toMatchObject({ plugins: { title: { display: true, text: VENDOR_CHART.title } } })
    for (const label of ['범주', '차트 제목', '범례']) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    for (const name of ['차트 만들기', '차트 삭제', '묶은 세로 막대', '차트 설정']) expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-074
  it('결과 탭이 없다', async () => {
    // when: 차트가 있는 리포트의 보기 화면을 연다
    await open()
    await screen.findByRole('img')

    // then: 탭 목록과 탭이 없다
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-074
  it('표만 보기를 고르면 차트 타일이 숨고 표+차트로 돌아오면 다시 보인다', async () => {
    // given: 차트가 있는 리포트의 보기 화면
    const { user } = await open()
    await screen.findByRole('img')

    // when: 보기 방식을 표만으로 바꾼다
    await chooseView(user, '표만')

    // then: 표만 보이고 차트 그림과 차트 타일이 없다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(queryTile('차트')).toBeNull()

    // when: 보기 방식을 표+차트로 되돌린다
    await chooseView(user, '표+차트')

    // then: 차트 그림이 다시 보인다
    expect(await screen.findByRole('img')).toBeVisible()
  })

  // 테스트 코드: RC-074
  it('차트만 보기는 차트 타일만 보인다', async () => {
    // given: 차트가 있는 리포트의 보기 화면
    const { user } = await open()
    await screen.findByRole('img')

    // when: 보기 방식을 차트만으로 바꾼다
    await chooseView(user, '차트만')

    // then: 표 타일과 결과 표가 없고 차트 그림만 보인다
    expect(queryTile('표')).toBeNull()
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(screen.getByRole('img')).toBeVisible()
  })

  // 테스트 코드: RC-074
  it('차트가 없는 리포트는 표 타일만 열리고 차트 보기 방식은 꺼져 있다', async () => {
    // when: 차트가 없는 리포트의 보기 화면을 연다
    await openView(MINE_PUBLIC.id)

    // then: 표만 보이고 표+차트·차트만 보기가 비활성이며 차트 타일·차트 만들기·그려진 차트가 없다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(viewRadio('표+차트')).toBeDisabled()
    expect(viewRadio('차트만')).toBeDisabled()
    expect(queryTile('차트')).toBeNull()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
    expect(renderedCharts()).toHaveLength(0)
  })

  // 테스트 코드: RC-074
  it('서버가 차트 문제를 알리면 저장 차트를 읽을 수 없었다고 안내한다', async () => {
    // given: 차트를 읽을 수 없는 저장 리포트
    const broken = savedReport({ id: 22, name: '깨진 차트', chartProblem: PROBLEM })
    // when: 보기 화면을 연다
    await open([broken])
    // then: 안내 문구가 보이고 그림이 없으며 차트만 보기는 비활성이다
    await screen.findByRole('table', { name: '조회 결과' })

    expect(screen.getByText(PROBLEM)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(viewRadio('차트만')).toBeDisabled()
  })

  // 테스트 코드: RC-074
  it('차트 설정이 지금 결과와 맞지 않으면 잘못 그리지 않고 안내한다', async () => {
    // given: 범주가 그룹 열이 아닌 저장 차트의 리포트
    const mismatched = savedReport({ id: 23, name: '어긋난 차트', chart: { ...VENDOR_CHART, category: 1 } })
    // when: 보기 화면을 연다
    await open([mismatched])

    // then: "차트 설정이 지금 결과와 맞지 않습니다…" 안내가 보이고 그림이 없다
    expect(await screen.findByText(MISMATCH)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
