import { FileText } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { usePastSessions } from '@/hooks/useDashboard'

import { VideoCard } from './VideoCard'

export function ContinueWatchingSection() {
  const { data, isLoading } = usePastSessions()

  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold text-text-primary">
        Continue Watching
      </h2>
      {isLoading ? (
        <div className="flex gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[210px] w-[250px] shrink-0" />
          ))}
        </div>
      ) : data && data.length > 0 ? (
        <div className="flex gap-4 overflow-x-auto pb-2 no-scrollbar">
          {data.map((s) => (
            <VideoCard key={s.id} session={s} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="pt-4">
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <FileText className="h-8 w-8 text-text-muted" />
              <p className="text-sm text-text-muted">
                Nothing to catch up on yet — past recordings will appear here.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  )
}
