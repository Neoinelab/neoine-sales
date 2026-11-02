import { screen } from '@testing-library/react'
import { vi } from 'vitest'
import { mockControl } from './fake/default'
import { renderAt, type RenderAtOptions } from './mockApp'

type Rendered = Awaited<ReturnType<typeof renderAt>>

/**
 * 앱에서 계정을 직접 관리하는(local) 시스템으로 화면을 연다. 최초 설정은 끝나 있고 시드 사용자는 그대로다.
 * `renderAt`이 시드로 되돌린 직후 인증 방식을 local로 바꾼다(호출한 테스트가 `vi.restoreAllMocks()`로 정리한다).
 */
export async function renderLocalAt(url: string, options: RenderAtOptions = {}): Promise<Rendered> {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.setAuthMode('local')
  })
  return renderAt(url, options)
}

/** 상단 바의 사용자 메뉴를 연다(이미 열려 있으면 그대로). */
export async function openUserMenu(user: Rendered['user']): Promise<HTMLElement> {
  const trigger = await screen.findByRole('button', { name: '사용자 메뉴' })
  if (trigger.getAttribute('aria-expanded') !== 'true') await user.click(trigger)
  return screen.findByRole('menu')
}

/** 사용자 메뉴에서 로그아웃한다. */
export async function logOutFromMenu(user: Rendered['user']): Promise<void> {
  await openUserMenu(user)
  await user.click(screen.getByRole('menuitem', { name: '로그아웃' }))
}

/** 최초 설정이 아직 안 된 상태(인증 방식 미선택)로 `/setup`을 열고 "인증 방식" 단계가 보일 때까지 기다린다. */
export async function openFreshSetup(): Promise<Rendered> {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  const view = await renderAt('/setup', { role: null })
  await screen.findByRole('heading', { name: '인증 방식' })
  return view
}

/** "앱에서 직접 관리"를 골라 저장 위치 단계까지 간다. */
export async function openLocalStorageStep(): Promise<Rendered> {
  const view = await openFreshSetup()
  await view.user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))
  await screen.findByRole('heading', { name: '파일 저장 위치' })
  return view
}

/** 저장 위치까지 마치고 local 관리자 등록 단계를 연다. */
export async function openLocalAdminStep(): Promise<Rendered> {
  const view = await openLocalStorageStep()
  await view.user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')
  await view.user.click(screen.getByRole('button', { name: '저장 위치 등록' }))
  await screen.findByRole('heading', { name: '관리자 등록' })
  return view
}
