import { useState } from 'react'
import { useAllTags, useResumeList, useResumeMutations } from '../../hooks/queries'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'
import { Button } from '../../components/Button'
import { InlineCreateForm } from '../../components/InlineCreateForm'
import { ListPage } from '../../components/ListPage'
import { LinkCount, ListRow, ListRowMain, ListRowMeta, ListRowTitle } from '../../components/ListRow'
import { SearchBar } from '../../components/SearchBar'
import { TagList } from '../../components/TagList'
import { useToast } from '../../components/toast'
import { formatDate } from '../../utils/formatDate'
import styles from './ResumeListView.module.css'

export default function ResumeListView() {
  const { search, setSearch, debounced, isFiltered } = useDebouncedSearch()
  const [creating, setCreating] = useState(false)

  const listQuery = useResumeList({ tags: search.tags, q: debounced.text || undefined })
  const tagsQuery = useAllTags()
  const { create } = useResumeMutations()
  const { success, error } = useToast()

  const allTags = tagsQuery.data ?? []
  // The default version always leads the list.
  const resumes = [...(listQuery.data ?? [])].sort(
    (a, b) => Number(b.is_default) - Number(a.is_default),
  )

  const handleCreateConfirm = async (label: string) => {
    try {
      await create.mutateAsync(label)
      success('Resume version created')
      setCreating(false)
    } catch {
      error('Failed to create resume version')
    }
  }

  return (
    <ListPage
      title="Resume Versions"
      noun="resume versions"
      testId="resume-list-view"
      action={
        <Button variant="link" onClick={() => setCreating(true)}>
          New Version
        </Button>
      }
      createForm={
        creating && (
          <InlineCreateForm
            onConfirm={handleCreateConfirm}
            onCancel={() => setCreating(false)}
            placeholder="e.g. Senior Engineer, Remote-focused..."
            confirmLabel="Create"
          />
        )
      }
      filters={
        <SearchBar
          value={search}
          onChange={setSearch}
          availableTags={allTags}
          placeholder="Search resume versions..."
        />
      }
      query={listQuery}
      items={resumes}
      getKey={(resume) => resume.id}
      isFiltered={isFiltered}
      emptyMessage='No resume versions yet. Click "New Version" to add one.'
      renderItem={(resume) => (
        <ListRow to={`/resumes/${resume.id}`}>
          <ListRowMain>
            <ListRowTitle>{resume.label}</ListRowTitle>
            {resume.is_default && <span className={styles.defaultBadge}>Default</span>}
          </ListRowMain>
          <TagList tags={resume.tags ?? []} />
          <ListRowMeta>
            <span>
              {resume.app_count} application{resume.app_count !== 1 ? 's' : ''}
            </span>
            <LinkCount count={resume.link_count} />
            <span>Created {formatDate(resume.created_at)}</span>
          </ListRowMeta>
        </ListRow>
      )}
    />
  )
}
