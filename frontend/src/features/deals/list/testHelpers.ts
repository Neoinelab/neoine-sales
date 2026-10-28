import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

/** 이름으로 목록 행을 찾는다(행의 접근 가능한 이름에 Deal 이름이 들어 있다). */
export async function rowOf(name: string | RegExp) {
  return screen.findByRole('row', { name })
}

/** 머리글 행을 뺀 데이터 행. 빠른 보기를 펼치지 않은 상태에서 쓴다. */
export function dataRows() {
  return screen.getAllByRole('row').slice(1)
}

/** 오늘로부터 offset일 뒤의 로컬 날짜(YYYY-MM-DD). */
export function isoDay(offset: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 전체 Deal(연도 '전체')을 전제로 하는 목록 테스트의 시작 주소. 기본 조건(올해)이 붙지 않는다. */
export const ALL_DEALS = '/deals?year=all'

/** 필터 바(form role=search "Deal 필터") 안에서 질의한다. 행의 "Forecast 편집" 버튼과 겹치지 않게 한다. */
export function filterBar() {
  return within(screen.getByRole('search', { name: 'Deal 필터' }))
}

/** 필터 바가 나타날 때까지 기다린 뒤 그 안에서 질의한다. */
export async function findFilterBar() {
  return within(await screen.findByRole('search', { name: 'Deal 필터' }))
}

/** 필터 바의 Forecast 버튼(접근 이름 "Forecast <요약>"). */
export function forecastButton(summary: string | RegExp = /^Forecast /) {
  return filterBar().getByRole('button', { name: typeof summary === 'string' ? `Forecast ${summary}` : summary })
}

/** Forecast 패널이 닫혀 있으면 열고, 그 안의 질의 도구를 돌려준다. */
export async function openForecastPanel(user: UserEvent) {
  await screen.findByRole('search', { name: 'Deal 필터' })
  const button = forecastButton()
  if (button.getAttribute('aria-expanded') !== 'true') await user.click(button)
  return within(screen.getByRole('group', { name: 'Forecast' }))
}

/** Forecast 체크박스를 코드 이름으로 켜거나 끈다(패널은 열린 채 둔다). */
export async function toggleForecast(user: UserEvent, name: string | RegExp) {
  const panel = await openForecastPanel(user)
  await user.click(panel.getByRole('checkbox', { name }))
}

/** 필터 바의 Quarter 버튼(접근 이름 "Quarter <요약>", 요약: 전체 또는 "Q1, Q3"). */
export function quarterButton(summary: string | RegExp = /^Quarter /) {
  return filterBar().getByRole('button', { name: typeof summary === 'string' ? `Quarter ${summary}` : summary })
}

/** Quarter 패널이 닫혀 있으면 열고, 그 안의 질의 도구를 돌려준다. */
export async function openQuarterPanel(user: UserEvent) {
  await screen.findByRole('search', { name: 'Deal 필터' })
  const button = quarterButton()
  if (button.getAttribute('aria-expanded') !== 'true') await user.click(button)
  return within(screen.getByRole('group', { name: 'Quarter' }))
}

/** Quarter 체크박스(이름 "Q1"~"Q4")를 켜거나 끈다(패널은 열린 채 둔다). */
export async function toggleQuarter(user: UserEvent, name: string) {
  const panel = await openQuarterPanel(user)
  await user.click(panel.getByRole('checkbox', { name }))
}

/** Quarter 패널의 "전체" 버튼으로 선택을 모두 지운다. */
export async function clearQuarter(user: UserEvent) {
  const panel = await openQuarterPanel(user)
  await user.click(panel.getByRole('button', { name: '전체' }))
}

/** 버튼의 aria-describedby가 가리키는 안내 문구(없으면 null). */
export function describedText(button: HTMLElement): string | null {
  const id = button.getAttribute('aria-describedby')
  return id ? (document.getElementById(id)?.textContent ?? null) : null
}
