import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dataRows } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

describe('목록 조건 전환 (keepPreviousData)', () => {
  it('keeps the previous table on screen while the next condition loads', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const before = dataRows().length

    const original = gateway.deals.list.bind(gateway.deals)
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      await gate
      return original(query)
    })

    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))
    expect(location()).toContain('q=')

    // 응답이 오기 전에도 이전 표가 그대로 있고, 로딩 문구로 바뀌지 않는다.
    expect(screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })).toBeVisible()
    expect(dataRows()).toHaveLength(before)
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()

    release()
    await screen.findByText('총 3건')
    expect(dataRows()).toHaveLength(3)
  })
})
