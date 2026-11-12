import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

const NEXT_ACTION_TEXT = '계약서 초안 검토'

function actionsHref(code: string): string {
  return `/deals/${code}?tab=actions`
}

describe('목록의 Next Action 바로가기', () => {
  // Next Action 내용은 Actions 탭 링크다
  // 테스트 코드: DL-059
  it('Next Action 내용은 Actions 탭 링크이고 누르면 Actions 탭이 열린다', async () => {
    // given: Next Action이 있는 Deal
    const code = await dealCodeOf(1)
    const { user, location } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    const link = within(row).getByRole('link', { name: NEXT_ACTION_TEXT })
    expect(link).toHaveAttribute('href', actionsHref(code))

    // when: 링크를 누른다
    await user.click(link)

    // then: 상세의 Actions 탭이 열린다
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    expect(location()).toContain('tab=actions')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Deal 상세' })).toHaveAttribute('aria-selected', 'false')
  })

  // 키보드 Enter로도 Actions 탭으로 이동한다
  // 테스트 코드: DL-059
  it('키보드 Enter로도 같은 곳으로 이동한다', async () => {
    // given: 링크에 포커스
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    within(row).getByRole('link', { name: NEXT_ACTION_TEXT }).focus()
    // when: Enter를 누른다
    await user.keyboard('{Enter}')

    // then: Actions 탭이 열린다
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    expect(await screen.findByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
  })

  // 링크 안에는 내용만 있고 Due·상태는 링크 밖 칸에 있다
  // 테스트 코드: DL-059
  it('링크 안에는 내용만 있고 Due와 상태 라벨은 링크 밖 별도 칸에 보인다', async () => {
    // given: Next Action이 있는 Deal
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const due = (await gateway.deals.list({ keyword: '한빛은행 ITDR' })).items.find((d) => d.name === '한빛은행 ITDR 도입')?.nextAction?.dueDate
    if (!due) throw new Error('시드 Deal 1의 Next Action이 필요합니다.')

    // when: 링크 내용을 확인한다
    const link = within(row).getByRole('link', { name: NEXT_ACTION_TEXT })

    // then: 링크 텍스트는 내용뿐이다
    expect(link).toHaveTextContent(/^계약서 초안 검토$/)
    expect(within(row).getByText(due)).toBeVisible()
    expect(link).not.toContainElement(within(row).getByText(due))
    expect(within(row).getByText('Open')).toBeVisible()
    expect(within(row).queryByText(`Due ${due}`)).not.toBeInTheDocument()
  })

  // Deal 이름 링크는 상세 첫 탭으로 간다
  // 테스트 코드: DL-058
  it('Deal 이름 링크는 그대로 상세(첫 탭)로 간다', async () => {
    // given: Deal 행
    const code = await dealCodeOf(1)
    await renderAt('/deals?q=한빛은행 ITDR')
    // when: 이름 링크를 누른다
    const row = await rowOf(/한빛은행 ITDR 도입/)

    // then: 상세 첫 탭이 열린다
    expect(within(row).getByRole('link', { name: '한빛은행 ITDR 도입' })).toHaveAttribute('href', `/deals/${code}`)
  })

  // Next Action이 없으면 '—'만 보이고 링크가 없다
  // 테스트 코드: DL-059
  it('Next Action이 없는 Deal은 —만 보이고 링크가 없다', async () => {
    // given: Next Action이 없는 Deal
    const { client } = await renderAt('/deals?q=액션 없는 Deal')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '액션 없는 Deal' }))
    await client.invalidateQueries()
    const row = await rowOf(/액션 없는 Deal/)
    const column = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === 'Next Action')

    // when: 행을 확인한다
    const cell = within(row).getAllByRole('cell')[column] as HTMLElement

    // then: '—'만 있고 Next Action 링크가 없다
    expect(cell).toHaveTextContent(/^—$/)
    expect(within(cell).queryByRole('link')).not.toBeInTheDocument()
    expect(within(row).queryAllByRole('link').filter((a) => a.getAttribute('href')?.includes('tab=actions'))).toEqual([])
  })
})
