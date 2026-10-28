import { NavLink } from 'react-router'
import { PlugZap } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { cx } from '../utils/cx'
import styles from './ConnectButton.module.css'

/** Header entry point to /connect. The label hides on phones; the name stays. */
export default function ConnectButton() {
  return (
    <NavLink
      to="/connect"
      className={({ isActive }) => cx(styles.button, isActive && styles.active)}
      aria-label="Connect AI"
      title="Connect your AI assistant"
    >
      <PlugZap size={ICON_SIZE.lg} aria-hidden="true" />
      <span className={styles.label}>Connect AI</span>
    </NavLink>
  )
}
