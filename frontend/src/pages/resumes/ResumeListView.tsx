import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Link2 } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { useAllTags, useResumeList, useResumeMutations } from '../../hooks/queries'
import { SearchBar } from '../../components/SearchBar'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { InlineCreateForm } from '../../components/InlineCreateForm'
import { useToast } from '../../components/toast'
import type { SearchValue } from '../../types'
import { Button } from '../../components/Button'
import { TagList } from '../../components/TagList'
import styles from './ResumeListView.module.css'

export default function ResumeListView() {
  const [search, setSearch] = useState<SearchValue>({ tags: [], text: '' })
  const [debouncedQ, setDebouncedQ] = useState('')
  const [creating, setCreating] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: resumes = [], isPending, isError } = useResumeList({
    tags: search.tags,
    q: debouncedQ || undefined,
  })
  const tagsQuery = useAllTags()
  const { create } = useResumeMutations()
  const { success, error } = useToast()

  const allTags = tagsQuery.data ?? []

  useEffect(() => {
    if (isError) {
      error('Failed to load resume versions')
    }
  }, [isError, error])

  const handleSearchChange = (v: SearchValue) => {
    setSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(v.text), 300)
  }

  const handleCreateConfirm = async (label: string) => {
    try {
      await create.mutateAsync(label)
      success('Resume version created')
      setCreating(false)
    } catch {
      error('Failed to create resume version')
    }
  }

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className={styles.container} data-testid="resume-list-view">
      <div className={styles.header}>
        <h2 className={styles.heading}>Resume Versions</h2>
        <Button variant="link" onClick={() => setCreating(true)}>
          New Version
        </Button>
      </div>

      {creating && (
        <InlineCreateForm
          onConfirm={handleCreateConfirm}
          onCancel={() => setCreating(false)}
          placeholder="e.g. Senior Engineer, Remote-focused..."
          confirmLabel="Create"
        />
      )}

      <div className={styles.filters}>
        <SearchBar
          value={search}
          onChange={handleSearchChange}
          availableTags={allTags}
          placeholder="Search resume versions..."
        />
      </div>

      {isPending ? (
        <LoadingSpinner />
      ) : resumes.length === 0 ? (
        <p className={styles.empty}>No resume versions found.</p>
      ) : (
        <ul className={styles.list}>
          {[...resumes].sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0)).map((resume) => (
            <li key={resume.id} className={styles.item}>
              <Link to={`/resumes/${resume.id}`} className={styles.itemLink}>
                <div className={styles.itemMain}>
                  <span className={styles.label}>{resume.label}</span>
                  {resume.is_default && (
                    <span className={styles.defaultBadge}>Default</span>
                  )}
                </div>
                <TagList tags={resume.tags ?? []} />
                <div className={styles.itemMeta}>
                  <span className={styles.metaItem}>
                    {resume.app_count} application{resume.app_count !== 1 ? 's' : ''}
                  </span>
                  {!!resume.link_count && (
                    <span className={`${styles.metaItem} ${styles.linkCount}`}><Link2 size={ICON_SIZE.sm} />{resume.link_count}</span>
                  )}
                  <span className={styles.metaItem}>
                    Created {formatDate(resume.created_at)}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

    </div>
  )
}
