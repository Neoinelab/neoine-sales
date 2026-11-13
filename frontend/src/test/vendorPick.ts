import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

/** 등록·수정 폼의 Vendor 선택 상자에서 이름으로 고른다(Vendor는 필수). 목록이 불러와질 때까지 기다린다. */
export async function pickVendor(user: UserEvent, name = 'Silverfort') {
  const select = screen.getByLabelText('Vendor')
  await within(select).findByRole('option', { name })
  await user.selectOptions(select, name)
}
