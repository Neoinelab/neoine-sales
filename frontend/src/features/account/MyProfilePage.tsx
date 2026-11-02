import { useMyProfile } from '../../data/me'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import './account.css'
import { PasswordForm } from './PasswordForm'
import { ProfileForm } from './ProfileForm'

/** 내 정보(`/me`): 로그인한 모든 역할이 자기 프로필을 고친다. 수정 가능한 항목과 비밀번호 변경은 로그인 방식에 따라 서버가 정한다. */
export function MyProfilePage() {
  const profile = useMyProfile()
  if (profile.isPending) return <p className="hint">불러오는 중…</p>
  if (profile.isError) {
    return (
      <section className="account-page">
        <h2>내 정보</h2>
        <ErrorBanner error={profile.error} />
      </section>
    )
  }
  return (
    <section className="account-page" aria-labelledby="my-profile-title">
      <h2 id="my-profile-title">내 정보</h2>
      <ProfileForm profile={profile.data} />
      {profile.data.editable.password && <PasswordForm />}
    </section>
  )
}
