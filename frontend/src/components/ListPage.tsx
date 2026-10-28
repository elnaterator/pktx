import { Fragment, type Key, type ReactNode } from 'react'
import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { LoadingSpinner } from './LoadingSpinner'
import rowStyles from './listRow.module.css'
import styles from './ListPage.module.css'

interface ListQueryState {
  isPending: boolean
  isError: boolean
  refetch: () => unknown
}

interface ListPageProps<T> {
  title: string
  /** Header control, usually the "New …" button. */
  action?: ReactNode
  /** Create form shown under the header while open. */
  createForm?: ReactNode
  /** Search and filter controls. */
  filters: ReactNode
  /** Extra content between the filters and the list (e.g. related results). */
  aside?: ReactNode
  query: ListQueryState
  items: T[]
  getKey: (item: T) => Key
  /** Render one row — normally a <ListRow>. */
  renderItem: (item: T) => ReactNode
  /** Plural noun for status messages ("notes"). */
  noun: string
  /** Shown when there are no items at all. */
  emptyMessage: ReactNode
  /** True while a search or filter is active (changes the empty message). */
  isFiltered: boolean
  testId?: string
}

/**
 * Shell of every resource list page: header, optional create form, filters,
 * then loading / error / empty / list states.
 */
export function ListPage<T>({
  title,
  action,
  createForm,
  filters,
  aside,
  query,
  items,
  getKey,
  renderItem,
  noun,
  emptyMessage,
  isFiltered,
  testId,
}: ListPageProps<T>) {
  let body: ReactNode
  if (query.isPending) {
    body = <LoadingSpinner />
  } else if (query.isError) {
    body = (
      <EmptyState
        action={
          <Button variant="link" size="sm" onClick={() => void query.refetch()}>
            Retry
          </Button>
        }
      >
        Couldn&apos;t load {noun}.
      </EmptyState>
    )
  } else if (items.length === 0) {
    body = <EmptyState>{isFiltered ? `No ${noun} match your search.` : emptyMessage}</EmptyState>
  } else {
    body = (
      <ul className={rowStyles.list}>
        {items.map((item) => (
          <Fragment key={getKey(item)}>{renderItem(item)}</Fragment>
        ))}
      </ul>
    )
  }

  return (
    <div className={styles.container} data-testid={testId}>
      <div className={styles.header}>
        <h2 className={styles.heading}>{title}</h2>
        {action}
      </div>
      {createForm && <div className={styles.createForm}>{createForm}</div>}
      <div className={styles.filters}>{filters}</div>
      {aside}
      {body}
    </div>
  )
}
