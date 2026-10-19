import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ApiClientError } from '../../types'
import { mapGroupedLinks } from '../../services/api'
import { useAllTags, useNoteDetail, useNoteMutations } from '../../hooks/queries'
import { LinksPanel } from '../../components/LinksPanel'
import { TagsPanel } from '../../components/TagsPanel'
import DetailLayout from '../../components/DetailLayout'
import Breadcrumb from '../../components/Breadcrumb'
import NotFound from '../../components/NotFound'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { NotePanel } from './NotePanel'
import type { NoteCreateInput } from '../../schemas/note'
import styles from './NoteDetailView.module.css'

export default function NoteDetailView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const numericId = id && /^\d+$/.test(id) ? Number(id) : null

  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { success, error } = useToast()

  useEffect(() => {
    if (numericId === null) {
      navigate('/notes', { replace: true })
    }
  }, [numericId, navigate])

  const detailQuery = useNoteDetail(numericId ?? undefined)
  const tagsQuery = useAllTags()
  const { update, remove } = useNoteMutations()

  const note = detailQuery.data ?? null
  const allTags = tagsQuery.data ?? []
  const errStatus = (detailQuery.error as ApiClientError | undefined)?.status
  const notFound = errStatus === 404
  const forbidden = errStatus === 403
  const reloadNote = () => detailQuery.refetch()

  if (numericId === null) return null
  if (notFound) return <NotFound entityName="Note" backTo="/notes" backLabel="Back to Notes" />
  if (forbidden) return <NotFound entityName="Note" backTo="/notes" backLabel="Back to Notes" heading="This note isn't yours" message="This note belongs to another account and cannot be accessed." />
  if (!note) {
    return <div>Loading...</div>
  }

  const handleSave = async (data: NoteCreateInput) => {
    await update.mutateAsync({
      id: numericId,
      data: {
        title: data.title,
        content: data.content,
        tags: note.tags ?? [],
      },
    })
    setEditing(false)
    success('Saved')
  }

  const handleDelete = async () => {
    try {
      await remove.mutateAsync(numericId)
      success('Note deleted')
      navigate('/notes')
    } catch {
      setConfirmDelete(false)
      error('Failed to delete note')
    }
  }

  return (
    <div className={styles.container}>
      <Breadcrumb
        items={[
          { label: 'Notes', to: '/notes' },
          { label: note.title },
        ]}
      />

      <DetailLayout
        sidebar={
          <>
            <TagsPanel
              tags={note.tags ?? []}
              allTags={allTags}
              onSave={(tags) => update.mutateAsync({ id: numericId, data: { tags } })}
            />
            <LinksPanel
              resourceType="note"
              resourceId={numericId}
              links={mapGroupedLinks(note.links as Record<string, unknown[]>)}
              onChange={reloadNote}
            />
          </>
        }
      >
        {editing ? (
          <NotePanel
            key="edit"
            mode="edit"
            note={note}
            allTags={allTags}
            onSave={handleSave}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <NotePanel
            key="view"
            mode="view"
            note={note}
            onEdit={() => setEditing(true)}
            onDelete={() => setConfirmDelete(true)}
          />
        )}
      </DetailLayout>

      {confirmDelete && (
        <ConfirmDialog
          message="Delete this note? This cannot be undone."
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
