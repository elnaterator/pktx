import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { LoadingSpinner } from './LoadingSpinner'
import NotFound from './NotFound'

export interface ResourceRoute {
  /** List page, e.g. "/notes". */
  listPath: string
  /** Capitalised singular, e.g. "Note". */
  singular: string
  /** Capitalised plural, e.g. "Notes". */
  plural: string
}

interface DetailQueryState {
  isPending: boolean
  error: unknown
  refetch: () => unknown
}

interface DetailFallbackProps {
  query: DetailQueryState
  route: ResourceRoute
}

/**
 * What a detail page shows before its record is available: a spinner, a
 * not-found / not-yours page, or a retryable error. Render it while
 * `query.data` is undefined.
 */
export function DetailFallback({ query, route }: DetailFallbackProps) {
  const { listPath, singular, plural } = route
  const status = (query.error as { status?: number } | null)?.status
  const backLabel = `Back to ${plural}`

  if (status === 404) {
    return <NotFound entityName={singular} backTo={listPath} backLabel={backLabel} />
  }
  if (status === 403) {
    const noun = singular.toLowerCase()
    return (
      <NotFound
        entityName={singular}
        backTo={listPath}
        backLabel={backLabel}
        heading={`This ${noun} isn't yours`}
        message={`This ${noun} belongs to another account and cannot be accessed.`}
      />
    )
  }
  if (query.error) {
    return (
      <EmptyState
        action={
          <Button variant="link" size="sm" onClick={() => void query.refetch()}>
            Retry
          </Button>
        }
      >
        Couldn&apos;t load this {singular.toLowerCase()}.
      </EmptyState>
    )
  }
  return <LoadingSpinner />
}
