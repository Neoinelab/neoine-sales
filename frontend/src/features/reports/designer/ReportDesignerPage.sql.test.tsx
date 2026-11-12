import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { resultOf } from '../../../test/reportDesigner'
import { showTab } from '../../../test/reportLayout'
import { addColumn, openAndRun, openDesigner, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const SQL = 'SELECT d.deal_code FROM deals d ORDER BY 1 LIMIT 100'

describe('생성 SQL', () => {
  // 테스트 코드: RQ-100
  it('처음 조회하기 전에는 안내만 보이고 SQL 입력칸이 없다', async () => {
    // when: 디자이너를 연다
    const { container } = await openDesigner()

    // then: 조회 전 안내가 보이고 SQL 입력칸이 없다
    expect(screen.getByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).toBeInTheDocument()
    expect(container.querySelector('textarea')).toBeNull()
    expect(screen.queryByRole('textbox', { name: /SQL/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-100
  it('조회하면 생성 SQL이 읽기 전용으로 보인다', async () => {
    // when: Deal code 컬럼으로 조회한다 (전제: 서버가 SQL을 돌려준다)
    const { container } = await openAndRun(resultOf({ sql: SQL }), 'Deal code')

    // then: 접이식 영역 안에 pre로 보이고 편집할 수 없으며 조회 전 안내는 사라진다
    const summary = screen.getByText('생성 SQL 보기(읽기 전용)')
    expect(summary.closest('details')).not.toBeNull()
    const pre = screen.getByText(SQL)
    expect(pre.tagName).toBe('PRE')
    expect(pre).toHaveAttribute('tabindex', '0')
    expect(container.querySelector('textarea')).toBeNull()
    expect(container.querySelector('[contenteditable="true"]')).toBeNull()
    expect(screen.queryByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-100
  it('다시 조회하면 최신 SQL이 보인다', async () => {
    // given: 첫 조회를 마친 결과
    const { user } = await openAndRun(resultOf({ sql: SQL }), 'Deal code')

    // when: 작성 탭에서 컬럼을 더하고 다시 조회한다
    await showTab(user, 'design')
    await addColumn(user, 'Deal 이름')
    const next = 'SELECT d.deal_code, d.name FROM deals d LIMIT 100'
    mockControl.setReportQueryHandler(() => resultOf({ sql: next }))
    await user.click(screen.getByRole('button', { name: '조회' }))

    // then: 새 SQL이 보이고 이전 SQL은 없다
    expect(await screen.findByText(next)).toBeInTheDocument()
    expect(screen.queryByText(SQL)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-100
  it('SQL 보기는 결과 탭에 있고 작성 탭이 보일 때는 숨는다', async () => {
    // when: 결과가 있는 설계를 조회한다
    const { user } = await openAndRun(resultOf({ sql: SQL }), 'Deal code')
    // then: 결과 탭에서 SQL 보기가 보인다
    expect(screen.getByText('생성 SQL 보기(읽기 전용)')).toBeVisible()

    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')

    // then: SQL 보기가 숨는다
    expect(screen.getByText('생성 SQL 보기(읽기 전용)')).not.toBeVisible()
  })
})
