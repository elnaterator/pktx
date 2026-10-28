import { useState } from 'react'
import {
  useAccomplishmentList,
  useAccomplishmentMutations,
  useAllTags,
} from '../../hooks/queries'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'
import { ListPage, NewButton } from '../../components/ListPage'
import { LinkCount, ListRow, ListRowMain, ListRowMeta, ListRowTitle } from '../../components/ListRow'
import { SearchBar } from '../../components/SearchBar'
import { TagList } from '../../components/TagList'
import { useToast } from '../../components/toast'
import { AccomplishmentPanel } from './AccomplishmentPanel'
import type { AccomplishmentCreateInput } from '../../schemas/accomplishment'

export default function AccomplishmentListView() {
  const { search, setSearch, debounced, isFiltered } = useDebouncedSearch()
  const [showForm, setShowForm] = useState(false)

  const listQuery = useAccomplishmentList({ tags: search.tags, q: debounced.text || undefined })
  const tagsQuery = useAllTags()
  const { create } = useAccomplishmentMutations()
  const { success, error } = useToast()

  const allTags = tagsQuery.data ?? []

  const handleCreate = async (data: AccomplishmentCreateInput) => {
    try {
      await create.mutateAsync({
        title: data.title,
        situation: data.situation ?? undefined,
        task: data.task ?? undefined,
        action: data.action ?? undefined,
        result: data.result ?? undefined,
        accomplishment_date: data.accomplishment_date ?? null,
        tags: data.tags ?? [],
      })
      setShowForm(false)
      success('Accomplishment created')
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to create accomplishment')
      throw err
    }
  }

  return (
    <ListPage
      title="Accomplishments"
      noun="accomplishments"
      action={
        <NewButton noun="Accomplishment" open={showForm} onClick={() => setShowForm((v) => !v)} />
      }
      createForm={
        showForm && (
          <AccomplishmentPanel
            mode="create"
            allTags={allTags}
            onSave={handleCreate}
            onCancel={() => setShowForm(false)}
          />
        )
      }
      filters={
        <SearchBar
          value={search}
          onChange={setSearch}
          availableTags={allTags}
          placeholder="Search accomplishments..."
        />
      }
      query={listQuery}
      items={listQuery.data ?? []}
      getKey={(acc) => acc.id}
      isFiltered={isFiltered}
      emptyMessage='No accomplishments yet. Click "New Accomplishment" to add one.'
      renderItem={(acc) => (
        <ListRow to={`/accomplishments/${acc.id}`}>
          <ListRowMain>
            <ListRowTitle>{acc.title}</ListRowTitle>
          </ListRowMain>
          <TagList tags={acc.tags} />
          <ListRowMeta>
            {acc.accomplishment_date && <span>{acc.accomplishment_date}</span>}
            <LinkCount count={acc.link_count} />
          </ListRowMeta>
        </ListRow>
      )}
    />
  )
}
