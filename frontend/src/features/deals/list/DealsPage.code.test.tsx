import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

const CODE_PATTERN = /\d{8}-[A-Z0-9]{4}/

describe('목록에서 Deal code 숨김', () => {
  it('shows no deal code anywhere in the text, but keeps it in the row link', async () => {
    const { user } = await renderAt('/deals?q=대한제조 MFA')
    const row = await rowOf(/대한제조 MFA 확대/)
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
    const link = within(row).getByRole('link', { name: '대한제조 MFA 확대' })
    expect(link.getAttribute('href')).toMatch(new RegExp(`^/deals/${CODE_PATTERN.source}$`))
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
    expect(screen.getByRole('link', { name: '상세 보기' }).getAttribute('href')).toMatch(/^\/deals\/\d{8}-/)
  })

  it('keeps accessible names and titles free of the code on the whole list', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)
    const names = [...document.querySelectorAll('[aria-label], [title]')].map(
      (el) => `${el.getAttribute('aria-label') ?? ''} ${el.getAttribute('title') ?? ''}`,
    )
    expect(names.join('\n')).not.toMatch(CODE_PATTERN)
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
  })

  it('still finds a deal by searching its code', async () => {
    const { user } = await renderAt('/deals?q=대한제조 MFA')
    const row = await rowOf(/대한제조 MFA 확대/)
    const code = within(row).getByRole('link').getAttribute('href')?.split('/').pop() ?? ''
    expect(code).toMatch(CODE_PATTERN)
    await user.clear(screen.getByLabelText('키워드'))
    await user.type(screen.getByLabelText('키워드'), `${code}{Enter}`)
    expect(await rowOf(/대한제조 MFA 확대/)).toBeVisible()
    expect(screen.getAllByRole('row')).toHaveLength(2)
  })
})
