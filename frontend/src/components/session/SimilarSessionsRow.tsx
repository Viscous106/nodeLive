import { VideoCard } from '@/components/dashboard/VideoCard'
import { Skeleton } from '@/components/ui/skeleton'
import { useSimilarSessions } from '@/hooks/useSession'

export function SimilarSessionsRow({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useSimilarSessions(sessionId)

  if (!isLoading && (!data || data.length === 0)) return null

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-text-primary">
        Sessions similar to this
      </h2>
      {isLoading ? (
        <div className="flex gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[210px] w-[250px] shrink-0" />
          ))}
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 no-scrollbar">
          {data?.map((s) => (
            <VideoCard key={s.id} session={s} />
          ))}
        </div>
      )}
    </section>
  )
}
