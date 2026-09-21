export const NAV_ITEMS = [
  { to: '/overview', label: '运行概览', icon: '📊', title: '运行概览', subtitle: '监测点规模、数据量与超标待办一览' },
  { to: '/stations', label: '监测点台账', icon: '📍', title: '监测点台账', subtitle: '维护监测点档案、点位信息与运行状态' },
  { to: '/measurements', label: '监测数据录入', icon: '✍️', title: '监测数据录入', subtitle: '按“监测点 + 时刻”成组录入各因子浓度' },
  { to: '/weather', label: '气象与关联分析', icon: '🌦️', title: '气象要素记录与关联分析', subtitle: '录入温湿度/风/气压/降水, 与同期浓度对照并导出' },
  { to: '/exceedances', label: '超标记录标注', icon: '⚠️', title: '超标记录标注', subtitle: '复核超标记录, 标注确认或忽略原因' },
  { to: '/query', label: '数据查询', icon: '🔍', title: '数据查询', subtitle: '多条件检索、聚合统计与结果导出' }
]

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

export const STATION_STATUS_TONE = { active: 'success', maintenance: 'warning', offline: 'neutral' }
export const EXCEEDANCE_STATUS_TONE = { pending: 'warning', confirmed: 'danger', ignored: 'neutral' }
export const EXCEEDANCE_LEVEL_TONE = { light: 'info', moderate: 'warning', severe: 'danger' }
export const DATA_SOURCE_TONE = { manual: 'primary', device: 'info', import: 'neutral' }

export const EXCEEDANCE_LEVEL_LABELS = { light: '轻度超标', moderate: '中度超标', severe: '重度超标' }
export const EXCEEDANCE_STATUS_LABELS = { pending: '待标注', confirmed: '已确认', ignored: '已忽略' }

export const POLLUTANT_CODE_LABELS = {
  PM25: 'PM2.5',
  PM10: 'PM10',
  SO2: 'SO₂',
  NO2: 'NO₂',
  CO: 'CO',
  O3: 'O₃'
}

// 气象要素元数据, 与后端 domain/weather.py 保持一致
export const WEATHER_FACTORS = [
  { code: 'temperature', label: '温度', unit: '℃', min: -60, max: 60, precision: 1 },
  { code: 'humidity', label: '相对湿度', unit: '%', min: 0, max: 100, precision: 1 },
  { code: 'wind_speed', label: '风速', unit: 'm/s', min: 0, max: 75, precision: 1 },
  { code: 'wind_direction', label: '风向角度', unit: '°', min: 0, max: 360, precision: 0 },
  { code: 'pressure', label: '气压', unit: 'hPa', min: 300, max: 1100, precision: 1 },
  { code: 'precipitation', label: '降水量', unit: 'mm', min: 0, max: 1000, precision: 1 }
]

export const WEATHER_FACTOR_LABELS = Object.fromEntries(
  WEATHER_FACTORS.map((item) => [item.code, item.label])
)

// 风向角度 -> 十六方位中文简称, 供录入表单即时提示
export function windDirectionLabel(angle) {
  if (angle === '' || angle === null || angle === undefined) return ''
  const value = Number(angle)
  if (Number.isNaN(value) || value < 0 || value > 360) return ''
  const dirs = ['北', '北东北', '东北', '东东北', '东', '东东南', '东南', '南东南',
                '南', '南西南', '西南', '西西南', '西', '西西北', '西北', '北西北']
  return dirs[Math.round((value % 360) / 22.5) % 16]
}

export const REFRESH_HINT = '数据来自 Flask 后端 /api 接口'
