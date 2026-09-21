import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

const SECTOR_NAMES = ['北风', '东北风', '东风', '东南风', '南风', '西南风', '西风', '西北风']

export function sectorLabel(degree) {
  if (degree === null || degree === undefined) return '-'
  const sector = Math.round(Number(degree) / 45) % 8
  return SECTOR_NAMES[sector]
}

export default function WeatherRecordTable({ rows, loading, onDelete }) {
  const columns = [
    {
      key: 'measured_at',
      title: '观测时间',
      width: 150,
      render: (row) => <span className="nowrap">{formatDateTime(row.measured_at)}</span>
    },
    {
      key: 'station',
      title: '监测点',
      render: (row) =>
        row.station ? (
          <span>
            {row.station.code} {row.station.name}
            <span className="small muted"> · {row.station.area}</span>
          </span>
        ) : (
          row.station_id
        )
    },
    {
      key: 'period',
      title: '周期',
      width: 80,
      render: (row) => <Tag tone="outline">{row.period_label}</Tag>
    },
    {
      key: 'temperature',
      title: '温度(℃)',
      align: 'right',
      render: (row) => formatNumber(row.temperature, 1)
    },
    {
      key: 'humidity',
      title: '湿度(%)',
      align: 'right',
      render: (row) => formatNumber(row.humidity, 0)
    },
    {
      key: 'wind_speed',
      title: '风速(m/s)',
      align: 'right',
      render: (row) => formatNumber(row.wind_speed, 1)
    },
    {
      key: 'wind_direction',
      title: '风向',
      render: (row) =>
        row.wind_direction === null || row.wind_direction === undefined ? (
          '-'
        ) : (
          <span className="nowrap">
            {formatNumber(row.wind_direction, 0)}°
            <span className="small muted"> {sectorLabel(row.wind_direction)}</span>
          </span>
        )
    },
    {
      key: 'pressure',
      title: '气压(hPa)',
      align: 'right',
      render: (row) => formatNumber(row.pressure, 1)
    },
    {
      key: 'precipitation',
      title: '降水(mm)',
      align: 'right',
      render: (row) => formatNumber(row.precipitation, 1)
    },
    {
      key: 'data_source',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source] || 'neutral'}>{row.data_source_label}</Tag>
    },
    {
      key: 'recorder',
      title: '录入人',
      render: (row) => row.recorder || '-'
    },
    {
      key: 'actions',
      title: '操作',
      width: 72,
      render: (row) => (
        <button
          type="button"
          className="btn btn-sm btn-danger"
          onClick={() => onDelete?.(row)}
        >
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
      emptyText="暂无气象观测记录, 请先在上方录入"
      emptyIcon="🌦️"
    />
  )
}
