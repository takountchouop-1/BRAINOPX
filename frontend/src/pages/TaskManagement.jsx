import React, { useState, useEffect, useCallback } from 'react'
import {
  Box,
  Typography,
  Button,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Snackbar,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import AddIconImport from '@mui/icons-material/Add'
import UploadFileIconImport from '@mui/icons-material/UploadFile'
import DescriptionIconImport from '@mui/icons-material/Description'
import DeleteIconImport from '@mui/icons-material/Delete'
import EditIconImport from '@mui/icons-material/Edit'
import { listTasks, createTask, updateTask, deleteTask } from '../services/taskService.js'
import PaginationBar from '../components/PaginationBar.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const AddIcon = AddIconImport?.default || AddIconImport
const UploadFileIcon = UploadFileIconImport?.default || UploadFileIconImport
const DescriptionIcon = DescriptionIconImport?.default || DescriptionIconImport
const DeleteIcon = DeleteIconImport?.default || DeleteIconImport
const EditIcon = EditIconImport?.default || EditIconImport

const TASK_TYPES = [
  { value: 'report_analyses', label: 'Report Analyses', description: 'Excel template (.xlsx)' },
  { value: 'skill_engine', label: 'Skill Engine', description: 'Rules file (.txt, .pdf, .doc, .docx)' },
]

const TaskManagement = ({ searchTerm = '', setSearchTerm = () => {} }) => {
  const { user } = useAuth()
  // Same dashboard for everyone; only creating a task is restricted.
  // The backend enforces this regardless — this only decides whether
  // the button is shown as usable, so a member is never invited to
  // try an action that will just 403.
  const isAdmin = user?.role === 'admin'

  const [tasks, setTasks] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // Dialog states
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState('create') // 'create' or 'edit'
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('report_analyses')
  const [file, setFile] = useState(null)
  const [submitError, setSubmitError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [taskToDelete, setTaskToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Snackbar
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' })

  const filteredTasks = tasks.filter((task) => {
    const searchLower = searchTerm.toLowerCase()
    return (
      !searchTerm ||
      task.name.toLowerCase().includes(searchLower) ||
      (task.description && task.description.toLowerCase().includes(searchLower)) ||
      (task.category && task.category.toLowerCase().includes(searchLower))
    )
  })

  // ─── PAGING ──────────────────────────────────────────────────────
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const pageCount = Math.max(1, Math.ceil(filteredTasks.length / pageSize))
  const pagedTasks = filteredTasks.slice((page - 1) * pageSize, page * pageSize)

  // A narrower search (or a delete) can leave the current page past
  // the new end; land on the new last page instead of an empty table.
  useEffect(() => {
    setPage((prev) => Math.min(prev, pageCount))
  }, [pageCount])

  // A search that matches something different deserves to start from
  // the top, not wherever paging happened to be left.
  useEffect(() => {
    setPage(1)
  }, [searchTerm])

  const changePageSize = (size) => {
    setPageSize(size)
    setPage(1)
  }

  const fetchTasks = useCallback(async () => {
    setIsLoading(true)
    setLoadError('')
    try {
      const data = await listTasks()
      setTasks(data)
    } catch (err) {
      setLoadError(err?.message || 'Unable to load tasks.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  const resetForm = () => {
    setName('')
    setDescription('')
    setCategory('report_analyses')
    setFile(null)
    setSubmitError('')
    setEditingTaskId(null)
  }

  const handleOpenCreateDialog = () => {
    resetForm()
    setDialogMode('create')
    setDialogOpen(true)
  }

  const handleOpenEditDialog = (task) => {
    setName(task.name)
    setDescription(task.description || '')
    setCategory(task.category || 'report_analyses')
    setFile(null)
    setEditingTaskId(task.id)
    setDialogMode('edit')
    setSubmitError('')
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    if (isSubmitting) return
    setDialogOpen(false)
    resetForm()
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitError('')

    if (!name.trim()) {
      setSubmitError('Task name is required.')
      return
    }

    const fileExt = file ? file.name.toLowerCase().split('.').pop() : ''
    const isReportAnalyses = category === 'report_analyses'

    // For create: file is required. For edit: file is optional
    if (dialogMode === 'create' && !file) {
      setSubmitError(isReportAnalyses ? 'Please select an Excel template file.' : 'Please select a rules file.')
      return
    }

    // Validate file extension based on task type
    if (file) {
      const allowedExts = isReportAnalyses ? ['xlsx'] : ['txt', 'pdf', 'doc', 'docx']
      if (!allowedExts.includes(fileExt)) {
        setSubmitError(
          isReportAnalyses
            ? 'Only .xlsx files are supported for Report Analyses.'
            : 'Only .txt, .pdf, .doc, .docx files are supported for Skill Engine.'
        )
        return
      }
    }

    setIsSubmitting(true)
    try {
      const taskData = { name, description, category, file }
      if (dialogMode === 'create') {
        await createTask(taskData)
        setSnackbar({ open: true, message: 'Task created successfully!', severity: 'success' })
      } else {
        await updateTask(editingTaskId, taskData)
        setSnackbar({ open: true, message: 'Task updated successfully!', severity: 'success' })
      }
      setDialogOpen(false)
      resetForm()
      fetchTasks()
    } catch (err) {
      setSubmitError(err?.message || 'Unable to save task.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteClick = (task) => {
    setTaskToDelete(task)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!taskToDelete) return
    setIsDeleting(true)
    try {
      await deleteTask(taskToDelete.id)
      setSnackbar({
        open: true,
        message: ` Task "${taskToDelete.name}" deleted successfully!`,
        severity: 'success',
      })
      setDeleteDialogOpen(false)
      setTaskToDelete(null)
      await fetchTasks()
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || ' Unable to delete task.',
        severity: 'error',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setTaskToDelete(null)
  }

  const handleSnackbarClose = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  const getTaskTypeLabel = (value) => {
    const type = TASK_TYPES.find((t) => t.value === value)
    return type ? type.label : 'Report Analyses'
  }

  const getFileAccept = (type) => {
    return type === 'skill_engine' ? '.txt,.pdf,.doc,.docx' : '.xlsx'
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ width: '100%' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 4 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: 'text.primary' }}>
              Task Management
            </Typography>
            <Typography variant="body1" sx={{ color: 'text.secondary' }}>
              Define BRAINOPX configuration tasks by uploading their expected Excel templates or rules files.
            </Typography>
          </Box>
          <Tooltip title={isAdmin ? '' : 'Only administrators can create tasks'}>
            <span>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleOpenCreateDialog}
                disabled={!isAdmin}
                sx={{
                  borderRadius: 3,
                  textTransform: 'none',
                  px: 3,
                  background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
                }}
              >
                New Task
              </Button>
            </span>
          </Tooltip>
        </Box>

        {loadError && <Alert severity="error" sx={{ mb: 3 }}>{loadError}</Alert>}

        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : filteredTasks.length === 0 ? (
          <Paper
            sx={{
              p: 6,
              textAlign: 'center',
              background: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff'),
              border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
              borderRadius: 3,
            }}
          >
            <DescriptionIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" sx={{ color: 'text.primary', mb: 1 }}>
              {searchTerm ? 'No tasks match your search' : 'No tasks defined yet'}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {searchTerm
                ? `Try adjusting your search term "${searchTerm}"`
                : isAdmin
                ? 'Click "New Task" to define your first configuration task.'
                : 'An administrator has not defined any tasks yet.'}
            </Typography>
          </Paper>
        ) : (
          <Box>
            <Typography variant="body2" sx={{ color: 'text.secondary', px: 1, mb: 1 }}>
              {filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''} found
              {searchTerm && ` for "${searchTerm}"`}
            </Typography>

            {/* The pagination bar shares this Paper's border and
                rounded corners, sitting flush under the table rather
                than as a separate floating strip. */}
            <Paper
              sx={{
                borderRadius: 3,
                overflow: 'hidden',
                border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                boxShadow: 'none',
              }}
            >
              <TableContainer
                sx={{
                '& .MuiTableHead-root .MuiTableCell-root': {
                  fontWeight: 700,
                  color: 'text.secondary',
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  borderBottom: (theme) => `2px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                  bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#f8fafc',
                },
                '& .MuiTableBody-root .MuiTableRow-root:hover': {
                  bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#f8fafc',
                },
                '& .MuiTableBody-root .MuiTableCell-root': {
                  borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#f0f0f0'}`,
                  py: 1.5,
                },
              }}
            >
              <Table sx={{ minWidth: 800 }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 160 }}>Name</TableCell>
                    <TableCell sx={{ width: 140 }}>Type</TableCell>
                    <TableCell sx={{ width: 240 }}>Description</TableCell>
                    <TableCell sx={{ width: 200 }}>Template / Rules</TableCell>
                    <TableCell sx={{ width: 110 }}>Created</TableCell>
                    <TableCell sx={{ width: 100, textAlign: 'center' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pagedTasks.map((task) => (
                    <TableRow key={task.id} hover>
                      {/* Name */}
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                          {task.name}
                        </Typography>
                      </TableCell>

                      {/* Type */}
                      <TableCell>
                        <Chip
                          size="small"
                          label={getTaskTypeLabel(task.category)}
                          color={task.category === 'skill_engine' ? 'info' : 'primary'}
                          variant="filled"
                          sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                        />
                      </TableCell>

                      {/* Description */}
                      <TableCell>
                        <Typography
                          variant="body2"
                          sx={{
                            color: 'text.secondary',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            maxWidth: 240,
                          }}
                        >
                          {task.description || (
                            <Box component="span" sx={{ fontStyle: 'italic', color: 'text.disabled' }}>
                              No description
                            </Box>
                          )}
                        </Typography>
                      </TableCell>

                      {/* Template / Rules */}
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <DescriptionIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                          <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                            {task.template_filename}
                          </Typography>
                        </Box>
                      </TableCell>

                      {/* Created At */}
                      <TableCell>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {task.created_at
                            ? new Date(task.created_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })
                            : '—'}
                        </Typography>
                      </TableCell>

                      {/* Actions */}
                      <TableCell>
                        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
                          <Tooltip title="Edit task">
                            <IconButton
                              size="small"
                              onClick={() => handleOpenEditDialog(task)}
                              sx={{ color: 'primary.main' }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete task">
                            <IconButton
                              size="small"
                              onClick={() => handleDeleteClick(task)}
                              sx={{ color: 'error.main' }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <PaginationBar
              page={page}
              pageSize={pageSize}
              totalRecords={filteredTasks.length}
              onPageChange={setPage}
              onPageSizeChange={changePageSize}
              recordLabel="tasks"
            />
            </Paper>
          </Box>
        )}

        {/* Create/Edit Dialog */}
        <Dialog open={dialogOpen} onClose={handleCloseDialog} fullWidth maxWidth="sm">
          <DialogTitle>
            {dialogMode === 'create' ? 'Define a new configuration task' : 'Edit configuration task'}
          </DialogTitle>
          <Box component="form" onSubmit={handleSubmit}>
            <DialogContent>
              {submitError && <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>}

              {/* Task Type */}
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel id="task-type-label">Task Type</InputLabel>
                <Select
                  labelId="task-type-label"
                  label="Task Type"
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value)
                    setFile(null)
                  }}
                >
                  {TASK_TYPES.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      {type.label}
                    </MenuItem>
                  ))}
                </Select>
                <Typography variant="caption" sx={{ color: 'text.secondary', mt: 1 }}>
                  {TASK_TYPES.find((t) => t.value === category)?.description}
                </Typography>
              </FormControl>

              <TextField
                fullWidth
                required
                label="Task name"
                placeholder="e.g. Scheduled Operations Setup"
                value={name}
                onChange={(e) => setName(e.target.value)}
                sx={{ mb: 3 }}
              />
              <TextField
                fullWidth
                multiline
                minRows={3}
                label="Description"
                placeholder="What does this configuration task do?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                sx={{ mb: 3 }}
              />
              <Button
                component="label"
                variant="outlined"
                startIcon={<UploadFileIcon />}
                sx={{ textTransform: 'none', py: 1.5, borderRadius: 2 }}
              >
                {file
                  ? file.name
                  : dialogMode === 'edit'
                  ? 'Keep existing file (optional)'
                  : category === 'skill_engine'
                  ? 'Choose rules file (.txt, .pdf, .doc, .docx)'
                  : 'Choose Excel template (.xlsx)'}
                <input
                  type="file"
                  accept={getFileAccept(category)}
                  hidden
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </Button>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                {dialogMode === 'edit'
                  ? 'Upload a new file only if you want to replace the existing one.'
                  : category === 'skill_engine'
                  ? 'The rules file defines the business rules used by the Skill Engine.'
                  : 'The column headers in this file\'s first row must match the target table\'s real column names.'}
              </Typography>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 3 }}>
              <Button onClick={handleCloseDialog} disabled={isSubmitting} sx={{ textTransform: 'none' }}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="contained"
                disabled={isSubmitting}
                sx={{
                  textTransform: 'none',
                  background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
                }}
              >
                {isSubmitting ? 'Saving...' : (dialogMode === 'create' ? 'Create Task' : 'Update Task')}
              </Button>
            </DialogActions>
          </Box>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel} maxWidth="sm" fullWidth>
          <DialogTitle>Delete Task</DialogTitle>
          <DialogContent>
            <Typography variant="body1" sx={{ color: 'text.primary', mb: 2 }}>
              Are you sure you want to delete the task <strong>"{taskToDelete?.name}"</strong>?
            </Typography>
            <Alert severity="warning" sx={{ borderRadius: 2 }}>
              This action cannot be undone. The task will be permanently deleted from the database.
            </Alert>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button onClick={handleDeleteCancel} disabled={isDeleting} sx={{ textTransform: 'none' }}>
              Cancel
            </Button>
            <Button
              onClick={handleDeleteConfirm}
              variant="contained"
              color="error"
              disabled={isDeleting}
              startIcon={isDeleting ? <CircularProgress size={16} /> : <DeleteIcon />}
              sx={{ textTransform: 'none' }}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar Notification */}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={handleSnackbarClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={handleSnackbarClose}
            severity={snackbar.severity}
            sx={{ width: '100%', borderRadius: 2 }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Box>
  )
}

export default TaskManagement

