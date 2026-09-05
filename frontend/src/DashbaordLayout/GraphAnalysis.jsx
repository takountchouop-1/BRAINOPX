import React, { useMemo } from 'react'
import {
  Box,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
} from 'recharts'

import InboxIconImport from '@mui/icons-material/Inbox'
import InsightsIconImport from '@mui/icons-material/Insights'
import AssessmentOutlinedIconImport from '@mui/icons-material/AssessmentOutlined'
import ExtensionOutlinedIconImport from '@mui/icons-material/ExtensionOutlined'
import PriorityHighIconImport from '@mui/icons-material/PriorityHigh'
import { useTranslation } from 'react-i18next'

import { STATUS_META, statusOf, PRIORITY_META, priorityOf, StatCard, dateOf } from './DashboardHome.jsx'

const InboxIcon = InboxIconImport?.default || InboxIconImport
const InsightsIcon = InsightsIconImport?.default || InsightsIconImport
const AssessmentOutlinedIcon = AssessmentOutlinedIconImport?.default || AssessmentOutlinedIconImport
const ExtensionOutlinedIcon = ExtensionOutlinedIconImport?.default || ExtensionOutlinedIconImport
const PriorityHighIcon = PriorityHighIconImport?.default || PriorityHighIconImport

// ─── CATEGORY ────────────────────────────────────────────────────────────────
// The two task types the configuration flow supports (TaskManagement.jsx's
// TASK_TYPES) — same labels and colours, so a category reads the same
// wherever it appears. Labels are resolved with `t` at the call site so
// this stays translation-aware.
const categoryOf = (value, t) => {
  if (value === 'report_analyses') return { label: t('graphAnalysis.category.reportAnalyses'), color: '#a02bbf' }
  if (value === 'skill_engine') return { label: t('graphAnalysis.category.skillEngine'), color: '#2979ff' }
  return {
    label: value ? value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : t('graphAnalysis.category.other'),
    color: '#64748b',
  }
}

// Where a request stands, collapsed to the three buckets the backend
// already sorts every request into — same colours as the Overview tab's
// stat tiles, so the two views never disagree on what a colour means.
const BUCKET_META = {
  not_started: { key: 'not_started', color: '#f59e0b' },
  pending: { key: 'pending', color: '#3b82f6' },
  completed: { key: 'completed', color: '#16a34a' },
}

// Percentage printed straight on the slice — a pie with this many
// categories needs the number in place, not just a colour, to be
// readable. Slivers too thin to hold text are left blank rather than
// overlapping their neighbour.
const renderSliceLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.045) return null
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.62
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} textAnchor="middle" dominantBaseline="central" style={{ fill: '#fff', fontSize: 12.5, fontWeight: 700 }}>
      {`${Math.round(percent * 100)}%`}
    </text>
  )
}

// A colour dot beside its label, wrapped across as many rows as
// needed — the legend row from the reference mock, driven by
// whichever statuses actually appear rather than a fixed set of five.
const DotLegend = ({ rows }) => (
  <Stack direction="row" flexWrap="wrap" columnGap={2} rowGap={0.75} sx={{ mb: 1.5 }}>
    {rows.map((row) => (
      <Stack key={row.key} direction="row" alignItems="center" spacing={0.75}>
        <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: row.color, flexShrink: 0 }} />
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, whiteSpace: 'nowrap' }}>
          {row.label}
        </Typography>
      </Stack>
    ))}
  </Stack>
)

const cardSx = (theme) => ({
  p: 2.5,
  borderRadius: 3,
  height: '100%',
  background: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
  border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
})

const GraphAnalysis = ({ items = [], loading = false }) => {
  const theme = useTheme()
  const { t } = useTranslation('layout')
  const gridStroke = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#eef0f4'
  const tickColor = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.6)' : '#64748b'
  const tooltipSx = {
    contentStyle: {
      borderRadius: 10,
      border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.15)' : '#e5e7eb'}`,
      background: theme.palette.mode === 'dark' ? '#1e293b' : '#ffffff',
      fontSize: 12.5,
    },
    labelStyle: { fontWeight: 700, color: theme.palette.mode === 'dark' ? '#fff' : '#0f172a' },
  }

  // ─── STATUS DISTRIBUTION ─────────────────────────────────────────────────
  const statusData = useMemo(() => {
    const counts = {}
    items.forEach((item) => {
      counts[item.status] = (counts[item.status] || 0) + 1
    })
    return Object.keys(STATUS_META)
      .map((key) => ({ key, label: t(STATUS_META[key].labelKey), color: STATUS_META[key].color, count: counts[key] || 0 }))
      .filter((row) => row.count > 0)
  }, [items, t])
  const statusTotal = statusData.reduce((sum, row) => sum + row.count, 0)

  // ─── PRIORITY BREAKDOWN ──────────────────────────────────────────────────
  const priorityData = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 }
    items.forEach((item) => {
      const key = String(item.priority || 'medium').toLowerCase()
      counts[key] = (counts[key] || 0) + 1
    })
    return ['high', 'medium', 'low'].map((key) => ({
      key,
      label: t(PRIORITY_META[key].labelKey),
      color: PRIORITY_META[key].color,
      count: counts[key] || 0,
    }))
  }, [items, t])

  // ─── REPORT ANALYSES BREAKDOWN ───────────────────────────────────────────
  // Not started / in progress / completed, scoped to the Excel-template
  // category — same shape as the Skill Engine chart below, just filtered
  // to the other category, so the two panels read identically.
  const reportCategoryData = useMemo(() => {
    const row = { key: 'report_analyses', label: categoryOf('report_analyses', t).label, not_started: 0, pending: 0, completed: 0, total: 0 }
    items
      .filter((item) => (item.task_category || 'other') === 'report_analyses')
      .forEach((item) => {
        const bucket = BUCKET_META[item.bucket] ? item.bucket : 'pending'
        row[bucket] += 1
        row.total += 1
      })
    return [row]
  }, [items, t])

  // ─── SKILL ENGINE BREAKDOWN ──────────────────────────────────────────────
  // Not started / in progress / completed, scoped to the rule-based
  // category only — Report Analyses already gets its own tracking panel,
  // so this chart is Skill Engine's equivalent.
  const categoryData = useMemo(() => {
    const row = { key: 'skill_engine', label: categoryOf('skill_engine', t).label, not_started: 0, pending: 0, completed: 0, total: 0 }
    items
      .filter((item) => (item.task_category || 'other') === 'skill_engine')
      .forEach((item) => {
        const bucket = BUCKET_META[item.bucket] ? item.bucket : 'pending'
        row[bucket] += 1
        row.total += 1
      })
    return [row]
  }, [items, t])

  // ─── REPORT ANALYSES TRACKING ────────────────────────────────────────────
  const reportAnalyses = useMemo(() => {
    const rows = items.filter((item) => (item.task_category || 'other') === 'report_analyses')
    const completed = rows.filter((r) => r.bucket === 'completed').length
    const pending = rows.filter((r) => r.bucket === 'pending').length
    const notStarted = rows.filter((r) => r.bucket === 'not_started').length
    const total = rows.length
    const recent = [...rows]
      .sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
      .slice(0, 5)
    return {
      total,
      completed,
      pending,
      notStarted,
      completionRate: total ? Math.round((completed / total) * 100) : 0,
      recent,
    }
  }, [items])

  const skillEngineTotal = useMemo(
    () => items.filter((item) => (item.task_category || 'other') === 'skill_engine').length,
    [items]
  )

  const overallCompletion = useMemo(() => {
    if (!items.length) return 0
    const sum = items.reduce((acc, item) => acc + (item.progress || 0), 0)
    return Math.round(sum / items.length)
  }, [items])

  const highPriorityOpen = useMemo(
    () => items.filter((item) => String(item.priority || '').toLowerCase() === 'high' && item.bucket !== 'completed').length,
    [items]
  )

  if (loading) {
    return (
      <Stack alignItems="center" justifyContent="center" sx={{ py: 10 }}>
        <CircularProgress size={28} />
      </Stack>
    )
  }

  if (items.length === 0) {
    return (
      <Paper sx={(t) => cardSx(t)}>
        <Stack alignItems="center" spacing={1} sx={{ color: 'text.disabled', py: 6 }}>
          <InboxIcon sx={{ fontSize: 36, opacity: 0.4 }} />
          <Typography variant="body2">
            {t('graphAnalysis.emptyState')}
          </Typography>
        </Stack>
      </Paper>
    )
  }

  return (
    <Box>
      {/* ── Headline tiles ─────────────────────────────────────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={InsightsIcon}
            iconColor="#4f46e5"
            iconBg="rgba(79,70,229,0.12)"
            label={t('graphAnalysis.stats.overallCompletion')}
            value={`${overallCompletion}%`}
            subtitle={t('graphAnalysis.stats.averageAcrossEveryRequest')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={AssessmentOutlinedIcon}
            iconColor="#a02bbf"
            iconBg="rgba(160,43,191,0.12)"
            label={t('graphAnalysis.stats.reportAnalyses')}
            value={reportAnalyses.total}
            subtitle={t('graphAnalysis.stats.percentCompleted', { percent: reportAnalyses.completionRate })}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={ExtensionOutlinedIcon}
            iconColor="#2979ff"
            iconBg="rgba(41,121,255,0.12)"
            label={t('graphAnalysis.stats.skillEngine')}
            value={skillEngineTotal}
            subtitle={t('graphAnalysis.stats.ruleBasedRequests')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={PriorityHighIcon}
            iconColor="#dc2626"
            iconBg="rgba(220,38,38,0.12)"
            label={t('graphAnalysis.stats.highPriorityOpen')}
            value={highPriorityOpen}
            subtitle={t('graphAnalysis.stats.notYetCompleted')}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        {/* ── By task category (Report Analyses) ──────────────────── */}
        <Grid item xs={12} md={7}>
          <Paper sx={cardSx(theme)}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.25 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                {t('graphAnalysis.charts.byTaskCategory')}
              </Typography>
              <Chip
                size="small"
                label={t('graphAnalysis.category.reportAnalyses')}
                sx={{ fontWeight: 700, fontSize: 11, color: '#a02bbf', bgcolor: 'rgba(160,43,191,0.12)' }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('graphAnalysis.charts.notStartedVsInProgressVsCompleted')}
            </Typography>
            <Box sx={{ height: 260, mt: 1 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reportCategoryData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke={gridStroke} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: tickColor }} axisLine={{ stroke: gridStroke }} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: tickColor }} axisLine={false} tickLine={false} />
                  <Tooltip {...tooltipSx} cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="not_started" name={t('graphAnalysis.bucket.notStarted')} stackId="a" fill={BUCKET_META.not_started.color} radius={[0, 0, 0, 0]} maxBarSize={54} />
                  <Bar dataKey="pending" name={t('graphAnalysis.bucket.inProgress')} stackId="a" fill={BUCKET_META.pending.color} maxBarSize={54} />
                  <Bar dataKey="completed" name={t('graphAnalysis.bucket.completed')} stackId="a" fill={BUCKET_META.completed.color} radius={[6, 6, 0, 0]} maxBarSize={54} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* ── Priority breakdown ───────────────────────────────────── */}
        <Grid item xs={12} md={5}>
          <Paper sx={cardSx(theme)}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.25 }}>
              {t('graphAnalysis.charts.priorityMix')}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('graphAnalysis.charts.everyRequestByUrgency')}
            </Typography>
            <Box sx={{ height: 260, mt: 1 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorityData} layout="vertical" margin={{ top: 8, right: 28, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={gridStroke} horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: tickColor }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="label" width={70} tick={{ fontSize: 12.5, fill: tickColor }} axisLine={false} tickLine={false} />
                  <Tooltip {...tooltipSx} cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={26}>
                    {priorityData.map((row) => (
                      <Cell key={row.key} fill={row.color} />
                    ))}
                    <LabelList dataKey="count" position="right" style={{ fill: tickColor, fontSize: 12, fontWeight: 700 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        {/* ── Status distribution ──────────────────────────────────── */}
        <Grid item xs={12} md={5}>
          <Paper sx={cardSx(theme)}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.25 }}>
              {t('graphAnalysis.charts.statusDistribution')}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('graphAnalysis.charts.whereEveryRequestSits')}
            </Typography>

            <Box sx={{ mt: 1.5 }}>
              <DotLegend rows={statusData} />
            </Box>

            <Box sx={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip
                    {...tooltipSx}
                    formatter={(value, _name, entry) => [
                      `${value} (${statusTotal ? Math.round((value / statusTotal) * 100) : 0}%)`,
                      entry?.payload?.label,
                    ]}
                  />
                  <Pie
                    data={statusData}
                    dataKey="count"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    labelLine={false}
                    label={renderSliceLabel}
                    isAnimationActive={false}
                  >
                    {statusData.map((row) => (
                      <Cell key={row.key} fill={row.color} stroke={theme.palette.mode === 'dark' ? '#1e293b' : '#ffffff'} strokeWidth={2} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* ── Category breakdown ───────────────────────────────────── */}
        <Grid item xs={12} md={7}>
          <Paper sx={cardSx(theme)}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.25 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                {t('graphAnalysis.charts.byTaskCategory')}
              </Typography>
              <Chip
                size="small"
                label={t('graphAnalysis.category.skillEngine')}
                sx={{ fontWeight: 700, fontSize: 11, color: '#2979ff', bgcolor: 'rgba(41,121,255,0.12)' }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('graphAnalysis.charts.notStartedVsInProgressVsCompleted')}
            </Typography>
            <Box sx={{ height: 260, mt: 1 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke={gridStroke} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: tickColor }} axisLine={{ stroke: gridStroke }} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: tickColor }} axisLine={false} tickLine={false} />
                  <Tooltip {...tooltipSx} cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="not_started" name={t('graphAnalysis.bucket.notStarted')} stackId="a" fill={BUCKET_META.not_started.color} radius={[0, 0, 0, 0]} maxBarSize={54} />
                  <Bar dataKey="pending" name={t('graphAnalysis.bucket.inProgress')} stackId="a" fill={BUCKET_META.pending.color} maxBarSize={54} />
                  <Bar dataKey="completed" name={t('graphAnalysis.bucket.completed')} stackId="a" fill={BUCKET_META.completed.color} radius={[6, 6, 0, 0]} maxBarSize={54} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* ── Report Analyses tracking ───────────────────────────────── */}
      <Paper sx={cardSx(theme)}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
          <Box sx={{ flex: '0 0 260px' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                {t('graphAnalysis.tracking.title')}
              </Typography>
              <Chip
                size="small"
                label={t('graphAnalysis.category.reportAnalyses')}
                sx={{ fontWeight: 700, fontSize: 11, color: '#a02bbf', bgcolor: 'rgba(160,43,191,0.12)' }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('graphAnalysis.tracking.subtitle')}
            </Typography>

            <Typography variant="h3" sx={{ fontWeight: 700, mt: 2 }}>
              {reportAnalyses.completionRate}%
            </Typography>
            <LinearProgress
              variant="determinate"
              value={reportAnalyses.completionRate}
              sx={{
                height: 8,
                borderRadius: 4,
                mt: 1,
                bgcolor: 'rgba(160,43,191,0.12)',
                '& .MuiLinearProgress-bar': { bgcolor: '#a02bbf', borderRadius: 4 },
              }}
            />

            <Stack spacing={0.75} sx={{ mt: 2 }}>
              {[
                { label: t('graphAnalysis.bucket.completed'), value: reportAnalyses.completed, color: BUCKET_META.completed.color },
                { label: t('graphAnalysis.bucket.inProgress'), value: reportAnalyses.pending, color: BUCKET_META.pending.color },
                { label: t('graphAnalysis.bucket.notStarted'), value: reportAnalyses.notStarted, color: BUCKET_META.not_started.color },
              ].map((row) => (
                <Stack key={row.label} direction="row" alignItems="center" spacing={1}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: row.color, flexShrink: 0 }} />
                  <Typography variant="body2" sx={{ color: 'text.secondary', flexGrow: 1 }}>
                    {row.label}
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {row.value}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>

          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 700, color: 'text.secondary', mb: 1 }}>
              {t('graphAnalysis.tracking.mostRecentlyUpdated')}
            </Typography>
            {reportAnalyses.recent.length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.disabled' }}>
                {t('graphAnalysis.tracking.noReportAnalysesYet')}
              </Typography>
            ) : (
              <Stack spacing={0}>
                {reportAnalyses.recent.map((item, idx) => {
                  const meta = statusOf(item.status, t)
                  return (
                    <Stack
                      key={item.id}
                      direction="row"
                      alignItems="center"
                      spacing={1.5}
                      sx={{
                        py: 1.1,
                        borderTop: idx === 0 ? 'none' : `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#f1f3f7'}`,
                      }}
                    >
                      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                        <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                          {item.task_name}
                        </Typography>
                      </Box>
                      <Chip
                        size="small"
                        label={meta.label}
                        sx={{ fontWeight: 700, fontSize: 11, color: meta.color, bgcolor: `${meta.color}1F`, border: 'none' }}
                      />
                      <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap', width: 88, textAlign: 'right' }}>
                        {dateOf(item.updated_at || item.created_at)}
                      </Typography>
                    </Stack>
                  )
                })}
              </Stack>
            )}
          </Box>
        </Stack>
      </Paper>
    </Box>
  )
}

export default GraphAnalysis
