import { Box } from '@mui/material'
import NotificationsPanelContent from './NotificationsPanelContent.jsx'

// Topbar bell dropdown: anchors the shared panel body just below the
// bell button, on the right edge.
const NotificationsPanel = ({ open, onClose }) => {
  if (!open) return null

  return (
    <Box sx={{ position: 'absolute', top: '100%', right: 0, mt: 1, zIndex: 1300 }}>
      <NotificationsPanelContent onClose={onClose} />
    </Box>
  )
}

export default NotificationsPanel

