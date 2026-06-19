import { create } from 'zustand'

export type ToastVariant = 'default' | 'success' | 'error'

export interface Toast {
  id: number
  title: string
  description?: string
  variant: ToastVariant
}

interface ToastState {
  toasts: Toast[]
  add: (t: Omit<Toast, 'id'>) => void
  dismiss: (id: number) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  add: (t) => {
    counter += 1
    const id = counter
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }))
    }, 4500)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}))

/** Fire a toast from anywhere — including non-React code (api, queryClient). */
export function toast(t: Omit<Toast, 'id'>): void {
  useToastStore.getState().add(t)
}
