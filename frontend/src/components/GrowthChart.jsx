import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// P5 y P95 son los umbrales de alerta del proyecto, por eso se destacan
const REFERENCE = [
  { key: 'p95', name: 'P95', color: '#b7791f', dash: '5 4', width: 1.5 },
  { key: 'p75', name: 'P75', color: '#9db8b4', width: 1 },
  { key: 'p50', name: 'P50 (mediana)', color: '#0e6b6b', width: 2.5 },
  { key: 'p25', name: 'P25', color: '#9db8b4', width: 1 },
  { key: 'p5', name: 'P5', color: '#b42318', dash: '5 4', width: 1.5 },
]

/**
 * reference: [{month, p5, p25, p50, p75, p95}]  (de la OMS)
 * points:    [{age, value}]                     (mediciones del niño)
 */
export default function GrowthChart({ title, unit, reference, points, maxMonths }) {
  const rows = reference.filter((r) => r.month <= maxMonths).map((r) => ({ ...r }))
  const childRows = points.filter((p) => p.age <= maxMonths).map((p) => ({ month: p.age, child: p.value }))
  const data = [...rows, ...childRows].sort((a, b) => a.month - b.month)

  const step = maxMonths <= 24 ? 3 : 6
  const ticks = Array.from({ length: Math.floor(maxMonths / step) + 1 }, (_, i) => i * step)

  return (
    <figure className="chart-card">
      <figcaption>{title}</figcaption>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
            <CartesianGrid stroke="#e3ecea" strokeDasharray="3 3" />
            <XAxis
              type="number" dataKey="month" domain={[0, maxMonths]} ticks={ticks}
              label={{ value: 'Edad (meses)', position: 'insideBottom', offset: -10, fill: '#5b727a', fontSize: 12 }}
              tick={{ fill: '#5b727a', fontSize: 12 }}
            />
            <YAxis
              domain={[(min) => Math.floor(min), (max) => Math.ceil(max)]}
              tick={{ fill: '#5b727a', fontSize: 12 }} width={42}
              label={{ value: unit, angle: -90, position: 'insideLeft', fill: '#5b727a', fontSize: 12 }}
            />
            <Tooltip
              labelFormatter={(m) => `Edad: ${Number(m).toFixed(1)} meses`}
              formatter={(v, name) => [`${v} ${unit}`, name]}
            />
            <Legend verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
            {REFERENCE.map((l) => (
              <Line
                key={l.key} dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={l.width}
                strokeDasharray={l.dash} dot={false} activeDot={false} connectNulls isAnimationActive={false}
              />
            ))}
            <Line
              dataKey="child" name="Niño" stroke="#17323a" strokeWidth={2.5} connectNulls isAnimationActive={false}
              dot={{ r: 5, fill: '#e0a526', stroke: '#17323a', strokeWidth: 2 }}
              activeDot={{ r: 7, fill: '#e0a526', stroke: '#17323a', strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
