import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { openDesigner, runQuery, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

describe('필드 목록', () => {
  // 테스트 코드: RQ-069
  it('필드를 엔티티별로 보이고 검색어로 거른다', async () => {
    // when: 디자이너를 연다
    const { user } = await openDesigner()

    // then: Deal과 Action에 각 엔티티의 필드가 있다
    const deal = screen.getByRole('group', { name: 'Deal' })
    const action = screen.getByRole('group', { name: 'Deal Actions' })
    expect(within(deal).getByRole('button', { name: '금액 컬럼에 추가' })).toBeVisible()
    expect(within(action).getByRole('button', { name: 'Action 건수 컬럼에 추가' })).toBeVisible()

    // when: 필드 검색에 VENDOR를 입력한다
    await user.type(screen.getByLabelText('필드 검색'), 'VENDOR')

    // then: Vendor만 남고 Status는 없다
    expect(screen.getByRole('button', { name: 'Vendor 컬럼에 추가' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Status 컬럼에 추가' })).not.toBeInTheDocument()
  })

  // 테스트 코드: CM-084
  it('Comments 그룹에서 본문과 작성·수정일자 및 작성자를 조회할 수 있다', async () => {
    // when: 새 리포트 작성 화면의 필드 목록을 연다
    const { user } = await openDesigner()

    const comments = within(screen.getByRole('group', { name: 'Comments' }))
    const labels = ['Comment 본문', '작성일자', '수정일자', '작성자']
    for (const label of labels) {
      await user.click(comments.getByRole('button', { name: `${label} 컬럼에 추가` }))
    }
    await runQuery(user)
    const table = await screen.findByRole('table', { name: '조회 결과' })
    expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual(labels)
    expect(screen.queryByRole('button', { name: /Comment\((Deal 전체|Action)\)/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Memo/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-069
  it('이름 부분 일치로 거르므로 bant로 BANT 필드 4개가 나온다', async () => {
    // when: 디자이너를 연다
    const { user } = await openDesigner()

    // when: 필드 검색에 bant를 입력한다
    await user.type(screen.getByLabelText('필드 검색'), 'bant')

    // then: BANT 필드 4개가 나온다
    expect(screen.getAllByRole('button', { name: /^BANT .* 컬럼에 추가$/ })).toHaveLength(4)
  })

  // 테스트 코드: RQ-069
  it.each([
    ['Deal code', '텍스트'],
    ['Vendor', '코드'],
    ['담당자', '사용자'],
    ['금액', '숫자'],
    ['Expected Close', '날짜'],
    ['등록일', '시각'],
  ])('%s 필드의 형식 이름은 %s로 보인다', async (label, kind) => {
    // when: 디자이너를 연다 (전제: 필드와 형식 매개변수)
    await openDesigner()

    // then: 그 필드 항목에 형식 이름이 보인다
    const item = screen.getByRole('button', { name: `${label} 컬럼에 추가` }).closest('li')

    expect(item).not.toBeNull()
    expect(within(item as HTMLElement).getByText(kind)).toBeVisible()
  })

  // 테스트 코드: RQ-070
  it('조건 추가 버튼은 조건에 쓸 수 있는 필드에만 있다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: Vendor에는 조건 추가 버튼이 있고 Action 건수에는 없다
    expect(screen.getByRole('button', { name: 'Vendor 조건 추가' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Action 건수 조건 추가' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-066
  it('카탈로그를 읽는 동안 로딩 문구를 보인다', async () => {
    // given: 끝나지 않는 카탈로그 요청
    vi.spyOn(gateway.reports, 'fields').mockImplementation(() => new Promise(() => undefined))

    // when: 디자이너 화면을 연다
    await renderAt('/reports/new')

    // then: 불러오는 중 문구가 보이고 필드 버튼은 없다
    expect(await screen.findByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Deal code 컬럼에 추가' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-066
  it('카탈로그 읽기가 실패하면 오류를 보이고 다시 시도하면 읽힌다', async () => {
    // given: 첫 요청이 실패하는 카탈로그
    const failure = new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '필드 목록을 불러오지 못했습니다' })
    vi.spyOn(gateway.reports, 'fields').mockRejectedValueOnce(failure)
    // when: 디자이너 화면을 연다
    const { user } = await renderAt('/reports/new')

    // then: 오류 알림에 서버 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('필드 목록을 불러오지 못했습니다')

    // when: 다시 시도를 누른다
    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    // then: 필드 목록이 보이고 알림이 사라진다
    expect(await screen.findByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('디자이너 첫 화면', () => {
  // 테스트 코드: RQ-067
  it('제목·초기화 버튼·빈 안내와 행 단위 안내를 보인다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 제목 새 리포트, 초기화 버튼, 조건 없음 안내, 행 단위 Deal 1건이 보인다
    expect(screen.getByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
    expect(screen.getByRole('button', { name: '초기화' })).toBeVisible()
    expect(screen.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()
    expect(screen.getAllByRole('status').find((el) => el.classList.contains('report-scope'))).toHaveTextContent('행 단위: Deal 1건')
  })

  // 테스트 코드: RQ-067
  it('작성·결과 두 탭만 있고 저장은 꺼져 있으며 저장 안 됨 표시가 없다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 탭은 둘이고 차트 탭이 없으며 저장 버튼은 꺼져 있고 저장 안 됨 표시가 없다
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
    expect(screen.queryByRole('tab', { name: /차트/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    expect(screen.queryByText(/저장 안 됨/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-067
  it('컬럼이 없으면 조회 버튼이 꺼져 있다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 조회 버튼이 꺼져 있다
    expect(screen.getByRole('button', { name: '조회' })).toBeDisabled()
  })
})
