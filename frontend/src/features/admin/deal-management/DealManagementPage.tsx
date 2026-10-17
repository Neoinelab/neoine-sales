import { useSearchParams } from 'react-router'
import { Tabs } from '../../../shared/ui/Tabs'
import '../admin.css'
import { AlertSettingsForm } from './AlertSettingsForm'
import { CodeManager } from './CodeManager'
import { LabelManager } from './LabelManager'

const TABS = [
  { id: 'status', label: 'Status 코드' },
  { id: 'forecast', label: 'Forecast 코드' },
  { id: 'label', label: 'BANT Label' },
  { id: 'alert', label: '경고 기준' },
] as const

type TabId = (typeof TABS)[number]['id']

function isTab(value: string | null): value is TabId {
  return TABS.some((t) => t.id === value)
}

/** Deal 관리(`/admin/deal`): Status 코드 · Forecast 코드 · BANT Label · 경고 기준 네 탭. 탭은 `?tab=`으로 유지한다. */
export function DealManagementPage() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const active: TabId = isTab(raw) ? raw : 'status'
  return (
    <section className="admin-page" aria-labelledby="deal-management-title">
      <h2 id="deal-management-title">Deal 관리</h2>
      <Tabs
        label="Deal 관리 항목"
        tabs={TABS}
        active={active}
        onChange={(id) => setParams(id === 'status' ? {} : { tab: id }, { replace: true })}
      >
        {active === 'alert' ? <AlertSettingsForm /> : active === 'label' ? <LabelManager /> : <CodeManager key={active} kind={active} />}
      </Tabs>
    </section>
  )
}
