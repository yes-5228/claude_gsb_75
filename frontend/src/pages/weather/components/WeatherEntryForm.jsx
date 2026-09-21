import { useEffect, useMemo, useState } from 'react'
import { createWeather } from '../../../api/weather.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import { Field, Input, Select, Checkbox } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { useStationOptions } from '../../../hooks/useOptions.js'
import { WEATHER_FACTORS, windDirectionLabel } from '../../../constants/index.js'
import { toDateTimeInput } from '../../../utils/format.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

const DATA_SOURCES = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]

export default function WeatherEntryForm({ onSubmitted }) {
  const toast = useToast()
  const { data: stationData, loading: stationLoading, error: stationError } = useStationOptions()

  const [form, setForm] = useState({
    station_id: '',
    measured_at: toDateTimeInput(),
    period: 'hourly',
    data_source: 'manual',
    recorder: '',
    remark: '',
    overwrite: false
  })
  const [values, setValues] = useState({})
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!form.station_id && stationData?.items?.length) {
      setForm((prev) => ({ ...prev, station_id: String(stationData.items[0].id) }))
    }
  }, [stationData, form.station_id])

  const filled = useMemo(
    () =>
      Object.entries(values).filter(
        ([, raw]) => raw !== '' && raw !== null && raw !== undefined
      ),
    [values]
  )

  const setField = (key) => (event) => {
    const value = key === 'overwrite' ? event.target.checked : event.target.value
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const setValue = (code) => (event) => {
    setValues((prev) => ({ ...prev, [code]: event.target.value }))
    setErrors((prev) => ({ ...prev, [code]: undefined }))
  }

  const validate = () => {
    const next = {}
    if (!form.station_id) next.station_id = '请选择监测点'
    if (!form.measured_at) next.measured_at = '请选择观测时间'
    if (filled.length === 0) next.entries = '至少填写一个气象要素'
    filled.forEach(([code, raw]) => {
      const meta = WEATHER_FACTORS.find((item) => item.code === code)
      const number = Number(raw)
      if (Number.isNaN(number)) {
        next[code] = '必须为数字'
      } else if (number < meta.min || number > meta.max) {
        next[code] = `合理范围 ${meta.min} ~ ${meta.max} ${meta.unit}`
      }
    })
    setErrors(next)
    if (Object.keys(next).length) {
      setMessage('请先修正表单中标红的问题')
      return false
    }
    setMessage(null)
    return true
  }

  const submit = async () => {
    if (!validate()) return
    setBusy(true)
    try {
      const payload = {
        station_id: Number(form.station_id),
        measured_at: form.measured_at,
        period: form.period,
        data_source: form.data_source,
        recorder: form.recorder || null,
        remark: form.remark || null,
        overwrite: form.overwrite
      }
      filled.forEach(([code, raw]) => {
        payload[code] = Number(raw)
      })
      const result = await createWeather(payload)
      onSubmitted?.(result)
      setValues({})
      setErrors({})
      toast.success(
        result.summary.created_count
          ? `气象记录录入成功, 共 ${result.summary.factor_count} 个要素`
          : '气象记录已更新'
      )
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
      toast.error(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (stationLoading) {
    return (
      <SectionCard title="气象要素录入">
        <div className="loading-block"><span className="spinner" /><span>正在加载监测点...</span></div>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      title="气象要素录入"
      hint="选择监测点与观测时刻, 一次录入温度、湿度、风、气压、降水等要素"
      actions={<Tag tone="primary">{form.period === 'hourly' ? '小时观测' : '日均观测'}</Tag>}
    >
      <div className="stack">
        {stationError ? <Alert tone="error">{stationError.message}</Alert> : null}
        {message ? <Alert tone="error">{message}</Alert> : null}

        <div className="form-grid">
          <Field label="监测点" required error={errors.station_id}>
            <Select
              value={form.station_id}
              onChange={setField('station_id')}
              invalid={Boolean(errors.station_id)}
              placeholder="请选择监测点"
              options={(stationData?.items ?? []).map((item) => ({
                value: String(item.id),
                label: `${item.code} ${item.name} (${item.area})`
              }))}
            />
          </Field>
          <Field label="观测时间" required error={errors.measured_at} hint="应与浓度监测时刻对齐">
            <Input
              type="datetime-local"
              value={form.measured_at}
              onChange={setField('measured_at')}
              invalid={Boolean(errors.measured_at)}
            />
          </Field>
          <Field label="数据周期" required>
            <Select value={form.period} onChange={setField('period')} options={PERIODS} />
          </Field>
          <Field label="数据来源">
            <Select value={form.data_source} onChange={setField('data_source')} options={DATA_SOURCES} />
          </Field>
          <Field label="录入人">
            <Input value={form.recorder} onChange={setField('recorder')} placeholder="如: 张三" />
          </Field>
          <Field label="备注">
            <Input value={form.remark} onChange={setField('remark')} placeholder="选填" />
          </Field>
        </div>

        <div className="card" style={{ boxShadow: 'none' }}>
          <div className="card-header">
            <h3>气象要素观测值</h3>
            <span className="hint">留空表示该时刻缺测; 风向按角度录入, 0/360 为正北</span>
          </div>
          <div className="card-body">
            {errors.entries ? <Alert tone="error">{errors.entries}</Alert> : null}
            <div className="form-grid">
              {WEATHER_FACTORS.map((meta) => {
                const raw = values[meta.code]
                const dirHint = meta.code === 'wind_direction' && raw !== '' && raw !== undefined
                  ? windDirectionLabel(raw)
                  : null
                return (
                  <Field
                    key={meta.code}
                    label={`${meta.label} (${meta.unit})`}
                    error={errors[meta.code]}
                    hint={dirHint ? `方位: ${dirHint}` : `合理范围 ${meta.min} ~ ${meta.max}`}
                  >
                    <div className="inline" style={{ flexWrap: 'nowrap' }}>
                      <Input
                        type="number"
                        step={meta.code === 'wind_direction' ? '1' : '0.1'}
                        min={meta.min}
                        max={meta.max}
                        value={raw ?? ''}
                        onChange={setValue(meta.code)}
                        invalid={Boolean(errors[meta.code])}
                        placeholder="--"
                      />
                      {meta.code === 'wind_direction' && dirHint ? <Tag tone="info">{dirHint}</Tag> : null}
                    </div>
                  </Field>
                )
              })}
            </div>
          </div>
        </div>

        <div>
          <Checkbox
            label="覆盖同一时刻已有气象记录"
            checked={form.overwrite}
            onChange={setField('overwrite')}
          />
          <div className="small muted" style={{ marginTop: 4 }}>
            勾选后重复提交将更新原记录, 仅提交的要素会被改写
          </div>
        </div>

        <div className="inline">
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '提交中...' : '提交气象记录'}
          </button>
          <span className="small muted">
            已填写 {filled.length} / {WEATHER_FACTORS.length} 个要素
          </span>
        </div>
      </div>
    </SectionCard>
  )
}
