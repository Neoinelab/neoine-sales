import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { DEFAULT_DEALS_URL_PATTERN } from '../../../test/dealsUrl'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows } from './testHelpers'

describe('Deals 필터: Next Action 상태', () => {
  // Next Action 상태 선택은 다섯 가지다
  // 테스트 코드: DL-083
  it('offers the five choices in the "Next Action 상태" select', async () => {
    // given: 목록 필터 바
    await renderAt(ALL_DEALS)

    // when: 선택 상자를 확인한다
    const select = await screen.findByLabelText('Next Action 상태')

    // then: 전체·Open·종료(수행)·종료(미수행)·종료(전체)가 있다
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체',
      'Open',
      '종료(수행)',
      '종료(미수행)',
      '종료(전체)',
    ])
  })

  // 선택이 next_status로 URL에 쓰이고 1페이지로 간다
  // 테스트 코드: DL-083
  it('puts the choice in the URL as next_status and keeps the first page', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt('/deals?year=all&page=2')

    // when: 상태를 고른다
    await user.selectOptions(await screen.findByLabelText('Next Action 상태'), 'Open')

    // then: URL에 next_status가 쓰이고 page가 없다
    expect(location()).toContain('next_status=open')
    expect(location()).not.toContain('page=')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
  })

  // 종료 상태 선택이 next_status 값으로 쓰인다
  // 테스트 코드: DL-083
  it.each([
    ['종료(수행)', 'done'],
    ['종료(미수행)', 'not_done'],
    ['종료(전체)', 'closed'],
  ])('writes %s as next_status=%s and tells nothing matches while every Next Action is Open', async (label, wire) => {
    // given: 모든 Next Action이 Open인 시드
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 종료 계열 상태를 고른다
    await user.selectOptions(screen.getByLabelText('Next Action 상태'), label)

    // then: URL 값이 맞고 일치하는 Deal이 없다는 문구가 보인다
    expect(location()).toContain(`next_status=${wire}`)
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  // URL로 선택을 복원하고 Open Deal을 보인다
  // 테스트 코드: DL-083
  it('restores the select from the URL and shows the Open deals', async () => {
    // given: next_status=open 주소
    await renderAt('/deals?next_status=open')

    // when: 그 주소를 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 선택이 Open이고 Open Deal이 보인다
    expect(screen.getByLabelText('Next Action 상태')).toHaveDisplayValue('Open')
  })

  // not_done은 종료(미수행)으로 복원된다
  // 테스트 코드: DL-083
  it('restores not_done as 종료(미수행)', async () => {
    // when: 그 주소를 연다 (전제: next_status=not_done 주소)
    await renderAt('/deals?next_status=not_done')

    // then: 선택이 종료(미수행)이다
    expect(await screen.findByLabelText('Next Action 상태')).toHaveDisplayValue('종료(미수행)')
  })

  // 잘못된 URL 값은 무시하고 전체를 보인다
  // 테스트 코드: DL-072
  it('ignores a wrong URL value and lists everything', async () => {
    // given: 틀린 next_status가 든 주소
    await renderAt('/deals?next_status=bogus')

    // when: 그 주소를 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 전체로 표시되고 모두 나온다
    expect(screen.getByLabelText('Next Action 상태')).toHaveDisplayValue('전체')
    expect(dataRows().length).toBeGreaterThan(0)
  })

  // 초기화하면 상태 선택이 전체로 돌아간다
  // 테스트 코드: DL-083
  it('resets the status choice with the reset button', async () => {
    // given: 상태가 걸린 목록
    const { user, location } = await renderAt('/deals?next_status=closed')

    // when: 초기화를 누른다
    await user.click(await screen.findByRole('button', { name: '초기화' }))

    // then: 선택이 전체이다
    expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN)
    expect(screen.getByLabelText('Next Action 상태')).toHaveDisplayValue('전체')
  })
})

describe('Deals 목록: Next Action 열의 상태 라벨', () => {
  // 기준 Next Action의 내용·Due·상태 라벨이 각자 칸에 보인다
  // 테스트 코드: DL-059
  it('shows the text, the due date and the status label of the basis Next Action in separate columns', async () => {
    // given: Next Action이 있는 Deal
    await renderAt(ALL_DEALS)

    // when: 목록을 연다
    const row = await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 세 값이 각각의 칸에 있다
    expect(row).toHaveTextContent('계약서 초안 검토')
    expect(row).toHaveTextContent('Open')
  })
})

describe('Deals 목록: Next Action·Due·상태 칸은 모든 상태에서 내용·Due·상태 라벨을 보인다', () => {
  // 상태별로 내용·Due·라벨이 보이고 다른 라벨은 없다
  // 테스트 코드: DL-059
  it.each([
    ['open', 'Open'],
    ['done', '종료(수행)'],
    ['notDone', '종료(미수행)'],
  ] as const)('shows the text, the due date and the label of a %s Next Action', async (status, label) => {
    // given: 상태가 다른 기준 Next Action
    const code = await dealCodeOf(1)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const basis = (await gateway.actions.list(code, {})).find((a) => a.nextAction === '계약서 초안 검토')
    if (!basis) throw new Error('기준 Action이 없습니다.')
    if (!basis.dueDate) throw new Error('기준 Action에 Due가 필요합니다.')
    if (status !== 'open') await gateway.actions.changeNextActionStatus(basis.id, { status, memo: '' }) // 시드는 이미 Open

    // when: 목록을 읽는다
    await client.invalidateQueries()

    // then: 그 상태 라벨만 보인다
    await waitFor(() => {
      const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
      expect(within(row).getByText(label)).toBeVisible()
      expect(row).toHaveTextContent('계약서 초안 검토')
      expect(row).toHaveTextContent(basis.dueDate as string)
    })
    const labels = ['Open', '종료(수행)', '종료(미수행)'].filter((l) => l !== label)
    const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
    for (const other of labels) expect(within(row).queryByText(other)).not.toBeInTheDocument()
  })
})
