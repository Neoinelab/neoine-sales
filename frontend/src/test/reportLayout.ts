/**
 * Reports 작성/결과 탭 분리와 결과 배치(표·차트 타일) 화면 테스트 공용 도구(운영 코드에서 쓰지 않는다).
 *
 * 화면 계약(접근 가능한 이름과 구조, 테스트가 정한 것)
 * - 디자이너: role=tablist(이름 "리포트 디자이너") 안에 tab "작성"·"결과"(aria-selected). 위반이 있으면 이름 뒤에 " (고칠 곳 N)".
 *   각 탭의 role=tabpanel은 그 탭 이름으로 불리고, 선택되지 않은 패널은 DOM에 남되 `hidden` 속성이다.
 * - 결과 영역(디자이너 결과 탭·보기 화면 공용): role=radiogroup "보기" 안에 radio "표+차트"·"차트만"·"표만".
 * - 타일: role=region 이름 "표 타일"·"차트 타일"(보이는 타일만 DOM에 있다). 두 타일의 부모는 클래스 `report-tiles`이고
 *   한 줄이면 `is-side`, 두 줄이면 `is-stacked`가 붙는다. 보이는 순서는 DOM 순서다.
 *   끄는 손잡이는 타일 안의 `[draggable="true"]` 요소(타일 머리), 놓기 대상은 타일(region) 전체다.
 *   끄는 동안 대상 타일에 `is-drop-left|right|top|bottom` 클래스가 붙는다.
 *   타일이 둘 보일 때만 버튼 "표 타일 옮기기"·"차트 타일 옮기기"(Alt+화살표)가 있고, 옮긴 결과는 aria-live=polite 영역에 안내된다.
 * - 표 타일 머리: 총 행 수·조회 시간 줄과 '합계 행' 체크박스. 차트 타일 머리: '차트 설정' 버튼(aria-expanded, 디자이너만).
 */

import { createEvent, fireEvent, screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { expect } from 'vitest'

export type TileName = '표' | '차트'
export type Edge = 'left' | 'right' | 'top' | 'bottom'

export const STALE_NOTE = "설계가 바뀌었습니다. 작성 탭에서 '조회'를 눌러 다시 조회하세요"
export const NO_RESULT_NOTE = "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요."

// ---- 탭 ----

export const designTab = (): HTMLElement => screen.getByRole('tab', { name: /^작성/ })
export const resultTab = (): HTMLElement => screen.getByRole('tab', { name: /^결과/ })

export async function showTab(user: UserEvent, which: 'design' | 'result'): Promise<void> {
  await user.click(which === 'design' ? designTab() : resultTab())
}

/** 탭의 패널: 탭의 aria-controls가 가리키는 요소(숨겨진 패널은 접근 이름이 비어 이름으로 찾을 수 없다). */
export const panelOf = (which: 'design' | 'result'): HTMLElement => {
  const id = (which === 'design' ? designTab() : resultTab()).getAttribute('aria-controls')
  const panel = id === null ? null : document.getElementById(id)
  if (!panel) throw new Error(`${which} 탭의 패널(aria-controls)을 찾을 수 없습니다.`)
  expect(panel).toHaveAttribute('role', 'tabpanel')
  return panel
}

export function expectTab(which: 'design' | 'result'): void {
  const other = which === 'design' ? 'result' : 'design'
  expect(which === 'design' ? designTab() : resultTab()).toHaveAttribute('aria-selected', 'true')
  expect(other === 'design' ? designTab() : resultTab()).toHaveAttribute('aria-selected', 'false')
  expect(panelOf(which)).not.toHaveAttribute('hidden')
  expect(panelOf(other)).toHaveAttribute('hidden')
}

// ---- 보기 방식 ----

export const VIEW_LABELS = ['표+차트', '차트만', '표만'] as const
export type ViewLabel = (typeof VIEW_LABELS)[number]

export const viewGroup = (): HTMLElement => screen.getByRole('radiogroup', { name: '보기' })
export const viewRadio = (label: ViewLabel): HTMLElement => within(viewGroup()).getByRole('radio', { name: label })

export async function chooseView(user: UserEvent, label: ViewLabel): Promise<void> {
  await user.click(viewRadio(label))
}

// ---- 타일 ----

export const tile = (name: TileName): HTMLElement => screen.getByRole('region', { name: `${name} 타일` })
export const queryTile = (name: TileName): HTMLElement | null => screen.queryByRole('region', { name: `${name} 타일` })
export const moveButton = (name: TileName): HTMLElement => screen.getByRole('button', { name: `${name} 타일 옮기기` })
export const queryMoveButton = (name: TileName): HTMLElement | null => screen.queryByRole('button', { name: `${name} 타일 옮기기` })

/** 지금 보이는 타일의 순서(DOM 순서). */
export function tileOrder(): TileName[] {
  return screen
    .queryAllByRole('region', { name: /^(표|차트) 타일$/ })
    .map((region) => (region.getAttribute('aria-label') === '표 타일' ? '표' : '차트'))
}

/** 타일 둘을 감싼 배치 상자(클래스 `report-tiles`). 타일이 없으면 null. */
export function tilesBox(): HTMLElement | null {
  const first = screen.queryAllByRole('region', { name: /^(표|차트) 타일$/ })[0]
  return first ? first.closest<HTMLElement>('.report-tiles') : null
}

/** 한 줄이면 'side', 두 줄이면 'stacked'. */
export function arrangement(): 'side' | 'stacked' {
  const box = tilesBox()
  if (!box) throw new Error('타일 배치 상자가 없습니다.')
  if (box.classList.contains('is-side')) return 'side'
  if (box.classList.contains('is-stacked')) return 'stacked'
  throw new Error(`배치 클래스가 없습니다: ${box.className}`)
}

// ---- 끌어서 놓기 ----

/** 놓기 대상 타일의 가상 크기(jsdom에는 레이아웃이 없다). */
export const RECT = { left: 100, top: 50, width: 200, height: 100 } as const

/** 끌기 이벤트가 공유하는 최소 DataTransfer. */
export function dataTransfer() {
  const data: Record<string, string> = {}
  return {
    setData: (type: string, value: string) => {
      data[type] = value
    },
    getData: (type: string) => data[type] ?? '',
    effectAllowed: 'all',
    dropEffect: 'move',
    types: [] as string[],
  }
}

type Transfer = ReturnType<typeof dataTransfer>

const handleOf = (name: TileName): HTMLElement => {
  const handle = tile(name).querySelector<HTMLElement>('[draggable="true"]')
  if (!handle) throw new Error(`${name} 타일에 끄는 손잡이([draggable])가 없습니다.`)
  return handle
}

/** 타일 안쪽 위치(0~1 비율)를 가리키는 마우스 좌표. */
export const pointAt = (fx: number, fy: number) => ({ x: RECT.left + fx * RECT.width, y: RECT.top + fy * RECT.height })

/** 정해진 가장자리 쪽 안쪽 위치. */
export const EDGE_POINT: Record<Edge, { x: number; y: number }> = {
  left: pointAt(0.1, 0.5),
  right: pointAt(0.9, 0.5),
  top: pointAt(0.5, 0.1),
  bottom: pointAt(0.5, 0.9),
}

function fireDrag(type: 'dragOver' | 'drop', target: HTMLElement, transfer: Transfer, point: { x: number; y: number }): void {
  target.getBoundingClientRect = () => ({ ...RECT, right: RECT.left + RECT.width, bottom: RECT.top + RECT.height, x: RECT.left, y: RECT.top, toJSON: () => ({}) })
  const event = createEvent[type](target, { dataTransfer: transfer })
  Object.defineProperty(event, 'clientX', { value: point.x })
  Object.defineProperty(event, 'clientY', { value: point.y })
  fireEvent(target, event)
}

/** 끌기를 시작한다. 같은 끌기 안에서 쓸 DataTransfer를 돌려준다. */
export function startDrag(dragged: TileName): Transfer {
  const transfer = dataTransfer()
  fireEvent.dragStart(handleOf(dragged), { dataTransfer: transfer })
  return transfer
}

export const dragOverTile = (transfer: Transfer, target: TileName, point: { x: number; y: number }): void => fireDrag('dragOver', tile(target), transfer, point)
export const dropOnTile = (transfer: Transfer, target: TileName, point: { x: number; y: number }): void => fireDrag('drop', tile(target), transfer, point)
export const endDrag = (transfer: Transfer, dragged: TileName): void => {
  fireEvent.dragEnd(handleOf(dragged), { dataTransfer: transfer })
}

/** 끌어서 놓기를 한 번에 한다(시작 → 위로 이동 → 놓기 → 끝). */
export function dragTile(dragged: TileName, target: TileName, edge: Edge | { x: number; y: number }): void {
  const point = typeof edge === 'string' ? EDGE_POINT[edge] : edge
  const transfer = startDrag(dragged)
  dragOverTile(transfer, target, point)
  dropOnTile(transfer, target, point)
  endDrag(transfer, dragged)
}

/** 타일 머리의 "옮기기" 버튼에 포커스를 두고 Alt+화살표를 누른다. */
export async function moveByKey(user: UserEvent, name: TileName, key: 'ArrowRight' | 'ArrowLeft' | 'ArrowDown' | 'ArrowUp'): Promise<void> {
  moveButton(name).focus()
  await user.keyboard(`{Alt>}{${key}}{/Alt}`)
}
