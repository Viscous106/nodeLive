import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { User } from '@/types'

const ME_KEY = ['auth', 'me'] as const

export interface LoginInput {
  email: string
  password: string
}

export interface SignupInput extends LoginInput {
  displayName: string
  inviteToken?: string
}

/**
 * Current-user state, sourced from `GET /api/auth/me`. A 401 (not logged in)
 * surfaces as `user: null`, not an error to handle at the call site.
 */
export function useAuth() {
  const { data, isLoading } = useQuery({
    queryKey: ME_KEY,
    queryFn: () => api.get<User>('/api/auth/me'),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
  return {
    user: data ?? null,
    isLoading,
    isAuthenticated: Boolean(data),
  }
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: LoginInput) => api.post<User>('/api/auth/login', input),
    onSuccess: (user) => qc.setQueryData(ME_KEY, user),
  })
}

export function useSignup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: SignupInput) =>
      api.post<User>('/api/auth/signup', input),
    onSuccess: (user) => qc.setQueryData(ME_KEY, user),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<null>('/api/auth/logout'),
    onSuccess: () => {
      qc.setQueryData(ME_KEY, null)
      qc.clear()
      toast({ variant: 'success', title: 'Signed out' })
    },
  })
}

export interface ProfileUpdateInput {
  displayName?: string
  avatarUrl?: string
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: ProfileUpdateInput) =>
      api.patch<User>('/api/auth/me', input),
    onSuccess: (user) => {
      qc.setQueryData(ME_KEY, user)
      toast({ variant: 'success', title: 'Profile updated' })
    },
    onError: () => toast({ variant: 'error', title: 'Could not update profile.' }),
  })
}
