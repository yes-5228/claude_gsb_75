import { useCallback, useEffect, useMemo, useState } from 'react'
import { createObservation, previewWeather } from '../../../api/weather.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import { Checkbox, Field, Input, Select } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { useWeatherOptions } from '../../../hooks/useWeatherOptions.js'
import { formatNumber, toDateTimeInput } from '../../../utils/format.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

const DATA_SOURCES = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]

// 录入区要素的展示顺序
const FACTOR_ORDER = ['temperature', 'humidity', 'wind_speed', 'wind_direction', 'pressure', 'precipitation']

export default function WeatherEntryForm({ onSubmitted }) {
  const toast = useToast()
  const { data: options, loading, error } = useWeatherOptions()

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
  const [busy, setBusy] = useState(null)
  const [preview, setPreview] = useState(null)

  const factors = useMemo(() => {
    const all = options?.factors ?? []
    return FACTOR_ORDER.map((code) => all.find((item) => item.code === code)).filter(Boolean)
  }, [options])

  useEffect(() => {
    if (!form.station_id && options?.stations?.length) {
      setForm((prev) => ({ ...prev, station_id: String(options.stations[0].id) }))
    }
  }, [options, form.station_id])

  const filled = useMemo(
    () =>
      Object.entries(values).filter(([, raw]) => raw !== '' && raw !== null && raw !== undefined),
    [values]
  )

  const setField = (key) => (event) => {
    const value = key === 'overwrite' ? event.target.checked : event.target.value
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const setValue = (factor) => (event) => {
    setValues((prev) => ({ ...prev, [factor]: event.target.value }))
    setErrors((prev) => ({ ...prev, [factor]: undefined }))
  }

  const buildPayload = useCallback(() => {
    const payload = {
      station_id: Number(form.station_id),
      measured_at: form.measured_at,
      period: form.period,
      data_source: form.data_source,
      recorder: form.recorder || null,
      remark: form.remark || null,
      overwrite: form.overwrite
    }
    filled.forEach(([factor, raw]) => {
      payload[factor] = Number(raw)
    })
    return payload
  }, [form, filled])

  const validate = () => {
    const next = {}
    if (!form.station_id) next.station_id = '请选择监测点'
    if (!form.measured_at) next.measured_at = '请选择观测时间'
    if (filled.length === 0) next.factors = '至少填写一个气象要素'
    filled.forEach(([factor, raw]) => {
      const meta = factors.find((item) => item.code === factor)
      const number = Number(raw)
      if (Number.isNaN(number)) next[factor] = '必须是数字'
      else if (number < meta.min || number > meta.max)
        next[factor] = `应在 ${formatNumber(meta.min)} ~ ${formatNumber(meta.max)} ${meta.unit}`
    })
    setErrors(next)
    if (Object.keys(next).length) {
      setMessage('请先修正表单中标红的问题')
      return false
    }
    setMessage(null)
    return true
  }

  const runPreview = async () => {
    if (!validate()) return
    setBusy('preview')
    try {
      const result = await previewWeather(buildPayload())
      setPreview(result)
      toast.success(`校验完成: 已填写 ${result.summary.factor_count} 个气象要素`)
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
      toast.error(err.message)
    } finally {
      setBusy(null)
    }
  }

  const submit = async () => {
    if (!validate()) return
    setBusy('submit')
    try {
      const result = await createObservation(buildPayload())
      setValues({})
      setPreview(null)
      onSubmitted?.(result)
      toast.success(result.action === 'updated' ? '气象记录已更新' : '气象观测录入成功')
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
      toast.error(err.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <SectionCard
      title="气象要素录入"
      hint="选择监测点与观测时刻, 一次录入温度、湿度、风等要素"
      actions={<Tag tone="primary">{form.period === 'hourly' ? '小时均值' : '日均值'}</Tag>}
    >
      <div className="stack">
        {error ? <Alert tone="error">{error.message}</Alert> : null}
        {message ? <Alert tone="error">{message}</Alert> : null}
        {loading ? (
          <Alert tone="info">正在加载监测点与气象要素...</Alert>
        ) : (
          <>
            <div className="form-grid">
              <Field label="监测点" required error={errors.station_id}>
                <Select
                  value={form.station_id}
                  onChange={setField('station_id')}
                  invalid={Boolean(errors.station_id)}
                  placeholder="请选择监测点"
                  options={(options?.stations ?? []).map((item) => ({
                    value: String(item.id),
                    label: `${item.code} ${item.name} (${item.area})`
                  }))}
                />
              </Field>
              <Field label="观测时间" required error={errors.measured_at} hint="与浓度数据保持同一时刻以便对照">
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
                <h3>气象要素</h3>
                <span className="hint">留空的要素不会写入, 风向按正北顺时针角度填写</span>
              </div>
              <div className="card-body">
                {errors.factors ? <Alert tone="error">{errors.factors}</Alert> : null}
                <div className="form-grid">
                  {factors.map((factor) => (
                    <Field
                      key={factor.code}
                      label={`${factor.label} (${factor.unit})`}
                      error={errors[factor.code]}
                      hint={factor.description}
                    >
                      <Input
                        type="number"
                        step="0.1"
                        value={values[factor.code] ?? ''}
                        onChange={setValue(factor.code)}
                        invalid={Boolean(errors[factor.code])}
                        placeholder={`${factor.min} ~ ${factor.max}`}
                      />
                    </Field>
                  ))}
                </div>
                {preview ? (
                  <div className="small muted inline" style={{ marginTop: 10, rowGap: 6 }}>
                    <span>最近一次校验:</span>
                    {preview.factors.map((item) => (
                      <Tag key={item.factor} tone="success">
                        {item.factor_label} {formatNumber(item.value)}
                      </Tag>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <div>
              <Checkbox
                label="覆盖同一时刻已有气象记录"
                checked={form.overwrite}
                onChange={setField('overwrite')}
              />
              <div className="small muted" style={{ marginTop: 4 }}>
                勾选后重复提交将更新原观测记录
              </div>
            </div>

            <div className="inline">
              <button type="button" className="btn" onClick={runPreview} disabled={busy !== null}>
                {busy === 'preview' ? '校验中...' : '校验预览'}
              </button>
              <button type="button" className="btn btn-primary" onClick={submit} disabled={busy !== null}>
                {busy === 'submit' ? '提交中...' : '提交录入'}
              </button>
              <span className="small muted">
                已填写 {filled.length} / {factors.length} 个要素
              </span>
            </div>
          </>
        )}
      </div>
    </SectionCard>
  )
}
