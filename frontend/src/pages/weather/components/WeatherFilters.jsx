import { useEffect, useState } from 'react'
import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { useWeatherOptions } from '../../../hooks/useWeatherOptions.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

const SOURCE_OPTIONS = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]

const EMPTY = {
  station_id: '',
  period: '',
  data_source: '',
  factor: '',
  date_from: '',
  date_to: '',
  keyword: ''
}

export default function WeatherFilters({ value, loading, onSubmit, onReset }) {
  const [draft, setDraft] = useState(value)
  const { data: options } = useWeatherOptions()

  useEffect(() => {
    setDraft(value)
  }, [value])

  const update = (key) => (event) => setDraft({ ...draft, [key]: event.target.value })

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(draft)}
      onReset={() => {
        setDraft(EMPTY)
        onReset()
      }}
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
      <Field label="关键字">
        <Input
          placeholder="监测点名称 / 编码 / 区域"
          value={draft.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={(event) => event.key === 'Enter' && onSubmit(draft)}
        />
      </Field>
      <Field label="数据周期">
        <Select value={draft.period || ''} onChange={update('period')} placeholder="全部周期" options={PERIODS} />
      </Field>
      <Field label="包含要素">
        <Select
          value={draft.factor || ''}
          onChange={update('factor')}
          placeholder="不限制"
          options={(options?.factors ?? []).map((item) => ({ value: item.code, label: `${item.label}(${item.unit})` }))}
        />
      </Field>
      <Field label="数据来源">
        <Select value={draft.data_source || ''} onChange={update('data_source')} placeholder="全部来源" options={SOURCE_OPTIONS} />
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

export { EMPTY as WEATHER_FILTER_EMPTY }
