import { useState } from 'react'
import { useAuth, UserButton } from '@clerk/clerk-react'
import { Download } from 'lucide-react'
import { fetchDataExport, saveBlob } from '../../services/api'
import { useToast } from '../toast'

const appearance = {
  variables: {
    colorBackground: '#1a1a1a',
    colorForeground: '#e0e0e0',
    colorPrimary: '#52b788',
    colorNeutral: '#888888',
    colorDanger: '#ff4444',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', 'Cascadia Code', ui-monospace, monospace",
    borderRadius: '0px',
    colorShadow: 'transparent',
  },
  elements: {
    userButtonTrigger: {
      boxShadow: 'none',
      outline: 'none',
    },
    userButtonTrigger__open: {
      boxShadow: 'none',
    },
    userButtonPopoverCard: {
      backgroundColor: '#1a1a1a',
      boxShadow: 'none',
      border: '1px solid #2a2a2a',
    },
    userButtonPopoverMain: {
      backgroundColor: '#1a1a1a',
    },
    userButtonPopoverActions: {
      backgroundColor: '#1a1a1a',
    },
    userButtonPopoverActionButton: {
      color: '#888888',
      backgroundColor: 'transparent',
    },
    userButtonPopoverActionButton__manageAccount: {
      color: '#888888',
    },
    userButtonPopoverActionButton__signOut: {
      color: '#888888',
    },
    userButtonPopoverActionButtonText: {
      color: '#888888',
    },
    userButtonPopoverActionButtonIcon: {
      color: '#555555',
    },
    userButtonPopoverFooter: {
      backgroundColor: '#1a1a1a',
      borderTop: '1px solid #2a2a2a',
    },
    userPreview: {
      backgroundColor: '#1a1a1a',
    },
    userPreviewMainIdentifier: {
      color: '#e0e0e0',
    },
    userPreviewSecondaryIdentifier: {
      color: '#555555',
    },
    avatarBox: {
      boxShadow: 'none',
    },
  },
} as const

export default function UserMenu() {
  const { isSignedIn } = useAuth()
  const toast = useToast()
  const [exporting, setExporting] = useState(false)

  if (!isSignedIn) {
    return null
  }

  const handleExport = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const { blob, filename } = await fetchDataExport()
      saveBlob(blob, filename)
      toast.success('Export downloaded')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <UserButton afterSignOutUrl="/" appearance={appearance}>
      <UserButton.MenuItems>
        <UserButton.Action
          label={exporting ? 'Exporting…' : 'Export my data'}
          labelIcon={<Download size={14} />}
          onClick={handleExport}
        />
      </UserButton.MenuItems>
    </UserButton>
  )
}
