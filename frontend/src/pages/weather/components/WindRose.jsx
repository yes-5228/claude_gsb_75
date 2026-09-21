/**
 * 八方位风向玫瑰图: 扇区长度表示该方位的平均污染浓度,
 * 扇区透明度叠加风向出现频次, 静风单独标注。
 */
const SIZE = 260
const CENTER = SIZE / 2
const MAX_RADIUS = SIZE / 2 - 54

function polarPoint(angle, radius) {
  const rad = ((angle - 90) * Math.PI) / 180
  return { x: CENTER + radius * Math.cos(rad), y: CENTER + radius * Math.sin(rad) }
}

function sectorPath(angle, radius, halfWidth) {
  const inner = 6
  const p1 = polarPoint(angle - halfWidth, inner)
  const p2 = polarPoint(angle - halfWidth, radius)
  const p3 = polarPoint(angle + halfWidth, radius)
  const p4 = polarPoint(angle + halfWidth, inner)
  return `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y} A ${radius} ${radius} 0 0 1 ${p3.x} ${p3.y} L ${p4.x} ${p4.y} A ${inner} ${inner} 0 0 0 ${p1.x} ${p1.y} Z`
}

export default function WindRose({ result }) {
  const sectors = result?.sectors ?? []
  if (!sectors.length || result.sample_count === 0) {
    return <div className="empty">所选范围内暂无可对照的风向数据</div>
  }

  const maxConcentration = Math.max(
    ...sectors.map((item) => item.avg_concentration || 0),
    1
  )
  const maxRatio = Math.max(...sectors.map((item) => item.ratio || 0), 0.0001)
  const angles = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 }

  return (
    <div className="windrose-block">
      <svg width={SIZE} height={SIZE} role="img" aria-label="风向-浓度玫瑰图">
        {[0.33, 0.66, 1].map((ring) => (
          <circle key={ring} cx={CENTER} cy={CENTER} r={MAX_RADIUS * ring} className="rose-grid" />
        ))}
        {sectors.map((item) => {
          const concentration = item.avg_concentration || 0
          const radius = Math.max((concentration / maxConcentration) * MAX_RADIUS, 8)
          const opacity = 0.35 + 0.65 * (item.ratio / maxRatio)
          const label = polarPoint(angles[item.code], MAX_RADIUS + 20)
          return (
            <g key={item.code}>
              <path
                d={sectorPath(angles[item.code], radius, 20)}
                className="rose-sector"
                opacity={opacity.toFixed(2)}
              >
                <title>
                  {`${item.label}风: 平均浓度 ${concentration || '-'}，样本 ${item.count} 条 (${(item.ratio * 100).toFixed(0)}%)`}
                </title>
              </path>
              <text x={label.x} y={label.y + 4} textAnchor="middle" className="rose-label">
                {item.label}
              </text>
            </g>
          )
        })}
        <circle cx={CENTER} cy={CENTER} r="5" className="rose-center" />
      </svg>
      <div className="windrose-table">
        <table className="data-table compact">
          <thead>
            <tr>
              <th>方位</th>
              <th className="text-right">样本</th>
              <th className="text-right">占比</th>
              <th className="text-right">平均浓度</th>
              <th className="text-right">最大浓度</th>
            </tr>
          </thead>
          <tbody>
            {sectors.map((item) => (
              <tr key={item.code}>
                <td>{item.label}</td>
                <td className="text-right">{item.count}</td>
                <td className="text-right">{(item.ratio * 100).toFixed(0)}%</td>
                <td className="text-right strong">{item.avg_concentration ?? '-'}</td>
                <td className="text-right">{item.max_concentration ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
