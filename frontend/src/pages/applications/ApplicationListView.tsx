import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Link2 } from 'lucide-react'
import {
  useAllTags,
  useApplicationList,
  useApplicationMutations,
} from '../../hooks/queries'
import { SearchBar } from '../../components/SearchBar'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { useToast } from '../../components/toast'
import { APPLICATION_STATUSES } from '../../schemas/application'
import { ApplicationPanel } from './ApplicationPanel'
import { StatusFilter } from './StatusFilter'
import type { ApplicationPanelInput } from './ApplicationPanel'
import type { SearchValue } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import styles from './ApplicationListView.module.css'

const STATUS_COLORS: Record<string, string> = {
  Interested: styles.statusInterested,
  Applied: styles.statusApplied,
  'Phone Screen': styles.statusPhoneScreen,
  Interview: styles.statusInterview,
  Offer: styles.statusOffer,
  Rejected: styles.statusRejected,
  Withdrawn: styles.statusWithdrawn,
  Accepted: styles.statusAccepted,
}

export default function ApplicationListView() {
  const navigate = useNavigate()
  const [search, setSearch] = useState<SearchValue>({ tags: [], text: '' })
  const [debouncedQ, setDebouncedQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [showNewForm, setShowNewForm] = useState(false)
  const { success, error } = useToast()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const listQuery = useApplicationList({
    status: statusFilter.length > 0 ? statusFilter : undefined,
    q: debouncedQ || undefined,
    tags: search.tags,
  })
  const tagsQuery = useAllTags()
  const { create } = useApplicationMutations()

  const applications = listQuery.data ?? []
  const allTags = tagsQuery.data ?? []
  const loading = listQuery.isPending

  useEffect(() => {
    if (listQuery.isError) {
      error('Failed to load applications')
    }
  }, [listQuery.isError, error])

  const handleSearchChange = (v: SearchValue) => {
    setSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(v.text), 300)
  }

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

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })

  return (
    <div className={styles.container} data-testid="application-list-view">
      <div className={styles.header}>
        <h2 className={styles.heading}>Job Applications</h2>
        <button
          className={styles.newButton}
          onClick={() => setShowNewForm((v) => !v)}
        >
          {showNewForm ? 'Cancel' : 'New Application'}
        </button>
      </div>

      {showNewForm && (
        <ApplicationPanel
          mode="create"
          allTags={allTags}
          onSave={onCreate}
          onCancel={() => setShowNewForm(false)}
        />
      )}

      <div className={styles.filters}>
        <SearchBar
          value={search}
          onChange={handleSearchChange}
          availableTags={allTags}
          placeholder="Search company or position..."
        />
        <StatusFilter
          value={statusFilter}
          onChange={setStatusFilter}
          options={[...APPLICATION_STATUSES]}
          placeholder="All statuses"
        />
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : applications.length === 0 ? (
        <p className={styles.empty}>No applications found.</p>
      ) : (
        <ul className={styles.list}>
          {applications.map((app) => (
            <li key={app.id} className={styles.item}>
              <Link to={`/applications/${app.id}`} className={styles.itemLink}>
                <div className={styles.itemMain}>
                  <span className={styles.position}>{app.position}</span>
                  <span className={styles.company}>{app.company}</span>
                  <span className={`${styles.statusBadge} ${STATUS_COLORS[app.status] || ''}`}>
                    {app.status}
                  </span>
                </div>
                {app.tags && app.tags.length > 0 && (
                  <div className={styles.tagList}>
                    {app.tags.map((tag) => (
                      <span key={tag} className={styles.tagBadge}>{tag}</span>
                    ))}
                  </div>
                )}
                <div className={styles.itemMeta}>
                  <span>Updated {formatDate(app.updated_at)}</span>
                  {!!app.link_count && (
                    <span className={styles.linkCount}><Link2 size={11} />{app.link_count}</span>
                  )}
                </div>
              </Link>
              {app.url && (
                <ExternalLink href={app.url} className={styles.metaLink}>
                  Job posting
                </ExternalLink>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
