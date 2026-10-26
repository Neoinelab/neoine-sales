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

describe('목록의 Next Action 바로가기 (AC-6)', () => {
  it('Next Action 내용은 Actions 탭 링크이고 누르면 Actions 탭이 열린다', async () => {
    const code = await dealCodeOf(1)
    const { user, location } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    const link = within(row).getByRole('link', { name: NEXT_ACTION_TEXT })

    expect(link).toHaveAttribute('href', actionsHref(code))
    await user.click(link)
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    expect(location()).toContain('tab=actions')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Deal 상세' })).toHaveAttribute('aria-selected', 'false')
  })

  it('키보드 Enter로도 같은 곳으로 이동한다', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    within(row).getByRole('link', { name: NEXT_ACTION_TEXT }).focus()
    await user.keyboard('{Enter}')

    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    expect(await screen.findByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
  })

  it('링크 안에는 내용만 있고 Due와 상태 라벨은 링크 밖 별도 칸에 보인다', async () => {
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const due = (await gateway.deals.list({ keyword: '한빛은행 ITDR' })).items.find((d) => d.name === '한빛은행 ITDR 도입')?.nextAction?.dueDate
    if (!due) throw new Error('시드 Deal 1의 Next Action이 필요합니다.')

    const link = within(row).getByRole('link', { name: NEXT_ACTION_TEXT })

    expect(link).toHaveTextContent(/^계약서 초안 검토$/)
    expect(within(row).getByText(due)).toBeVisible()
    expect(link).not.toContainElement(within(row).getByText(due))
    expect(within(row).getByText('Open')).toBeVisible()
    expect(within(row).queryByText(`Due ${due}`)).not.toBeInTheDocument()
  })

  it('Deal 이름 링크는 그대로 상세(첫 탭)로 간다', async () => {
    const code = await dealCodeOf(1)
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    expect(within(row).getByRole('link', { name: '한빛은행 ITDR 도입' })).toHaveAttribute('href', `/deals/${code}`)
  })

  it('Next Action이 없는 Deal은 —만 보이고 링크가 없다', async () => {
    const { client } = await renderAt('/deals?q=액션 없는 Deal')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '액션 없는 Deal' }))
    await client.invalidateQueries()
    const row = await rowOf(/액션 없는 Deal/)
    const column = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === 'Next Action')

    const cell = within(row).getAllByRole('cell')[column] as HTMLElement

    expect(cell).toHaveTextContent(/^—$/)
    expect(within(cell).queryByRole('link')).not.toBeInTheDocument()
    expect(within(row).queryAllByRole('link').filter((a) => a.getAttribute('href')?.includes('tab=actions'))).toEqual([])
  })
})
