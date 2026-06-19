import { Spinner } from '@/components/ui/spinner'

export function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page">
      <Spinner className="h-8 w-8 text-primary" />
    </div>
  )
}
