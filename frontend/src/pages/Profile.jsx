import React, { useState, useRef } from 'react'
import {
  Box,
  Typography,
  Paper,
  Avatar,
  Button,
  IconButton,
  Alert,
  CircularProgress,
  Stack,
  Divider,
  TextField,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext.jsx'
import PhotoCameraIconImport from '@mui/icons-material/PhotoCamera'
import DeleteIconImport from '@mui/icons-material/Delete'
import SaveIconImport from '@mui/icons-material/Save'

const PhotoCameraIcon = PhotoCameraIconImport?.default || PhotoCameraIconImport
const DeleteIcon = DeleteIconImport?.default || DeleteIconImport
const SaveIcon = SaveIconImport?.default || SaveIconImport

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const Profile = () => {
  const { t } = useTranslation('pages')
  const { user, token, updateUser } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [profilePicture, setProfilePicture] = useState(user?.profile_picture || null)
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const fileInputRef = useRef(null)

  const profilePictureUrl = profilePicture
    ? `${API_BASE_URL}/uploads/profiles/${profilePicture}`
    : null

  const handleUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      setError(t('profile.errorInvalidImageType'))
      return
    }

    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
      setError(t('profile.errorFileTooLarge'))
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE_URL}/api/users/upload-profile-picture`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || t('profile.errorUploadFailed'))
      }

      const data = await response.json()
      setProfilePicture(data.profile_picture)
      // Sync to AuthContext so Topbar updates immediately
      updateUser({ profile_picture: data.profile_picture })
      setSuccess(t('profile.successUploaded'))

    } catch (err) {
      setError(err.message || t('profile.errorUploadFailedGeneric'))
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!profilePicture) return

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/users/profile-picture`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || t('profile.errorDeleteFailed'))
      }

      setProfilePicture(null)
      // Sync to AuthContext so Topbar updates immediately
      updateUser({ profile_picture: null })
      setSuccess(t('profile.successDeleted'))

    } catch (err) {
      setError(err.message || t('profile.errorDeleteFailedGeneric'))
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProfile = async () => {
    setError('')
    setSuccess('')

    // Basic validation
    if (!fullName.trim() || fullName.trim().length < 2) {
      setError(t('profile.errorFullNameTooShort'))
      return
    }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError(t('profile.errorInvalidEmail'))
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || t('profile.errorUpdateFailed'))
      }

      const updatedUser = await response.json()
      // Sync to AuthContext so Topbar updates immediately with new name
      updateUser({
        full_name: updatedUser.full_name,
        email: updatedUser.email,
      })
      setSuccess(t('profile.successUpdated'))

    } catch (err) {
      setError(err.message || t('profile.errorUpdateFailedGeneric'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ maxWidth: 800, mx: 'auto' }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 4 }}>
          {t('profile.pageTitle')}
        </Typography>

        <Paper sx={{ p: 4, borderRadius: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            {t('profile.profilePictureTitle')}
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            {/* Avatar */}
            <Box sx={{ position: 'relative' }}>
              <Avatar
                sx={{
                  width: 120,
                  height: 120,
                  bgcolor: profilePicture ? 'transparent' : '#3b66ff',
                  fontSize: 48,
                  fontWeight: 700,
                  border: '4px solid #e5e7eb',
                }}
                src={profilePictureUrl}
              >
                {!profilePicture && user?.full_name?.charAt(0)?.toUpperCase() || t('profile.avatarFallback')}
              </Avatar>
              
              {/* Upload button overlay */}
              <IconButton
                sx={{
                  position: 'absolute',
                  bottom: 0,
                  right: 0,
                  bgcolor: 'primary.main',
                  color: 'white',
                  '&:hover': { bgcolor: 'primary.dark' },
                  width: 36,
                  height: 36,
                }}
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
              >
                <PhotoCameraIcon fontSize="small" />
              </IconButton>
              
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={handleUpload}
              />
            </Box>

            {/* Actions */}
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                {t('profile.uploadHint')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('profile.supportedFormats')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<PhotoCameraIcon />}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                >
                  {t('profile.upload')}
                </Button>
                {profilePicture && (
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={handleDelete}
                    disabled={loading}
                  >
                    {t('profile.delete')}
                  </Button>
                )}
              </Box>
              {loading && !success && <CircularProgress size={24} />}
            </Stack>
          </Box>

          <Divider sx={{ my: 4 }} />

          {/* Editable User Info */}
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            {t('profile.profileInformationTitle')}
          </Typography>
          <Stack spacing={3}>
            <TextField
              label={t('profile.fullNameLabel')}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              fullWidth
              variant="outlined"
              disabled={loading}
            />
            <TextField
              label={t('profile.emailLabel')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              fullWidth
              variant="outlined"
              type="email"
              disabled={loading}
            />
            <Box>
              <Typography variant="caption" color="text.secondary">{t('profile.roleLabel')}</Typography>
              <Typography variant="body1" fontWeight={600}>{user?.role || t('profile.roleDefault')}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
                onClick={handleSaveProfile}
                disabled={loading}
                sx={{
                  px: 4,
                  py: 1.2,
                  borderRadius: 2,
                  textTransform: 'none',
                  fontWeight: 600,
                }}
              >
                {loading ? t('profile.saving') : t('profile.saveChanges')}
              </Button>
            </Box>
          </Stack>
        </Paper>
      </Box>
    </Box>
  )
}

export default Profile
