import { screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import { gateway } from '../../gateway'
import type { DashboardSummary } from '../../shared/model/types'

/** 시드 날짜가 기준일 상대값이라 기준일을 고정한다(2026-10-15, 올해 = 2026, 이번 달 10월, 이번 분기 Q4). */
export const NOW = '2026-10-15T09:00:00+09:00'

/** 서버 요약을 고정 값으로 바꿔 끼운다(Fake의 계산 대신 화면이 받은 값을 그대로 확인한다). */
export function mockSummary(summary: DashboardSummary) {
  return vi.spyOn(gateway.dashboard, 'summary').mockResolvedValue(summary)
}

/** 마지막 요약 조회 조건. */
export function lastQuery(spy: ReturnType<typeof vi.spyOn>): Record<string, unknown> {
  return spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
}

/** 이름이 패턴에 맞는 링크 하나(타일). 여러 개면 오류. */
export function link(name: RegExp | string): HTMLElement {
  return screen.getByRole('link', { name })
}

/** 표 한 행의 링크. */
export function rowLink(rowName: RegExp | string): HTMLElement {
  return within(screen.getByRole('row', { name: rowName })).getByRole('link')
}

/** 화면에 그려진 차트(canvas) 목록. */
export function canvases(): HTMLElement[] {
  return screen.queryAllByRole('img').filter((el) => el.tagName === 'CANVAS')
}
