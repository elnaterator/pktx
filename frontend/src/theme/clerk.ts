/** Clerk appearance objects, built from the shared palette in ./index.ts. */
import { clerkPalette, fontMono, palette } from './index'

export const clerkAppearance = {
  variables: {
    colorBackground: palette['bg-primary'],
    colorForeground: palette['text-primary'],
    colorPrimary: palette['accent-green'],
    colorNeutral: palette['text-secondary'],
    colorDanger: palette['status-error'],
    colorText: palette['text-primary'],
    colorTextSecondary: palette['text-secondary'],
    colorInputBackground: palette['bg-input'],
    colorInputText: palette['text-primary'],
    fontFamily: fontMono,
    borderRadius: '0px',
    colorShadow: 'transparent',
  },
  elements: {
    // Modal backdrop
    modalBackdrop: {
      backgroundColor: palette['bg-modal-overlay'],
      backdropFilter: 'blur(4px)',
    },
    // Cards / modal containers
    card: {
      backgroundColor: palette['bg-primary'],
      boxShadow: 'none',
      border: `1px solid ${clerkPalette.border}`,
    },
    cardBox: {
      boxShadow: 'none',
    },
    // Navigation sidebar (account modal)
    navbar: {
      backgroundColor: palette['bg-input'],
      borderRight: `1px solid ${clerkPalette.border}`,
    },
    navbarButton: {
      color: palette['text-secondary'],
    },
    navbarButton__active: {
      color: palette['accent-green'],
      backgroundColor: palette['accent-green-bg'],
    },
    // Page content
    pageScrollBox: {
      backgroundColor: palette['bg-primary'],
    },
    profileSection: {
      backgroundColor: palette['bg-primary'],
      borderTop: `1px solid ${clerkPalette.border}`,
    },
    profileSectionContent: {
      backgroundColor: palette['bg-primary'],
    },
    // Headers
    headerTitle: {
      color: palette['text-primary'],
    },
    headerSubtitle: {
      color: palette['text-secondary'],
    },
    // Form fields
    formFieldLabel: {
      color: palette['text-secondary'],
    },
    formFieldInput: {
      backgroundColor: palette['bg-input'],
      border: `1px solid ${clerkPalette.border}`,
      color: palette['text-primary'],
      boxShadow: 'none',
    },
    formFieldInputShowPasswordButton: {
      color: palette['text-muted'],
    },
    // Buttons
    formButtonPrimary: {
      backgroundColor: palette['accent-green'],
      color: palette['bg-primary'],
      boxShadow: 'none',
    },
    formButtonReset: {
      color: palette['text-secondary'],
    },
    // Social sign-in buttons
    socialButtonsBlockButton: {
      backgroundColor: palette['bg-input'],
      border: `1px solid ${clerkPalette.border}`,
      color: palette['text-primary'],
      boxShadow: 'none',
    },
    socialButtonsBlockButtonText: {
      color: palette['text-primary'],
    },
    // Divider
    dividerLine: {
      backgroundColor: clerkPalette.border,
    },
    dividerText: {
      color: palette['text-muted'],
    },
    // Identity / avatar
    identityPreviewText: {
      color: palette['text-primary'],
    },
    identityPreviewEditButton: {
      color: palette['accent-green'],
    },
    avatarBox: {
      boxShadow: 'none',
    },
    // Badges / tags
    badge: {
      backgroundColor: palette['accent-green-bg'],
      color: palette['accent-green'],
      border: `1px solid ${palette['accent-green-dim']}`,
    },
    // Footer
    footer: {
      backgroundColor: palette['bg-primary'],
      borderTop: `1px solid ${clerkPalette.border}`,
    },
    footerActionLink: {
      color: palette['accent-green'],
    },
    // Alert
    alertText: {
      color: palette['text-secondary'],
    },
  },
}

export const userMenuAppearance = {
  variables: {
    colorBackground: palette['bg-primary'],
    colorForeground: palette['text-primary'],
    colorPrimary: palette['accent-green'],
    colorNeutral: clerkPalette.neutral,
    colorDanger: palette['status-error'],
    fontFamily: fontMono,
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
      backgroundColor: palette['bg-primary'],
      boxShadow: 'none',
      border: `1px solid ${clerkPalette.border}`,
    },
    userButtonPopoverMain: {
      backgroundColor: palette['bg-primary'],
    },
    userButtonPopoverActions: {
      backgroundColor: palette['bg-primary'],
    },
    userButtonPopoverActionButton: {
      color: clerkPalette.neutral,
      backgroundColor: 'transparent',
    },
    userButtonPopoverActionButton__manageAccount: {
      color: clerkPalette.neutral,
    },
    userButtonPopoverActionButton__signOut: {
      color: clerkPalette.neutral,
    },
    userButtonPopoverActionButtonText: {
      color: clerkPalette.neutral,
    },
    userButtonPopoverActionButtonIcon: {
      color: clerkPalette.faint,
    },
    userButtonPopoverFooter: {
      backgroundColor: palette['bg-primary'],
      borderTop: `1px solid ${clerkPalette.border}`,
    },
    userPreview: {
      backgroundColor: palette['bg-primary'],
    },
    userPreviewMainIdentifier: {
      color: palette['text-primary'],
    },
    userPreviewSecondaryIdentifier: {
      color: clerkPalette.faint,
    },
    avatarBox: {
      boxShadow: 'none',
    },
  },
} as const
