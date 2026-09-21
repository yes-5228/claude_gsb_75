import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

function valueCell(row, key, unit, missing = '-') {
  const value = row[key]
  if (value === null || value === undefined) return <span className="muted">{missing}</span>
  return (
    <span>
      {formatNumber(value, key === 'wind_direction' ? 0 : 1)} <span className="muted small">{unit}</span>
    </span>
  )
}

export default function WeatherTable({ rows, loading, onDelete }) {
  const columns = [
    {
      key: 'measured_at',
      title: '观测时间',
      className: 'cell-nowrap',
      render: (row) => formatDateTime(row.measured_at)
    },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <div>
          <div>{row.station?.name || '-'}</div>
          <div className="small muted mono">{row.station?.code || ''}</div>
        </div>
      )
    },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    { key: 'temperature', title: '温度', align: 'right', render: (row) => valueCell(row, 'temperature', '℃') },
    { key: 'humidity', title: '湿度', align: 'right', render: (row) => valueCell(row, 'humidity', '%') },
    { key: 'wind_speed', title: '风速', align: 'right', render: (row) => valueCell(row, 'wind_speed', 'm/s') },
    {
      key: 'wind_direction',
      title: '风向',
      className: 'cell-nowrap',
      render: (row) =>
        row.wind_direction === null || row.wind_direction === undefined ? (
          <span className="muted">-</span>
        ) : (
          <Tag tone="info" title={`${formatNumber(row.wind_direction, 0)}°`}>
            {row.is_calm ? '静风' : `${row.wind_dir_label} ${formatNumber(row.wind_direction, 0)}°`}
          </Tag>
        )
    },
    { key: 'pressure', title: '气压', align: 'right', render: (row) => valueCell(row, 'pressure', 'hPa') },
    { key: 'precipitation', title: '降水', align: 'right', render: (row) => valueCell(row, 'precipitation', 'mm') },
    {
      key: 'data_source_label',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
          删除
        </button>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="暂无气象记录, 请先在上方录入"
      emptyIcon="🌦️"
    />
  )
}
