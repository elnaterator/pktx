import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import {
  useAllTags,
  useApplicationList,
  useApplicationMutations,
} from '../../hooks/queries'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'
import { Button } from '../../components/Button'
import { ExternalLink } from '../../components/ExternalLink'
import { ListPage } from '../../components/ListPage'
import { LinkCount, ListRow, ListRowMain, ListRowMeta } from '../../components/ListRow'
import { SearchBar } from '../../components/SearchBar'
import { TagList } from '../../components/TagList'
import { useToast } from '../../components/toast'
import { APPLICATION_STATUSES } from '../../schemas/application'
import { formatDate } from '../../utils/formatDate'
import { ApplicationPanel } from './ApplicationPanel'
import type { ApplicationPanelInput } from './ApplicationPanel'
import { StatusBadge } from './StatusBadge'
import { StatusFilter } from './StatusFilter'
import styles from './ApplicationListView.module.css'

export default function ApplicationListView() {
  const navigate = useNavigate()
  const { search, setSearch, debounced, isFiltered } = useDebouncedSearch()
  // Status filter lives in the URL (?status=Applied&status=Interview) so it
  // can be linked to (e.g. "N active" on the home page) and survives back/forward.
  const [searchParams, setSearchParams] = useSearchParams()
  const statusFilter = searchParams
    .getAll('status')
    .filter((s) => (APPLICATION_STATUSES as readonly string[]).includes(s))
  const setStatusFilter = (statuses: string[]) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('status')
        statuses.forEach((s) => next.append('status', s))
        return next
      },
      { replace: true },
    )
  const [showNewForm, setShowNewForm] = useState(false)
  const { success, error } = useToast()

  const listQuery = useApplicationList({
    status: statusFilter.length > 0 ? statusFilter : undefined,
    q: debounced.text || undefined,
    tags: search.tags,
  })
  const tagsQuery = useAllTags()
  const { create } = useApplicationMutations()

  const allTags = tagsQuery.data ?? []

  const onCreate = async (data: ApplicationPanelInput) => {
    try {
      const created = await create.mutateAsync({
        company: data.company,
        position: data.position,
        status: data.status,
        url: data.url ?? undefined,
        description: data.description ?? undefined,
        notes: data.notes ?? undefined,
        tags: data.tags ?? [],
      })
      setShowNewForm(false)
      success('Application created')
      navigate(`/applications/${created.id}`)
    } catch {
      error('Failed to create application')
    }
  }

  return (
    <ListPage
      title="Job Applications"
      noun="applications"
      testId="application-list-view"
      action={
        <Button variant="link" onClick={() => setShowNewForm((v) => !v)}>
          {showNewForm ? 'Cancel' : 'New Application'}
        </Button>
      }
      createForm={
        showNewForm && (
          <ApplicationPanel
            mode="create"
            allTags={allTags}
            onSave={onCreate}
            onCancel={() => setShowNewForm(false)}
          />
        )
      }
      filters={
        <>
          <SearchBar
            value={search}
            onChange={setSearch}
            availableTags={allTags}
            placeholder="Search company or position..."
          />
          <StatusFilter
            value={statusFilter}
            onChange={setStatusFilter}
            options={[...APPLICATION_STATUSES]}
            placeholder="All statuses"
          />
        </>
      }
      query={listQuery}
      items={listQuery.data ?? []}
      getKey={(app) => app.id}
      isFiltered={isFiltered || statusFilter.length > 0}
      emptyMessage='No applications yet. Click "New Application" to add one.'
      renderItem={(app) => (
        <ListRow
          to={`/applications/${app.id}`}
          after={
            app.url && (
              <ExternalLink href={app.url} className={styles.postingLink}>
                Job posting
              </ExternalLink>
            )
          }
        >
          <ListRowMain>
            <span className={styles.position}>{app.position}</span>
            <span className={styles.at}>@</span>
            <span className={styles.company}>{app.company}</span>
            <StatusBadge status={app.status} />
          </ListRowMain>
          <TagList tags={app.tags ?? []} />
          <ListRowMeta>
            <span>Updated {formatDate(app.updated_at)}</span>
            <LinkCount count={app.link_count} />
          </ListRowMeta>
        </ListRow>
      )}
    />
  )
}
