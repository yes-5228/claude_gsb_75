import { useMemo, useState } from 'react'
import { correlation } from '../../../api/weather.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { Alert, EmptyState, Loading } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import StatCard from '../../../components/common/StatCard.jsx'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { WEATHER_FACTORS } from '../../../constants/index.js'
import { formatNumber, formatPercent } from '../../../utils/format.js'
import CorrelationChart from './CorrelationChart.jsx'
import WindRose from './WindRose.jsx'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

// 可切换的气象因子: 5 个连续要素 + 风向
const FACTOR_TABS = WEATHER_FACTORS.map((item) => ({
  value: item.code,
  label: item.label.replace('角度', ''),
  unit: item.unit
}))

const EMPTY_FILTERS = {
  station_id: '',
  pollutant: 'PM25',
  period: 'hourly',
  date_from: '',
  date_to: ''
}

function strengthTone(strength) {
  if (!strength) return 'neutral'
  if (strength.includes('极强') || strength.includes('强相关')) return 'danger'
  if (strength.includes('中等')) return 'warning'
  return 'neutral'
}

function rTone(r) {
  if (r === null || r === undefined) return 'var(--text-muted)'
  const abs = Math.abs(r)
  if (abs >= 0.6) return 'var(--danger)'
  if (abs >= 0.4) return 'var(--warning)'
  return 'var(--text)'
}

export default function CorrelationPanel({ onExport, exporting = false }) {
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [selectedFactor, setSelectedFactor] = useState('temperature')

  const loader = useMemo(
    () => () => correlation(filters),
    // 仅在筛选条件(点位/时间/污染因子/周期)变化时重新请求; 切换气象因子走本地数据
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filters]
  )
  const { data, loading, error, reload } = useAsyncData(loader)

  const update = (key) => (event) => setFilters((prev) => ({ ...prev, [key]: event.target.value }))

  // 当前选中的气象因子结果: 连续要素取 result/factor_ranking 合并视图, 风向取 wind_result
  const isWind = selectedFactor === 'wind_direction'
  const activeResult = useMemo(() => {
    if (!data) return null
    if (isWind) return data.wind_result
    if (data.params.factor === selectedFactor) return data.result
    return data.factor_ranking?.find((item) => item.factor === selectedFactor) || null
  }, [data, isWind, selectedFactor])

  const factorMeta = FACTOR_TABS.find((item) => item.value === selectedFactor) || {}
  const pollutantMeta = pollutantData?.items?.find((item) => item.code === filters.pollutant) || {}
  const pollutantUnit = pollutantMeta.unit || data?.params?.pollutant_unit || ''
  const pollutantLabel = data?.params?.pollutant_label || pollutantMeta.label || ''

  return (
    <SectionCard
      title="气象要素与同期浓度关联分析"
      hint="按“监测点 + 同时刻 + 同周期”配对浓度与气象观测, 切换因子即时对照"
      actions={
        <div className="inline">
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => onExport?.(filters)}
            disabled={loading || exporting || !data?.sample_total}
          >
            {exporting ? '导出中...' : '导出配对 CSV'}
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => reload()} disabled={loading}>
            {loading ? '分析中...' : '重新分析'}
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="filter-bar">
          <Field label="监测点">
            <Select
              value={filters.station_id}
              onChange={update('station_id')}
              placeholder="全部监测点"
              options={(stationData?.items ?? []).map((item) => ({
                value: String(item.id),
                label: `${item.code} ${item.name}`
              }))}
            />
          </Field>
          <Field label="对照污染因子">
            <Select
              value={filters.pollutant}
              onChange={update('pollutant')}
              options={(pollutantData?.items ?? []).map((item) => ({ value: item.code, label: item.label }))}
            />
          </Field>
          <Field label="数据周期">
            <Select value={filters.period} onChange={update('period')} options={PERIODS} />
          </Field>
          <Field label="开始日期">
            <Input type="date" value={filters.date_from} onChange={update('date_from')} />
          </Field>
          <Field label="结束日期">
            <Input type="date" value={filters.date_to} onChange={update('date_to')} />
          </Field>
        </div>

        <div className="factor-tabs">
          {FACTOR_TABS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`factor-tab ${selectedFactor === item.value ? 'active' : ''}`}
              onClick={() => setSelectedFactor(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {error ? <Alert tone="error">{error.message}</Alert> : null}
        {loading && !data ? <Loading text="正在配对同期数据并计算关联..." /> : null}

        {data && data.sample_total === 0 ? (
          <EmptyState
            text="所选范围内没有同时具备浓度与气象观测的配对数据, 请调整点位或时间范围"
            icon="🌬️"
          />
        ) : null}

        {data && data.sample_total > 0 ? (
          <>
            <div className="stat-grid">
              <StatCard label="配对样本数" value={data.sample_total} foot="浓度与气象同时刻配对" />
              {isWind ? (
                <StatCard
                  label="主导风向"
                  value={activeResult?.prevailing_sector_label || '-'}
                  foot={`出现占比 ${formatPercent(
                    Math.max(...(activeResult?.sectors || []).map((item) => item.ratio), 0)
                  )}`}
                />
              ) : (
                <StatCard
                  label="Pearson 相关系数"
                  value={activeResult?.pearson_r === null || activeResult?.pearson_r === undefined ? '-' : formatNumber(activeResult.pearson_r, 3)}
                  foot={activeResult?.direction || '样本不足'}
                  tone={Math.abs(activeResult?.pearson_r || 0) >= 0.6 ? 'danger' : Math.abs(activeResult?.pearson_r || 0) >= 0.4 ? 'warning' : undefined}
                />
              )}
              <StatCard
                label={isWind ? '整体平均浓度' : `${factorMeta.label}均值`}
                value={
                  isWind
                    ? formatNumber(activeResult?.overall_avg_concentration)
                    : formatNumber(activeResult?.factor_avg)
                }
                unit={isWind ? pollutantUnit : factorMeta.unit}
                foot={isWind ? '全部配对样本' : `浓度均值 ${formatNumber(activeResult?.concentration_avg)}`}
              />
              <StatCard
                label={isWind ? '静风占比' : '相关强度'}
                value={
                  isWind
                    ? formatPercent(activeResult?.calm?.ratio || 0)
                    : activeResult?.strength || '-'
                }
                foot={isWind ? `静风样本 ${activeResult?.calm?.count || 0} 条` : `n = ${activeResult?.sample_count ?? 0}`}
                tone={isWind ? undefined : strengthTone(activeResult?.strength) === 'danger' ? 'danger' : strengthTone(activeResult?.strength) === 'warning' ? 'warning' : undefined}
              />
            </div>

            {!isWind && (activeResult?.pearson_r === null || activeResult?.pearson_r === undefined) ? (
              <Alert tone="info">配对样本不足 3 组或要素无变化, 无法计算相关系数, 仅展示对照曲线。</Alert>
            ) : null}

            {data.series_truncated ? (
              <Alert tone="info">配对点超过 {data.series_limit} 个, 对照图仅展示最近 {data.series_limit} 个点, 完整数据请导出 CSV。</Alert>
            ) : null}

            <div className="card" style={{ boxShadow: 'none' }}>
              <div className="card-header">
                <h3>{isWind ? '风向 - 浓度玫瑰图' : '同期变化对照'}</h3>
                <span className="hint">
                  {data.params.pollutant_label} · {data.params.period_label}
                  {filters.station_id ? '' : ' · 全部点位'}
                </span>
              </div>
              <div className="card-body">
                {isWind ? (
                  <WindRose result={activeResult} />
                ) : (
                  <CorrelationChart
                    series={data.series}
                    factor={selectedFactor}
                    factorLabel={factorMeta.label}
                    factorUnit={factorMeta.unit}
                    pollutantLabel={pollutantLabel}
                    pollutantUnit={pollutantUnit}
                  />
                )}
              </div>
            </div>

            {!isWind ? (
              <div className="card" style={{ boxShadow: 'none' }}>
                <div className="card-header">
                  <h3>各气象要素相关系数一览</h3>
                  <span className="hint">点击标签可切换对照因子, 无需重新请求</span>
                </div>
                <div className="card-body">
                  <div className="ranking-row">
                    {data.factor_ranking.map((item) => (
                      <button
                        key={item.factor}
                        type="button"
                        className={`ranking-chip ${selectedFactor === item.factor ? 'active' : ''}`}
                        onClick={() => setSelectedFactor(item.factor)}
                      >
                        <span className="ranking-label">{item.factor_label}</span>
                        <span className="ranking-value" style={{ color: rTone(item.pearson_r) }}>
                          {item.pearson_r === null ? 'n/a' : formatNumber(item.pearson_r, 2)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </SectionCard>
  )
}
