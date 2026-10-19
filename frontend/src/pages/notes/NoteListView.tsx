import { useState } from 'react'
import { useAllTags, useNoteList, useNoteMutations } from '../../hooks/queries'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'
import { Button } from '../../components/Button'
import { ListPage } from '../../components/ListPage'
import { LinkCount, ListRow, ListRowMain, ListRowMeta, ListRowTitle } from '../../components/ListRow'
import { SearchBar } from '../../components/SearchBar'
import { TagList } from '../../components/TagList'
import { useToast } from '../../components/toast'
import { formatDate } from '../../utils/formatDate'
import { NotePanel } from './NotePanel'
import type { NoteCreateInput } from '../../schemas/note'

export default function NoteListView() {
  const { search, setSearch, debounced, isFiltered } = useDebouncedSearch()
  const [showForm, setShowForm] = useState(false)

  const listQuery = useNoteList({ tags: search.tags, q: debounced.text || undefined })
  const tagsQuery = useAllTags()
  const { create } = useNoteMutations()
  const { success, error } = useToast()

  const allTags = tagsQuery.data ?? []

  const handleCreate = async (data: NoteCreateInput) => {
    try {
      await create.mutateAsync({
        title: data.title,
        content: data.content ?? undefined,
        tags: data.tags ?? [],
      })
      setShowForm(false)
      success('Note created')
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to create note')
      throw err
    }
  }

  return (
    <ListPage
      title="Notes"
      noun="notes"
      action={
        <Button variant="link" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'New Note'}
        </Button>
      }
      createForm={
        showForm && (
          <NotePanel
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
          placeholder="Search notes..."
        />
      }
      query={listQuery}
      items={listQuery.data ?? []}
      getKey={(note) => note.id}
      isFiltered={isFiltered}
      emptyMessage='No notes yet. Click "New Note" to add one.'
      renderItem={(note) => (
        <ListRow to={`/notes/${note.id}`}>
          <ListRowMain>
            <ListRowTitle>{note.title}</ListRowTitle>
          </ListRowMain>
          <TagList tags={note.tags} />
          <ListRowMeta>
            <span>{formatDate(note.updated_at)}</span>
            <LinkCount count={note.link_count} />
          </ListRowMeta>
        </ListRow>
      )}
    />
  )
}
