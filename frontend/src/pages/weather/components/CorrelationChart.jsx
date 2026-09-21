import { useEffect, useRef, useState } from 'react'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

/**
 * 轻量 SVG 双轴时序折线图: 左轴为污染因子浓度, 右轴为气象要素。
 * 不引入第三方图表库, 宽度随容器自适应。
 */
const HEIGHT = 260
const PAD = { top: 18, right: 52, bottom: 38, left: 56 }

function useWidth() {
  const ref = useRef(null)
  const [width, setWidth] = useState(640)
  useEffect(() => {
    if (!ref.current) return undefined
    const element = ref.current
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width
      if (next) setWidth(Math.max(320, next))
    })
    observer.observe(element)
    setWidth(Math.max(320, element.clientWidth || 640))
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

function scale(value, min, max, range) {
  if (max === min) return range / 2
  return ((value - min) / (max - min)) * range
}

function niceBounds(values) {
  const numbers = values.filter((item) => item !== null && item !== undefined && !Number.isNaN(item))
  if (!numbers.length) return { min: 0, max: 1 }
  let min = Math.min(...numbers)
  let max = Math.max(...numbers)
  if (min === max) {
    min -= 1
    max += 1
  }
  const padding = (max - min) * 0.12
  return { min: min - padding, max: max + padding }
}

export default function CorrelationChart({ series, factor, factorLabel, factorUnit, pollutantLabel, pollutantUnit }) {
  const [containerRef, width] = useWidth()
  if (!series?.length) {
    return <div className="empty">所选范围内暂无可对照的同期数据</div>
  }

  const plotW = width - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const concentrationBounds = niceBounds(series.map((item) => item.pollutant_value))
  const factorBounds = niceBounds(series.map((item) => item[factor]))

  const xAt = (index) => PAD.left + (index / Math.max(series.length - 1, 1)) * plotW
  const yConcentration = (value) =>
    PAD.top + plotH - scale(value, concentrationBounds.min, concentrationBounds.max, plotH)
  const yFactor = (value) =>
    PAD.top + plotH - scale(value, factorBounds.min, factorBounds.max, plotH)

  const concentrationPath = series
    .map((item, index) => `${index === 0 ? 'M' : 'L'} ${xAt(index).toFixed(1)} ${yConcentration(item.pollutant_value).toFixed(1)}`)
    .join(' ')
  const factorPoints = series
    .map((item, index) =>
      item[factor] === null || item[factor] === undefined
        ? null
        : { x: xAt(index), y: yFactor(item[factor]) }
    )
    .filter(Boolean)
  const factorPath = factorPoints
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(' ')

  const ticks = [0, 0.25, 0.5, 0.75, 1]
  const concentrationTicks = ticks.map((t) => concentrationBounds.max - t * (concentrationBounds.max - concentrationBounds.min))
  const factorTicks = ticks.map((t) => factorBounds.max - t * (factorBounds.max - factorBounds.min))
  const labelEvery = Math.max(1, Math.ceil(series.length / 8))

  return (
    <div ref={containerRef} className="corr-chart">
      <svg width={width} height={HEIGHT} role="img" aria-label="气象要素与浓度对照时序图">
        {ticks.map((t, index) => {
          const y = PAD.top + t * plotH
          return (
            <g key={t}>
              <line x1={PAD.left} y1={y} x2={width - PAD.right} y2={y} className="chart-grid" />
              <text x={PAD.left - 8} y={y + 4} textAnchor="end" className="chart-axis-text concentration">
                {formatNumber(concentrationTicks[index], 1)}
              </text>
              <text x={width - PAD.right + 8} y={y + 4} textAnchor="start" className="chart-axis-text factor">
                {formatNumber(factorTicks[index], 1)}
              </text>
            </g>
          )
        })}
        <path d={concentrationPath} className="chart-line concentration" />
        {factorPath ? <path d={factorPath} className="chart-line factor" /> : null}
        {series.map((item, index) => (
          <circle
            key={`c-${index}`}
            cx={xAt(index)}
            cy={yConcentration(item.pollutant_value)}
            r="2.4"
            className="chart-dot concentration"
          >
            <title>
              {`${formatDateTime(item.measured_at)} ${item.station_name}\n` +
                `${pollutantLabel}: ${item.pollutant_value} ${pollutantUnit}\n` +
                `${factorLabel}: ${item[factor] ?? '-'} ${factorUnit}`}
            </title>
          </circle>
        ))}
        {factorPoints.map((point, index) => (
          <circle key={`f-${index}`} cx={point.x} cy={point.y} r="2.2" className="chart-dot factor" />
        ))}
        {series.map((item, index) =>
          index % labelEvery === 0 ? (
            <text key={`x-${index}`} x={xAt(index)} y={HEIGHT - 12} textAnchor="middle" className="chart-axis-text x">
              {formatDateTime(item.measured_at).slice(5, 10)}
            </text>
          ) : null
        )}
      </svg>
      <div className="chart-legend">
        <span className="legend-item">
          <i className="legend-dot concentration" />
          {pollutantLabel}浓度 ({pollutantUnit}) · 左轴
        </span>
        <span className="legend-item">
          <i className="legend-dot factor" />
          {factorLabel} ({factorUnit}) · 右轴
        </span>
      </div>
    </div>
  )
}
