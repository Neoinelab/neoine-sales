/** Action 상세 팝업의 칸별 인라인 수정: 화면 검증과 수정 요청 본문 만들기(순수 함수). 서버가 같은 규칙으로 다시 검증한다. */
import { ACTION_TYPE_NAME_MAX_LENGTH } from '../../../shared/model/constants'
import { toChoice } from '../../../shared/model/catalogChoice'
import { dateValueError } from '../../../shared/model/dateText'
import type { ActionUpdateInput } from '../../../shared/model/inputs'
import type { DealAction } from '../../../shared/model/types'

/** 지금 값 그대로 보내는 수정 본문(유형은 id, 수행일은 보내지 않는다). 바꾼 칸만 `patch`로 덮어쓴다. */
export function updateBody(action: DealAction, patch: Partial<ActionUpdateInput> = {}): ActionUpdateInput {
  return {
    type: { id: action.typeId },
    progress: action.progress ?? '',
    nextAction: action.nextAction ?? '',
    dueDate: action.dueDate,
    ...patch,
  }
}

const NEED_PROGRESS_OR_NEXT = '진행사항 또는 Next Action을 입력하세요.'

/** 진행사항: Next Action도 없으면 비울 수 없다. */
export function progressPatch(action: DealAction, text: string): Partial<ActionUpdateInput> {
  const progress = text.trim()
  if (progress === '' && (action.nextAction ?? '') === '') throw new Error(NEED_PROGRESS_OR_NEXT)
  return { progress }
}

/** 유형: 비어 있거나 50자를 넘으면 막고, 목록에 있으면 id·없으면 이름으로 보낸다. */
export function typePatch(text: string, types: readonly { id: number; name: string }[]): Partial<ActionUpdateInput> {
  const name = text.trim()
  if (name === '') throw new Error('유형을 입력하세요.')
  if ([...name].length > ACTION_TYPE_NAME_MAX_LENGTH) throw new Error(`유형은 ${ACTION_TYPE_NAME_MAX_LENGTH}자 이내로 입력하세요.`)
  const choice = toChoice(name, types)
  if (!choice) throw new Error('유형을 입력하세요.')
  return { type: choice }
}

/** Next Action·Due Date 묶음(편집 중에는 한 글자열 `next\ndue`로 다룬다. Next Action에 줄바꿈이 있어도 Due는 마지막 줄바꿈 뒤다). */
export const encodePair = (next: string, due: string) => `${next}\n${due}`
export function decodePair(value: string): { next: string; due: string } {
  const at = value.lastIndexOf('\n')
  return at < 0 ? { next: value, due: '' } : { next: value.slice(0, at), due: value.slice(at + 1) }
}

export function nextActionPatch(action: DealAction, value: string): Partial<ActionUpdateInput> {
  const { next, due } = decodePair(value)
  const nextAction = next.trim()
  if (nextAction === '' && (action.progress ?? '') === '') throw new Error(NEED_PROGRESS_OR_NEXT)
  if (nextAction === '') {
    if (due !== '') throw new Error('Next Action 없이 Due Date를 입력할 수 없습니다.')
    return { nextAction: '', dueDate: null }
  }
  if (due === '') throw new Error('Due Date를 입력하세요.')
  const invalid = dateValueError(due)
  if (invalid !== null) throw new Error(invalid)
  return { nextAction, dueDate: due }
}

export function dueDatePatch(action: DealAction, due: string): Partial<ActionUpdateInput> {
  if (!action.nextAction) throw new Error('Next Action 없이 Due Date를 입력할 수 없습니다.')
  if (due === '') throw new Error('Due Date를 입력하세요.')
  const invalid = dateValueError(due)
  if (invalid !== null) throw new Error(invalid)
  return { dueDate: due }
}

/** 수행일: 비움·틀린 날짜·오늘 이후·Deal 등록일 이전은 막는다(이전 Next Action 수행일과는 비교하지 않는다). */
export function actedOnPatch(text: string, today: string, registeredOn: string): Partial<ActionUpdateInput> {
  if (text === '') throw new Error('수행일을 입력하세요.')
  const invalid = dateValueError(text)
  if (invalid !== null) throw new Error(invalid)
  if (text > today) throw new Error('수행일은 오늘 이후로 지정할 수 없습니다.')
  if (text < registeredOn) throw new Error(`수행일은 Deal 등록일(${registeredOn}) 이전으로 지정할 수 없습니다.`)
  return { actedOn: text }
}
