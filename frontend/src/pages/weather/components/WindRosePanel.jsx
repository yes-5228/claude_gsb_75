import { WIND_SECTOR_COLORS } from '../../../constants/index.js'
import { formatNumber } from '../../../utils/format.js'

/** 8 方位 + 静风的平均浓度玫瑰图 (内联 SVG 极坐标柱)。 */
export default function WindRosePanel({ breakdown }) {
  const items = breakdown?.items ?? []
  const sectorItems = items.filter((item) => item.key !== 'calm')
  const calm = items.find((item) => item.key === 'calm')
  const total = breakdown?.total || 0

  const values = sectorItems.map((item) => item.avg_pollutant).filter((v) => v !== null)
  const max = values.length ? Math.max(...values) : 0
  const size = 260
  const center = size / 2
  const maxRadius = 92
  const barWidth = (Math.PI * 2 * maxRadius) / sectorItems.length - 6

  // 8 个扇区从正北开始顺时针排列
  const bars = sectorItems.map((item, index) => {
    const angle = (Math.PI * 2 * index) / sectorItems.length - Math.PI / 2
    const radius = item.avg_pollutant !== null && max > 0
      ? Math.max(6, (item.avg_pollutant / max) * maxRadius)
      : 0
    return { ...item, angle, radius, color: WIND_SECTOR_COLORS[item.key] || '#94a3b8' }
  })

  return (
    <div className="grid-2" style={{ gridTemplateColumns: 'minmax(260px, 300px) 1fr', alignItems: 'center' }}>
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" role="img" aria-label="风向玫瑰图">
        {[0.25, 0.5, 0.75, 1].map((ratio) => (
          <circle
            key={ratio}
            cx={center}
            cy={center}
            r={maxRadius * ratio}
            fill="none"
            stroke="#eef2f7"
          />
        ))}
        {bars.map((bar) => (
          <g key={bar.key}>
            <rect
              x={center - barWidth / 2}
              y={center - bar.radius}
              width={barWidth}
              height={bar.radius}
              rx={2}
              fill={bar.color}
              opacity={bar.count ? 0.85 : 0.25}
              transform={`rotate(${(bar.angle * 180) / Math.PI + 90} ${center} ${center})`}
            />
            <text
              x={center + Math.sin((bars.indexOf(bar) * Math.PI * 2) / bars.length) * (maxRadius + 16)}
              y={center - Math.cos((bars.indexOf(bar) * Math.PI * 2) / bars.length) * (maxRadius + 16) + 4}
              textAnchor="middle"
              fontSize="11"
              fill="#64748b"
            >
              {bar.key}
            </text>
          </g>
        ))}
        <circle cx={center} cy={center} r="3" fill="#64748b" />
      </svg>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>方位</th>
              <th className="text-right">样本数</th>
              <th className="text-right">占比</th>
              <th className="text-right">平均浓度</th>
            </tr>
          </thead>
          <tbody>
            {sectorItems.map((item) => (
              <tr key={item.key}>
                <td>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 9,
                      height: 9,
                      borderRadius: 2,
                      background: WIND_SECTOR_COLORS[item.key],
                      marginRight: 6
                    }}
                  />
                  {item.label.replace(/ [A-Z]+$/, '')} {item.key}
                </td>
                <td className="text-right">{item.count}</td>
                <td className="text-right">{total ? `${Math.round((item.count / total) * 100)}%` : '-'}</td>
                <td className="text-right strong">{formatNumber(item.avg_pollutant)}</td>
              </tr>
            ))}
            {calm ? (
              <tr>
                <td>{calm.label} (风速≤0.2m/s)</td>
                <td className="text-right">{calm.count}</td>
                <td className="text-right">{total ? `${Math.round((calm.count / total) * 100)}%` : '-'}</td>
                <td className="text-right strong">{formatNumber(calm.avg_pollutant)}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
