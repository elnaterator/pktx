import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Briefcase,
  Trophy,
  FileText,
  StickyNote,
  User,
  Plus,
  X,
} from 'lucide-react'
import { ICON_SIZE } from '../theme'
import type { GroupedLinks, ResourceRef, ResourceType } from '../types'
import { useLinkMutations } from '../hooks/queries'
import { LinkPickerModal } from './LinkPickerModal'
import { Button } from './Button'
import { IconButton } from './IconButton'
import styles from './LinksPanel.module.css'

const TYPE_ICON: Record<ResourceType, React.ReactNode> = {
  application: <Briefcase size={ICON_SIZE.sm} />,
  accomplishment: <Trophy size={ICON_SIZE.sm} />,
  resume: <FileText size={ICON_SIZE.sm} />,
  note: <StickyNote size={ICON_SIZE.sm} />,
  contact: <User size={ICON_SIZE.sm} />,
}

const TYPE_LABEL: Record<ResourceType, string> = {
  application: 'Applications',
  accomplishment: 'Accomplishments',
  resume: 'Resumes',
  note: 'Notes',
  contact: 'Contacts',
}

const TYPE_ROUTE: Record<ResourceType, string> = {
  application: 'applications',
  accomplishment: 'accomplishments',
  resume: 'resumes',
  note: 'notes',
  contact: 'contacts',
}

interface LinksPanelProps {
  resourceType: ResourceType
  resourceId: number
  links: GroupedLinks
  onChange: () => void
}

function totalLinkCount(links: GroupedLinks): number {
  return Object.values(links).reduce((acc, refs) => acc + (refs?.length ?? 0), 0)
}

function buildSelfRef(resourceType: ResourceType, resourceId: number): ResourceRef {
  return { type: resourceType, id: resourceId, name: '' }
}

function buildExcludeRefs(links: GroupedLinks, selfRef: ResourceRef): ResourceRef[] {
  const refs: ResourceRef[] = [selfRef]
  for (const items of Object.values(links)) {
    if (items) refs.push(...items)
  }
  return refs
}

export function LinksPanel({
  resourceType,
  resourceId,
  links = {},
  onChange,
}: LinksPanelProps) {
  const navigate = useNavigate()
  const [showPicker, setShowPicker] = useState(false)
  const { link, unlink } = useLinkMutations()
  const unlinking = unlink.isPending
    ? `${unlink.variables?.bType}/${unlink.variables?.bId}`
    : null

  const count = totalLinkCount(links)
  const selfRef = buildSelfRef(resourceType, resourceId)
  const excludeRefs = buildExcludeRefs(links, selfRef)

  const handlePick = async (ref: ResourceRef) => {
    setShowPicker(false)
    try {
      await link.mutateAsync({ aType: resourceType, aId: resourceId, bType: ref.type, bId: ref.id })
      onChange()
    } catch {
      // ignore
    }
  }

  const handleUnlink = async (ref: ResourceRef) => {
    try {
      await unlink.mutateAsync({ aType: resourceType, aId: resourceId, bType: ref.type, bId: ref.id })
      onChange()
    } catch {
      // ignore
    }
  }

  const navigateTo = (ref: ResourceRef) => {
    navigate(`/${TYPE_ROUTE[ref.type]}/${ref.id}`)
  }

  const nonEmptyTypes = (Object.keys(links) as ResourceType[]).filter(
    (t) => links[t] && links[t]!.length > 0
  )

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.title}>Links ({count})</h4>
        <Button variant="link" size="sm" onClick={() => setShowPicker(true)}>
          <Plus size={ICON_SIZE.sm} aria-hidden="true" />
          Link
        </Button>
      </div>

      {nonEmptyTypes.length === 0 ? (
        <p className={styles.empty}>No links yet.</p>
      ) : (
        nonEmptyTypes.map((type) => (
          <div key={type} className={styles.typeGroup}>
            <div className={styles.typeLabel}>
              {TYPE_ICON[type]}
              {TYPE_LABEL[type]}
            </div>
            <ul className={styles.linkList}>
              {links[type]!.map((ref) => {
                const key = `${ref.type}/${ref.id}`
                return (
                  <li key={key} className={styles.linkRow}>
                    <button
                      className={styles.linkName}
                      onClick={() => navigateTo(ref)}
                    >
                      {ref.name}
                    </button>
                    <IconButton
                      icon={X}
                      iconSize={ICON_SIZE.sm}
                      label={`Unlink ${ref.name}`}
                      tone="danger"
                      className={styles.unlinkButton}
                      onClick={() => handleUnlink(ref)}
                      disabled={unlinking === key}
                    />
                  </li>
                )
              })}
            </ul>
          </div>
        ))
      )}

      {showPicker && (
        <LinkPickerModal
          excludeRefs={excludeRefs}
          onPick={handlePick}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  )
}
