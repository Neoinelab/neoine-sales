import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

describe('빠른 보기의 Users (AC-19)', () => {
  it('shows a Users value of zero as 0 instead of a dash', async () => {
    const { user, client } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const code = (within(row).getByRole('link', { name: /한빛은행 ITDR 도입/ }).getAttribute('href') ?? '').replace('/deals/', '')
    await gateway.deals.update(code, { users: 0 })
    await client.invalidateQueries()

    await waitFor(async () => {
      const fresh = await rowOf(/한빛은행 ITDR 도입/)
      expect(within(fresh).getByRole('button', { name: /빠른 보기/ })).toBeVisible()
    })
    await user.click(within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('button', { name: /빠른 보기/ }))

    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    const users = within(view).getByText('Users').closest('div') as HTMLElement
    expect(within(users).getByText('0')).toBeVisible()
  })
})
