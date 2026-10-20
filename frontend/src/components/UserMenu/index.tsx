import { useState } from 'react'
import { useAuth, UserButton } from '@clerk/clerk-react'
import { Download } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { fetchDataExport, saveBlob } from '../../services/api'
import { useToast } from '../toast'
import { userMenuAppearance } from '../../theme/clerk'

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
    <UserButton afterSignOutUrl="/" appearance={userMenuAppearance}>
      <UserButton.MenuItems>
        <UserButton.Action
          label={exporting ? 'Exporting…' : 'Export my data'}
          labelIcon={<Download size={ICON_SIZE.md} />}
          onClick={handleExport}
        />
      </UserButton.MenuItems>
    </UserButton>
  )
}
