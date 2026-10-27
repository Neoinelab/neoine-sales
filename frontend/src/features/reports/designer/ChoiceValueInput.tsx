import { useActionTypes } from '../../../data/actionTypes'
import { useLabels } from '../../../data/labels'
import { useCodeSet } from '../../../data/codes'
import { useUserOptions } from '../../../data/users'
import { useVendors } from '../../../data/vendors'
import { userLabel } from '../../../shared/model/period'
import type { ReportField } from '../../../shared/model/reportTypes'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { MultiCheckSelect } from '../../../shared/ui/MultiCheckSelect'

interface Option {
  value: string
  label: string
}

interface ChoiceProps {
  field: ReportField
  /** 조건 번호(1부터). 접근 가능한 이름 `조건 N 값`에 쓴다. */
  n: number
  values: string[]
  onChange: (values: string[]) => void
  describedBy?: string
}

/** 선택 요약: 없으면 '선택', 1~2개는 이름, 3개 이상은 '이름1, 이름2 외 N'. */
function summarize(values: readonly string[], options: readonly Option[]): string {
  if (values.length === 0) return '선택'
  const names = values.map((v) => options.find((o) => o.value === v)?.label ?? v)
  return names.length <= 2 ? names.join(', ') : `${names.slice(0, 2).join(', ')} 외 ${names.length - 2}`
}

function ChoiceSelect({ options, n, values, onChange, describedBy }: Omit<ChoiceProps, 'field'> & { options: readonly Option[] }) {
  return (
    <MultiCheckSelect
      label={`조건 ${n} 값`}
      name={`report-condition-${n}`}
      options={options}
      selected={values}
      summary={summarize(values, options)}
      onToggle={(value, on) => onChange(on ? [...values.filter((v) => v !== value), value] : values.filter((v) => v !== value))}
      onClear={() => onChange([])}
      clearLabel="선택 해제"
      describedBy={describedBy}
    />
  )
}

/** 데이터 출처 하나의 조회 결과를 선택지로 보인다. 조회가 실패하면 그 오류를 함께 보인다. */
function FromQuery<T>({ query, toOptions, ...rest }: Omit<ChoiceProps, 'field'> & { query: { data?: T; error: unknown }; toOptions: (data: T) => Option[] }) {
  return (
    <>
      <ChoiceSelect options={query.data ? toOptions(query.data) : []} {...rest} />
      <ErrorBanner error={query.error} />
    </>
  )
}

function UserChoices(props: Omit<ChoiceProps, 'field'>) {
  const query = useUserOptions({ includeResigned: true })
  return <FromQuery query={query} toOptions={(users) => users.map((u) => ({ value: String(u.id), label: userLabel(u) }))} {...props} />
}

function VendorChoices(props: Omit<ChoiceProps, 'field'>) {
  const query = useVendors()
  return <FromQuery query={query} toOptions={(vendors) => vendors.map((v) => ({ value: String(v.id), label: v.name }))} {...props} />
}

function CodeChoices({ kind, ...props }: Omit<ChoiceProps, 'field'> & { kind: 'statuses' | 'forecasts' }) {
  const query = useCodeSet()
  return (
    <FromQuery
      query={query}
      toOptions={(set) => [...set[kind]].sort((a, b) => a.order - b.order).map((c) => ({ value: c.key, label: c.name }))}
      {...props}
    />
  )
}

function LabelChoices({ category, ...props }: Omit<ChoiceProps, 'field'> & { category: string | null }) {
  const query = useLabels()
  return (
    <FromQuery
      query={query}
      toOptions={(labels) => labels.filter((l) => l.category === category).map((l) => ({ value: String(l.id), label: l.name }))}
      {...props}
    />
  )
}

function ActionTypeChoices(props: Omit<ChoiceProps, 'field'>) {
  const query = useActionTypes()
  return <FromQuery query={query} toOptions={(types) => types.map((t) => ({ value: String(t.id), label: t.name }))} {...props} />
}

/** 목록 값(다중 선택). 선택지는 필드의 정적 `options`, 없으면 `optionsSource`의 현재 데이터에서 온다. */
export function ChoiceValueInput({ field, ...props }: ChoiceProps) {
  if (field.options) return <ChoiceSelect options={field.options} {...props} />
  switch (field.optionsSource) {
    case 'users':
      return <UserChoices {...props} />
    case 'vendors':
      return <VendorChoices {...props} />
    case 'status_codes':
      return <CodeChoices kind="statuses" {...props} />
    case 'forecast_codes':
      return <CodeChoices kind="forecasts" {...props} />
    case 'bant_labels':
      return <LabelChoices category={field.optionsCategory} {...props} />
    case 'action_types':
      return <ActionTypeChoices {...props} />
    default:
      return <ChoiceSelect options={[]} {...props} />
  }
}
