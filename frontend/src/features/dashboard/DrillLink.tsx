import { createContext, useContext, type ComponentProps } from 'react'
import { Link } from 'react-router'

/** 이전 조건의 응답(placeholder)을 보이는 동안 false. Drill-down 이동을 막는다. */
export const DrillEnabledContext = createContext(true)

export const useDrillEnabled = (): boolean => useContext(DrillEnabledContext)

/** Deal 목록으로 가는 Drill-down 링크. 이전 응답을 보이는 동안에는 링크 역할 없이 내용만 보인다. */
export function DrillLink({ to, className, children }: ComponentProps<typeof Link>) {
  const enabled = useDrillEnabled()
  if (!enabled) return <span className={className}>{children}</span>
  return (
    <Link to={to} className={className}>
      {children}
    </Link>
  )
}
