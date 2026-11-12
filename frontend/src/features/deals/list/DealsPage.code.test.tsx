import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

const CODE_PATTERN = /\d{8}-[A-Z0-9]{4}/

describe('목록에서 Deal code 숨김', () => {
  // 화면 글자에는 Deal code가 없고 링크 주소에만 있다
  // 테스트 코드: DL-060
  it('shows no deal code anywhere in the text, but keeps it in the row link', async () => {
    // given: 시드 목록
    const { user } = await renderAt('/deals?q=대한제조 MFA')
    // when: 목록을 연다
    const row = await rowOf(/대한제조 MFA 확대/)
    // then: 본문 글자에 code가 없고 이름 링크 주소에는 있다
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
    const link = within(row).getByRole('link', { name: '대한제조 MFA 확대' })
    expect(link.getAttribute('href')).toMatch(new RegExp(`^/deals/${CODE_PATTERN.source}$`))
    // when: 빠른 보기를 연다
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    // then: 빠른 보기에도 code가 없고 상세 링크 주소에만 있다
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
    expect(screen.getByRole('link', { name: '상세 보기' }).getAttribute('href')).toMatch(/^\/deals\/\d{8}-/)
  })

  // 접근성 이름과 title에도 Deal code가 없다
  // 테스트 코드: DL-060
  it('keeps accessible names and titles free of the code on the whole list', async () => {
    // given: 시드 목록
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)
    // when: 목록 전체를 확인한다
    const names = [...document.querySelectorAll('[aria-label], [title]')].map(
      (el) => `${el.getAttribute('aria-label') ?? ''} ${el.getAttribute('title') ?? ''}`,
    )
    // then: aria-label·title에 code가 없다
    expect(names.join('\n')).not.toMatch(CODE_PATTERN)
    expect(document.body.textContent).not.toMatch(CODE_PATTERN)
  })

  // code로 검색은 된다
  // 테스트 코드: DL-060
  it('still finds a deal by searching its code', async () => {
    // given: code를 아는 Deal
    const { user } = await renderAt('/deals?q=대한제조 MFA')
    const row = await rowOf(/대한제조 MFA 확대/)
    const code = within(row).getByRole('link', { name: '대한제조 MFA 확대' }).getAttribute('href')?.split('/').pop() ?? ''
    expect(code).toMatch(CODE_PATTERN)
    // when: 키워드에 code를 넣고 검색한다
    await user.clear(screen.getByLabelText('키워드'))
    await user.type(screen.getByLabelText('키워드'), `${code}{Enter}`)
    // then: 그 Deal 행만 보인다
    expect(await rowOf(/대한제조 MFA 확대/)).toBeVisible()
    expect(screen.getAllByRole('row')).toHaveLength(2)
  })
})
