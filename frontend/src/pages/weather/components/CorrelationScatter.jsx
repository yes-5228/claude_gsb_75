import { useMemo, useState } from 'react'

/**
 * 配对样本散点图 (内联 SVG): 横轴=气象要素, 纵轴=浓度。
 * 多站点时各轴按全部样本线性归一化, 直观呈现同期共变方向。
 */
export default function CorrelationScatter({ points = [], weatherMeta, pollutantMeta }) {
  const [hover, setHover] = useState(null)
  const width = 460
  const height = 300
  const padding = { top: 18, right: 18, bottom: 44, left: 52 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const layout = useMemo(() => {
    if (points.length === 0) return null
    const wx = points.map((p) => p.weather)
    const cx = points.map((p) => p.pollutant)
    const wMin = Math.min(...wx)
    const wMax = Math.max(...wx)
    const cMin = Math.min(...cx)
    const cMax = Math.max(...cx)
    const norm = (v, min, max) => (max === min ? 0.5 : (v - min) / (max - min))
    const x = (w) => padding.left + norm(w, wMin, wMax) * innerW
    const y = (c) => padding.top + (1 - norm(c, cMin, cMax)) * innerH
    return { x, y, wMin, wMax, cMin, cMax }
  }, [points, innerW, innerH])

  if (!layout) return <div className="empty">暂无成对样本</div>

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="气象-浓度散点图"
           onMouseLeave={() => setHover(null)}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <g key={ratio}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerH * ratio}
              y2={padding.top + innerH * ratio}
              stroke="#f1f5f9"
            />
            <line
              y1={padding.top}
              y2={padding.top + innerH}
              x1={padding.left + innerW * ratio}
              x2={padding.left + innerW * ratio}
              stroke="#f1f5f9"
            />
          </g>
        ))}
        {points.map((point, index) => (
          <circle
            key={index}
            cx={layout.x(point.weather)}
            cy={layout.y(point.pollutant)}
            r={hover === index ? 5 : 3.2}
            fill={hover === index ? '#dc2626' : 'rgba(37, 99, 235, 0.55)'}
            stroke="#2563eb"
            strokeWidth="0.5"
            onMouseEnter={() => setHover(index)}
          />
        ))}
        <text x={padding.left + innerW / 2} y={height - 8} textAnchor="middle" fontSize="11" fill="#475569">
          {weatherMeta?.label} ({weatherMeta?.unit})
        </text>
        <text
          x={14}
          y={padding.top + innerH / 2}
          textAnchor="middle"
          fontSize="11"
          fill="#475569"
          transform={`rotate(-90 14 ${padding.top + innerH / 2})`}
        >
          {pollutantMeta?.label} ({pollutantMeta?.unit})
        </text>
      </svg>
      {hover !== null && points[hover] ? (
        <div className="small" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          {String(points[hover].measured_at).replace('T', ' ').slice(0, 16)} · 站点 #{points[hover].station_id}
          : {weatherMeta?.label} {points[hover].weather} / {pollutantMeta?.label} {points[hover].pollutant}
        </div>
      ) : null}
    </div>
  )
}
