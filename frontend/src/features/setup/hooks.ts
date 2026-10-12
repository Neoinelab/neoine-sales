import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../shared/api/client'
import { ApiError, call } from '../../shared/api/problem'
import type { DirectoryRequest } from '../../shared/directory/directoryForm'

/** 1단계: AD 서버 등록. 이미 관리자가 있으면(409) config가 바뀌었으니 다시 읽는다. */
export function useSetupDirectory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: DirectoryRequest) => call(api.PUT('/api/v1/auth/setup/directory', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ['auth-config'] }),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void client.invalidateQueries({ queryKey: ['auth-config'] })
      }
    },
  })
}
