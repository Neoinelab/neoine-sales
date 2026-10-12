import { useMutation, useQuery } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'

export function useDirectorySettings() {
  return useQuery({
    queryKey: ['directory-settings'],
    queryFn: () => call(api.GET('/api/v1/settings/directory')),
    // 편집 중인 폼을 다시 불러온 값으로 덮어쓰지 않는다.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

// 비밀번호가 든 variables를 화면이 사라진 뒤 캐시(기본 5분)에 남기지 않는다.
export function useTestDirectory() {
  return useMutation({
    gcTime: 0,
    mutationFn: (body: Schemas['DirectorySettingsTestRequest']) =>
      call(api.POST('/api/v1/settings/directory/test', { body })),
  })
}

export function useSaveDirectory() {
  return useMutation({
    gcTime: 0,
    mutationFn: (body: Schemas['DirectorySettingsUpdateRequest']) =>
      call(api.PUT('/api/v1/settings/directory', { body })),
  })
}
