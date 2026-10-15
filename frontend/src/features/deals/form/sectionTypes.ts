import type { DealDetail } from '../../../shared/model/types'
import type { DealFormState, FormErrors } from './formState'

/** 폼 상태의 한 필드를 바꾼다. */
export type SetField = <K extends keyof DealFormState>(key: K, value: DealFormState[K]) => void

/** 섹션 컴포넌트가 공통으로 받는 값. */
export interface SectionProps {
  state: DealFormState
  set: SetField
  errors: FormErrors
  /** 수정 중인 Deal(신규면 undefined). */
  original?: DealDetail
}
