/**
 * The Mythic Circle as a ring of seats. One segment per member seat.
 * `filled` is in seats (fractional): 3.5 means three full seats and a half.
 * `open` marks that many seats at the end as unclaimed (dashed). Aggregate only: it never
 * shows who paid what.
 */
export default function SeatRing({ seats, filled = 0, open = 0, size = 260, children, label }) {
  const r = 84, w = 15, cx = 100, cy = 100
  const circ = 2 * Math.PI * r
  const slot = circ / seats
  const gap = 9
  const len = Math.max(4, slot - gap - w) // round caps add w to each segment
  const startDeg = (i) => -90 + (i * 360) / seats + ((gap + w) / 2 / circ) * 360
  const openFrom = seats - Math.min(open, seats)
  return (
    <div className="relative mx-auto" style={{ width: size, height: size }} role="img"
      aria-label={label || `${seats} seat circle, ${Math.min(open, seats)} seats open`}>
      <svg viewBox="0 0 200 200" className="h-full w-full">
        {Array.from({ length: seats }, (_, i) => {
          const f = Math.max(0, Math.min(1, filled - i))
          const isOpen = i >= openFrom
          const common = { cx, cy, r, fill: 'none', strokeWidth: w, strokeLinecap: 'round', transform: `rotate(${startDeg(i)} ${cx} ${cy})` }
          return (
            <g key={i}>
              <circle {...common} stroke="rgb(var(--line))" strokeDasharray={isOpen ? `0.1 ${slot / 3.2}` : `${len} ${circ}`}
                style={isOpen ? { stroke: 'rgb(var(--mute))', strokeWidth: 3.5, opacity: 0.7 } : undefined} />
              {f > 0 && !isOpen && (
                <circle {...common} className="seat-fill" stroke="rgb(var(--accent))"
                  strokeDasharray={`${Math.max(0.01, len * f)} ${circ}`} style={{ animationDelay: `${i * 70}ms` }} />
              )}
            </g>
          )
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center px-12 text-center">{children}</div>
    </div>
  )
}
