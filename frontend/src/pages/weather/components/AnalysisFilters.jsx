import { useEffect, useState } from 'react'
import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { useWeatherOptions } from '../../../hooks/useWeatherOptions.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

// 数值相关分析默认要素 (风向走玫瑰图)
const NUMERIC_FACTOR_CODES = ['temperature', 'humidity', 'wind_speed', 'pressure', 'precipitation']

export default function AnalysisFilters({ value, loading, onSubmit, onReset, onFactorChange }) {
  const [draft, setDraft] = useState(value)
  const { data: options } = useWeatherOptions()

  useEffect(() => {
    setDraft(value)
  }, [value])

  const update = (key) => (event) => {
    const next = { ...draft, [key]: event.target.value }
    setDraft(next)
    if (key === 'weather_factor') onFactorChange?.(event.target.value)
  }

  const factorOptions = (options?.factors ?? []).filter((item) =>
    NUMERIC_FACTOR_CODES.includes(item.code)
  )
  // 风向额外作为可选项 (后端按方位分组返回)
  const windDirection = (options?.factors ?? []).find((item) => item.code === 'wind_direction')
  if (windDirection) factorOptions.push(windDirection)

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(draft)}
      onReset={() => {
        const empty = {
          station_id: '',
          area: '',
          period: 'hourly',
          pollutant: 'PM25',
          weather_factor: 'temperature',
          date_from: '',
          date_to: ''
        }
        setDraft(empty)
        onReset()
      }}
      extra={
        <div className="small muted">
          关联规则: 同一监测点、同一时刻、同一数据周期的气象观测与浓度自动配对;
          跨点位时按各点位分别标准化 (z-score) 后计算 Pearson 相关系数。
        </div>
      }
    >
      <Field label="监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(options?.stations ?? []).map((item) => ({
            value: String(item.id),
            label: `${item.code} ${item.name}`
          }))}
        />
      </Field>
      <Field label="所属区域">
        <Select
          value={draft.area || ''}
          onChange={update('area')}
          placeholder="全部区域"
          options={(options?.areas ?? []).map((area) => ({ value: area, label: area }))}
        />
      </Field>
      <Field label="数据周期">
        <Select value={draft.period || 'hourly'} onChange={update('period')} options={PERIODS} />
      </Field>
      <Field label="污染浓度因子">
        <Select
          value={draft.pollutant || 'PM25'}
          onChange={update('pollutant')}
          options={(options?.pollutants ?? []).map((item) => ({
            value: item.value,
            label: `${item.label} (${item.unit})`
          }))}
        />
      </Field>
      <Field label="气象要素">
        <Select
          value={draft.weather_factor || 'temperature'}
          onChange={update('weather_factor')}
          options={factorOptions.map((item) => ({
            value: item.code,
            label: `${item.label} (${item.unit})${item.correlatable ? '' : ' · 方位统计'}`
          }))}
        />
      </Field>
      <Field label="开始日期">
        <Input type="date" value={draft.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="结束日期">
        <Input type="date" value={draft.date_to || ''} onChange={update('date_to')} />
      </Field>
    </FilterPanel>
  )
}
