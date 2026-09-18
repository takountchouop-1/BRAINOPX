import InfoIconImport from '@mui/icons-material/Info'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import WarningIconImport from '@mui/icons-material/Warning'
import ErrorIconImport from '@mui/icons-material/Error'

const InfoIcon = InfoIconImport?.default || InfoIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const WarningIcon = WarningIconImport?.default || WarningIconImport
const ErrorIcon = ErrorIconImport?.default || ErrorIconImport

// Shared look-and-feel for a notification, keyed by its `type` field
// ("info", "success", "warning", "error"). Used by both the topbar
// dropdown and the dedicated notifications page.
export const notificationTypeConfig = {
  info: { icon: <InfoIcon fontSize="small" />, color: '#3b66ff' },
  success: { icon: <CheckCircleIcon fontSize="small" />, color: '#10b981' },
  warning: { icon: <WarningIcon fontSize="small" />, color: '#f59e0b' },
  error: { icon: <ErrorIcon fontSize="small" />, color: '#ef4444' },
}
