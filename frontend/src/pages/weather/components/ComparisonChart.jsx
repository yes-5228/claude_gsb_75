import { useMemo, useState } from 'react'

/**
 * 同期气象要素与浓度的双序列对照图 (内联 SVG, 无第三方依赖)。
 * 两条序列量纲不同, 各自按自身 min/max 归一化到同一绘图层, 鼠标悬停显示真实值。
 */
export default function ComparisonChart({ series = [], weatherMeta, pollutantMeta }) {
  const [hover, setHover] = useState(null)

  const width = 920
  const height = 300
  const padding = { top: 24, right: 24, bottom: 46, left: 44 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const data = useMemo(() => {
    if (series.length < 2) return null
    const wx = series.map((item) => item.weather)
    const cx = series.map((item) => item.pollutant)
    const wMin = Math.min(...wx)
    const wMax = Math.max(...wx)
    const cMin = Math.min(...cx)
    const cMax = Math.max(...cx)
    const normalize = (value, min, max) =>
      max === min ? 0.5 : (value - min) / (max - min)

    const x = (index) => padding.left + (innerW * index) / (series.length - 1)
    const y = (norm) => padding.top + innerH * (1 - norm)

    const weatherPoints = series.map((item, index) => [x(index), y(normalize(item.weather, wMin, wMax))])
    const pollutantPoints = series.map((item, index) => [x(index), y(normalize(item.pollutant, cMin, cMax))])
    const toPath = (points) => points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')

    // 时间刻度 (最多 8 个)
    const tickEvery = Math.max(1, Math.ceil(series.length / 8))
    const ticks = series
      .map((item, index) => ({ ...item, x: x(index), index }))
      .filter((item) => item.index % tickEvery === 0 || item.index === series.length - 1)

    return { weatherPoints, pollutantPoints, toPath, ticks, x, wMin, wMax, cMin, cMax }
  }, [series, innerW, innerH])

  if (!series || series.length < 2) {
    return <div className="empty">同周期成对样本不足 2 个时刻, 暂无法绘制对照曲线</div>
  }

  const handleMove = (event) => {
    if (!data) return
    const rect = event.currentTarget.getBoundingClientRect()
    const scaleX = width / rect.width
    const px = (event.clientX - rect.left) * scaleX
    const ratio = (px - padding.left) / innerW
    const index = Math.round(ratio * (series.length - 1))
    if (index >= 0 && index < series.length) setHover(index)
  }

  const gridYs = [0, 0.25, 0.5, 0.75, 1]

  return (
    <div>
      <div className="inline" style={{ justifyContent: 'center', marginBottom: 8, gap: 20 }}>
        <span className="small">
          <span style={{ display: 'inline-block', width: 14, height: 3, background: '#0ea5e9', verticalAlign: 'middle', marginRight: 6 }} />
          {weatherMeta?.label} ({weatherMeta?.unit})
        </span>
        <span className="small">
          <span style={{ display: 'inline-block', width: 14, height: 3, background: '#f59e0b', verticalAlign: 'middle', marginRight: 6 }} />
          {pollutantMeta?.label} ({pollutantMeta?.unit})
        </span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        role="img"
        aria-label="气象与浓度对照曲线"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        {gridYs.map((ratio) => (
          <g key={ratio}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerH * ratio}
              y2={padding.top + innerH * ratio}
              stroke="#eef2f7"
            />
            <text x={padding.left - 8} y={padding.top + innerH * ratio + 4} textAnchor="end" fontSize="10" fill="#94a3b8">
              {Math.round((1 - ratio) * 100)}%
            </text>
          </g>
        ))}

        <path d={data.toPath(data.weatherPoints)} fill="none" stroke="#0ea5e9" strokeWidth="2" />
        <path d={data.toPath(data.pollutantPoints)} fill="none" stroke="#f59e0b" strokeWidth="2" />

        {data.weatherPoints.map(([x, y], index) => (
          <circle key={`w-${index}`} cx={x} cy={y} r={hover === index ? 4 : 2.2} fill="#0ea5e9" />
        ))}
        {data.pollutantPoints.map(([x, y], index) => (
          <circle key={`p-${index}`} cx={x} cy={y} r={hover === index ? 4 : 2.2} fill="#f59e0b" />
        ))}

        {data.ticks.map((tick) => (
          <text key={tick.index} x={tick.x} y={height - 18} textAnchor="middle" fontSize="10" fill="#64748b">
            {String(tick.measured_at).slice(5, 10)}
          </text>
        ))}
        {data.ticks.map((tick) => (
          <text key={`h-${tick.index}`} x={tick.x} y={height - 6} textAnchor="middle" fontSize="10" fill="#94a3b8">
            {String(tick.measured_at).slice(11, 16)}
          </text>
        ))}

        {hover !== null ? (
          <line
            x1={data.x(hover)}
            x2={data.x(hover)}
            y1={padding.top}
            y2={padding.top + innerH}
            stroke="#cbd5e1"
            strokeDasharray="3 3"
          />
        ) : null}
      </svg>
      {hover !== null && series[hover] ? (
        <div className="small" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          {String(series[hover].measured_at).replace('T', ' ').slice(0, 16)} ·{' '}
          <span style={{ color: '#0369a1' }}>
            {weatherMeta?.label} {series[hover].weather} {weatherMeta?.unit}
          </span>{' '}
          ·{' '}
          <span style={{ color: '#b45309' }}>
            {pollutantMeta?.label} {series[hover].pollutant} {pollutantMeta?.unit}
          </span>{' '}
          · {series[hover].sample_count} 个点位平均
        </div>
      ) : (
        <div className="small muted" style={{ textAlign: 'center' }}>
          两序列量纲不同, 纵轴为各自范围内的归一化位置 (0~100%)
        </div>
      )}
    </div>
  )
}
