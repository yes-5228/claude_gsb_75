import { useCallback, useState } from 'react'
import { downloadFile } from '../../api/client.js'
import { deleteWeather, exportCorrelationUrl, exportWeatherUrl, listWeather } from '../../api/weather.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useListQuery } from '../../hooks/useListQuery.js'
import { saveBlob } from '../../utils/download.js'
import WeatherEntryForm from './components/WeatherEntryForm.jsx'
import WeatherFilters from './components/WeatherFilters.jsx'
import WeatherTable from './components/WeatherTable.jsx'
import CorrelationPanel from './components/CorrelationPanel.jsx'

const INITIAL_FILTERS = { station_id: '', period: '', factor: '', date_from: '', date_to: '' }

export default function WeatherPage() {
  const toast = useToast()
  const query = useListQuery(listWeather, INITIAL_FILTERS)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [correlationExporting, setCorrelationExporting] = useState(false)

  const handleSubmitted = useCallback(() => {
    query.reload()
  }, [query])

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteWeather(pendingDelete.id)
      toast.success('气象记录已删除')
      setPendingDelete(null)
      query.reload()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }, [pendingDelete, query, toast])

  const handleExport = useCallback(async () => {
    setExporting(true)
    try {
      const blob = await downloadFile(exportWeatherUrl(query.filters))
      saveBlob(blob, `气象记录_${Date.now()}.csv`)
      toast.success('导出完成, 请查看下载文件')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setExporting(false)
    }
  }, [query.filters, toast])

  const handleCorrelationExport = useCallback(
    async (filters) => {
      setCorrelationExporting(true)
      try {
        const blob = await downloadFile(exportCorrelationUrl(filters))
        saveBlob(blob, `气象浓度关联配对_${Date.now()}.csv`)
        toast.success('关联配对明细导出完成')
      } catch (error) {
        toast.error(error.message)
      } finally {
        setCorrelationExporting(false)
      }
    },
    [toast]
  )

  return (
    <>
      <WeatherEntryForm onSubmitted={handleSubmitted} />

      <WeatherFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(INITIAL_FILTERS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="气象观测记录"
        hint="按观测时间倒序, 可按点位 / 周期 / 要素 / 时间范围筛选并导出"
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={query.reload} disabled={query.loading}>
              刷新
            </button>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleExport} disabled={exporting}>
              {exporting ? '导出中...' : '导出 CSV'}
            </button>
          </>
        }
      >
        <WeatherTable rows={query.items} loading={query.loading} onDelete={(row) => setPendingDelete(row)} />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <CorrelationPanel onExport={handleCorrelationExport} exporting={correlationExporting} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={deleting}
        title="删除气象记录"
        message={`确认删除该时刻 (${pendingDelete?.measured_at?.replace('T', ' ').slice(0, 16) || ''}) 的气象记录吗?`}
        detail="删除后该时刻将无法再与同期浓度进行关联对照。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
