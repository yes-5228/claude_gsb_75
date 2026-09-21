import { useCallback, useEffect, useState } from 'react'
import { downloadFile } from '../../api/client.js'
import {
  exportCorrelationUrl,
  exportWeatherUrl,
  getCorrelation,
  deleteWeather,
  listWeather
} from '../../api/weather.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { useListQuery } from '../../hooks/useListQuery.js'
import { saveBlob } from '../../utils/download.js'
import { formatDateTime, formatNumber } from '../../utils/format.js'
import AnalysisFilters from './components/AnalysisFilters.jsx'
import CorrelationPanel from './components/CorrelationPanel.jsx'
import WeatherEntryForm from './components/WeatherEntryForm.jsx'
import WeatherFilters, { WEATHER_FILTER_EMPTY } from './components/WeatherFilters.jsx'
import WeatherRecordTable from './components/WeatherRecordTable.jsx'

const INITIAL_ANALYSIS = {
  station_id: '',
  area: '',
  period: 'hourly',
  pollutant: 'PM25',
  weather_factor: 'temperature',
  date_from: '',
  date_to: ''
}

export default function WeatherPage() {
  const toast = useToast()
  const query = useListQuery(listWeather, WEATHER_FILTER_EMPTY, { pageSize: 10 })
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [analysisFilters, setAnalysisFilters] = useState(INITIAL_ANALYSIS)

  const analysisLoader = useCallback(() => getCorrelation(analysisFilters), [analysisFilters])
  const analysis = useAsyncData(analysisLoader, { immediate: false })

  useEffect(() => {
    analysis.reload().catch(() => {})
  }, [analysis.reload])

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteWeather(pendingDelete.id)
      toast.success('气象记录已删除')
      setPendingDelete(null)
      query.reload()
      analysis.reload().catch(() => {})
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }, [pendingDelete, query, analysis, toast])

  const handleExportRecords = async () => {
    setExporting('records')
    try {
      const blob = await downloadFile(exportWeatherUrl(query.filters))
      saveBlob(blob, `气象观测记录_${Date.now()}.csv`)
      toast.success('导出任务已完成, 请查看下载文件')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setExporting(null)
    }
  }

  const handleExportCorrelation = async () => {
    setExporting('correlation')
    try {
      const blob = await downloadFile(exportCorrelationUrl(analysisFilters))
      saveBlob(blob, `气象浓度对照样本_${Date.now()}.csv`)
      toast.success('对照样本已导出, 请查看下载文件')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setExporting(null)
    }
  }

  const summary = query.summary

  return (
    <>
      <WeatherEntryForm
        onSubmitted={() => {
          query.reload()
          analysis.reload().catch(() => {})
        }}
      />

      <WeatherFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(WEATHER_FILTER_EMPTY)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <div className="stat-grid">
        <StatCard label="气象观测记录" value={summary ? summary.total : '-'} foot={summary ? `涉及 ${summary.station_count} 个监测点` : ''} />
        <StatCard label="平均温度" value={summary ? formatNumber(summary.avg_temperature, 1) : '-'} unit="℃" />
        <StatCard label="平均相对湿度" value={summary ? formatNumber(summary.avg_humidity, 0) : '-'} unit="%" />
        <StatCard
          label="平均风速"
          value={summary ? formatNumber(summary.avg_wind_speed, 2) : '-'}
          unit="m/s"
          foot={summary ? `${formatDateTime(summary.first_measured_at)} ~ ${formatDateTime(summary.last_measured_at)}` : ''}
        />
      </div>

      <SectionCard
        title="气象观测记录"
        hint="按观测时间倒序, 支持按点位/时间/要素筛选"
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={query.reload} disabled={query.loading}>
              刷新
            </button>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleExportRecords} disabled={exporting !== null}>
              {exporting === 'records' ? '导出中...' : '导出 CSV'}
            </button>
          </>
        }
      >
        <WeatherRecordTable rows={query.items} loading={query.loading} onDelete={setPendingDelete} />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <AnalysisFilters
        value={analysisFilters}
        loading={analysis.loading}
        onSubmit={(next) => setAnalysisFilters(next)}
        onReset={() => setAnalysisFilters(INITIAL_ANALYSIS)}
      />

      <div className="inline" style={{ justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="btn btn-sm btn-primary"
          onClick={handleExportCorrelation}
          disabled={exporting !== null || analysis.loading}
        >
          {exporting === 'correlation' ? '导出中...' : '导出对照样本 CSV'}
        </button>
      </div>

      <CorrelationPanel data={analysis.data} loading={analysis.loading} error={analysis.error} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={deleting}
        title="删除气象记录"
        message={`确认删除 ${formatDateTime(pendingDelete?.measured_at)} 的这条气象观测记录吗?`}
        detail="删除后关联分析中的对应配对样本也会随之减少。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
