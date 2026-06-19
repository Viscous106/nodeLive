import { QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/api'
import { toast } from '@/stores/toastStore'

// Hoisted so the cache's onError can clear auth on the same client instance.
let client: QueryClient

const queryCache = new QueryCache({
  onError: (error, query) => {
    // A 401 on any non-auth query means the session expired mid-use. Clearing
    // the cached user makes ProtectedRoute redirect to /login on next render.
    const isAuthQuery = query.queryKey[0] === 'auth'
    if (error instanceof ApiError && error.status === 401 && !isAuthQuery) {
      client.setQueryData(['auth', 'me'], null)
      toast({
        variant: 'error',
        title: 'Session expired',
        description: 'Please sign in again.',
      })
    }
  },
})

client = new QueryClient({
  queryCache,
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Retry transient/network errors, never API errors (4xx/5xx).
      retry: (count, error) => !(error instanceof ApiError) && count < 2,
    },
  },
})

export const queryClient = client
