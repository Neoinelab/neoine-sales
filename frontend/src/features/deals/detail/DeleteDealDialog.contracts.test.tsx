import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { defaultMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'

/** Deal 삭제 확인 팝업의 라이선스 계약 건수(AC21): 계약도 함께 삭제되므로 건수를 알려 준다. */
async function openDialog(no: number, title: string) {
  const view = await renderAt(await detailPath(no), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: title })
  await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
  return { ...view, dialog: await screen.findByRole('dialog', { name: 'Deal 삭제' }) }
}

describe('Deal 삭제 팝업의 계약 건수 (AC21)', () => {
  it('shows the number of license contracts that are deleted together', async () => {
    const code = await dealCodeOf(11)
    await defaultMock.signInAs(USER_ID.root)
    const count = (await gateway.deals.impact(code)).licenseContractCount
    expect(count).toBeGreaterThan(0)

    const { dialog } = await openDialog(11, '청명대학교 SSO/MFA')

    await waitFor(() => expect(dialog).toHaveTextContent(`라이선스 계약 ${count}건`))
    expect(dialog).toHaveTextContent('복구할 수 없습니다')
  })

  it('shows 0 for a deal without contracts', async () => {
    const { dialog } = await openDialog(2, '대한제조 MFA 확대')

    await waitFor(() => expect(dialog).toHaveTextContent('라이선스 계약 0건'))
  })

  it('removes the contracts together with the deal', async () => {
    const code = await dealCodeOf(11)
    await defaultMock.signInAs(USER_ID.root)
    const before = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)).items.filter((c) => c.dealCode === code)
    expect(before.length).toBeGreaterThan(0)

    await gateway.deals.remove(code, code)

    const after = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)).items.filter((c) => c.dealCode === code)
    expect(after).toEqual([])
  })
})
