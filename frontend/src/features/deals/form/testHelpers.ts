import { cleanup, screen, waitFor } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { expect } from 'vitest'
import { renderAt } from '../../../test/mockApp'

/** 저장 뒤 상세 페이지 주소 형식. */
export const DETAIL_URL = /^\/deals\/\d{8}-[A-Z0-9]{4}$/

/** 시드의 Deal 이름으로 Deal code를 찾는다. 시드 code는 매번 같다. */
export async function codeOf(name: string): Promise<string> {
  await renderAt(`/deals?q=${encodeURIComponent(name)}`)
  const link = await screen.findByRole('link', { name })
  const href = link.getAttribute('href') ?? ''
  cleanup()
  return href.replace('/deals/', '')
}

/** 이름으로 찾은 Deal의 수정 화면을 열고 폼이 그려질 때까지 기다린다. */
export async function openEdit(name: string, role?: 'admin' | 'sales' | 'user') {
  const code = await codeOf(name)
  const view = await renderAt(`/deals/${code}/edit`, role ? { role } : {})
  await screen.findByRole('heading', { name: 'Deal 수정' })
  await screen.findByLabelText('Deal Name')
  return { ...view, code }
}

/** ContactPicker에서 회사명을 입력하고 담당자 목록에서 사람을 고른다. */
export async function pickPerson(user: UserEvent, label: string, company: string, person: string | RegExp) {
  const companyInput = screen.getByLabelText(`${label} 회사명`)
  await user.clear(companyInput)
  await user.type(companyInput, company)
  await user.click(screen.getByLabelText(`${label} 담당자명`))
  await user.click(await screen.findByRole('option', { name: person }))
}

export async function save(user: UserEvent) {
  await user.click(screen.getByRole('button', { name: '저장' }))
}

/** 상단 메뉴로 목록에 가서 키워드로 검색하고 그 Deal의 행을 돌려준다. */
export async function openList(user: UserEvent, query: string) {
  await waitFor(() => expect(screen.getByRole('link', { name: 'Deals' })).toBeVisible())
  await user.click(screen.getByRole('link', { name: 'Deals' }))
  const keyword = await screen.findByLabelText('키워드')
  await user.clear(keyword) // P5 Q1: 메뉴가 마지막 목록 조건(키워드 포함)을 복원한다
  await user.type(keyword, query)
  await user.click(screen.getByRole('button', { name: '검색' }))
  return screen.findByRole('row', { name: new RegExp(query) })
}
