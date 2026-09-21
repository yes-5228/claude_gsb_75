import { SectionCard } from '../../../components/common/Card.jsx'
import { Alert, EmptyState, Loading } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import {
  CORRELATION_STRENGTH_LABELS,
  CORRELATION_STRENGTH_TONE
} from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'
import ComparisonChart from './ComparisonChart.jsx'
import CorrelationScatter from './CorrelationScatter.jsx'
import WindRosePanel from './WindRosePanel.jsx'

function StatItem({ label, value, unit, tone }) {
  return (
    <div className="stat-card" style={{ boxShadow: 'none', border: '1px solid var(--border)' }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: tone || 'var(--text)' }}>
        {value}
        {unit ? <small>{unit}</small> : null}
      </div>
    </div>
  )
}

function directionLabel(direction) {
  if (direction === 'positive') return { text: '正相关', tone: 'danger' }
  if (direction === 'negative') return { text: '负相关', tone: 'info' }
  return { text: '—', tone: 'neutral' }
}

export default function CorrelationPanel({ data, loading, error }) {
  if (loading && !data) return <SectionCard title="气象-浓度关联分析"><Loading text="正在配对同期数据..." /></SectionCard>
  if (error) {
    return (
      <SectionCard title="气象-浓度关联分析">
        <Alert tone="error">{error.message}</Alert>
      </SectionCard>
    )
  }
  if (!data) {
    return (
      <SectionCard title="气象-浓度关联分析" hint="设置上方条件后点击查询">
        <EmptyState text="选择点位、时间范围与对照要素, 查看同期气象与浓度的关联" icon="🔗" />
      </SectionCard>
    )
  }

  const { correlation, wind_breakdown: breakdown, weather_meta: weatherMeta, pollutant_meta: pollutantMeta } = data
  const dir = directionLabel(correlation?.direction)
  const isWindDirection = weatherMeta?.correlatable === false

  return (
    <SectionCard
      title="气象-浓度关联分析"
      hint={`${weatherMeta?.label} 与 ${pollutantMeta?.label} 的同期对照, 共 ${data.pair_count} 组成对样本`}
      actions={
        correlation?.pearson_r !== null && correlation?.pearson_r !== undefined ? (
          <Tag tone={CORRELATION_STRENGTH_TONE[correlation.strength] || 'neutral'}>
            {CORRELATION_STRENGTH_LABELS[correlation.strength] || correlation.strength}
          </Tag>
        ) : null
      }
    >
      <div className="stack">
        {data.pair_count === 0 ? (
          <Alert tone="warning">
            当前条件下没有同时具备气象观测与浓度数据的配对时刻, 请扩大时间范围或更换监测点/要素。
          </Alert>
        ) : null}

        <div className="stat-grid">
          <StatItem
            label="Pearson 相关系数 r"
            value={correlation?.pearson_r !== null && correlation?.pearson_r !== undefined
              ? formatNumber(correlation.pearson_r, 3)
              : isWindDirection
                ? '角度量'
                : '-'}
            tone={dir.tone === 'danger' ? 'var(--danger)' : dir.tone === 'info' ? 'var(--info)' : undefined}
            unit={correlation?.pearson_r !== null && correlation?.pearson_r !== undefined ? dir.text : isWindDirection ? '方位统计' : ''}
          />
          <StatItem label="成对样本数" value={data.pair_count} unit={`组 / ${correlation?.station_count ?? data.station_count_scope ?? '-'} 点`} />
          <StatItem
            label={`${weatherMeta?.label}均值`}
            value={formatNumber(data.weather_stats?.avg)}
            unit={weatherMeta?.unit}
          />
          <StatItem
            label={`${pollutantMeta?.label}均值`}
            value={formatNumber(data.pollutant_stats?.avg)}
            unit={pollutantMeta?.unit}
          />
        </div>

        {correlation?.standardised ? (
          <div className="small muted">
            ℹ️ 当前跨 {correlation.station_count} 个点位分析, 相关系数基于各点位 z-score
            标准化后的 {correlation.sample_size} 个样本计算 (参与标准化 {correlation.used_station_count} 个点位), 已消除点位本底差异影响。
          </div>
        ) : null}

        {isWindDirection ? (
          breakdown ? (
            <div className="stack">
              <Alert tone="info">{breakdown.note}</Alert>
              <WindRosePanel breakdown={breakdown} />
            </div>
          ) : null
        ) : (
          <>
            {correlation?.pearson_r === null && data.pair_count > 0 && data.pair_count < 3 ? (
              <Alert tone="warning">
                成对样本不足 {correlation?.min_samples ?? 3} 组, 相关系数无法稳定计算, 仍可查看下方对照曲线。
              </Alert>
            ) : null}
            <div className="card" style={{ boxShadow: 'none' }}>
              <div className="card-header">
                <h3>同期对照曲线</h3>
                <span className="hint">同一时刻多点位取平均</span>
              </div>
              <div className="card-body">
                <ComparisonChart
                  series={data.series}
                  weatherMeta={weatherMeta}
                  pollutantMeta={pollutantMeta}
                />
              </div>
            </div>
            <div className="card" style={{ boxShadow: 'none' }}>
              <div className="card-header">
                <h3>配对样本散点</h3>
                <span className="hint">点越贴近斜线, 线性关联越强</span>
              </div>
              <div className="card-body">
                <CorrelationScatter
                  points={data.points}
                  weatherMeta={weatherMeta}
                  pollutantMeta={pollutantMeta}
                />
              </div>
            </div>
          </>
        )}

        <PairedSampleTable data={data} />
      </div>
    </SectionCard>
  )
}

function PairedSampleTable({ data }) {
  const rows = (data.points || []).slice().reverse().slice(0, 50)
  if (rows.length === 0) return null
  return (
    <div>
      <div className="table-caption" style={{ borderTop: 'none', paddingLeft: 0 }}>
        配对明细 (最近 {rows.length} 组, 完整数据请导出 CSV)
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>观测时间</th>
              <th>监测点</th>
              <th className="text-right">{data.weather_meta?.label} ({data.weather_meta?.unit})</th>
              <th className="text-right">{data.pollutant_meta?.label} ({data.pollutant_meta?.unit})</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.measured_at}-${row.station_id}-${index}`}>
                <td>{formatDateTime(row.measured_at)}</td>
                <td>#{row.station_id}</td>
                <td className="text-right">{formatNumber(row.weather)}</td>
                <td className="text-right strong">{formatNumber(row.pollutant)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
