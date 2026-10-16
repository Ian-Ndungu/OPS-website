import { Table } from './ui'

export function TeamLogo({ team, size = 'h-10 w-10' }) {
  return team.logo_url
    ? <img src={team.logo_url} alt="" className={`${size} rounded-full object-cover`} />
    : <div className={`${size} flex shrink-0 items-center justify-center rounded-full bg-ops-raised font-display font-bold text-white`}>{team.team?.[0]}</div>
}

const STEP = { 1: 'h-32 bg-ops-accent text-ops-on-accent', 2: 'h-24 bg-ops-raised text-white', 3: 'h-16 bg-ops-raised/70 text-slate-300' }

/** Stepped podium: the step height is the rank, so the order reads without colour. */
export function Podium({ top }) {
  if (!top?.length) return null
  const order = [top[1], top[0], top[2]].filter(Boolean)
  return (
    <ol className="grid grid-cols-3 items-end gap-2 sm:gap-3" aria-label="Top three teams">
      {order.map((t) => (
        <li key={t.team_id} className="flex min-w-0 flex-col items-center text-center">
          <TeamLogo team={t} size={t.rank === 1 ? 'h-14 w-14' : 'h-11 w-11'} />
          <div className="mt-2 w-full text-balance break-words font-display text-base font-bold leading-tight text-white">{t.team}</div>
          <div className="num mb-2 mt-1 text-sm text-ops-mute">{t.total_points} pts{t.kills ? ` · ${t.kills} kills` : ''}</div>
          <div className={`flex w-full items-start justify-center rounded-t-3xl pt-3 font-display text-4xl font-extrabold ${STEP[t.rank]}`}>{t.rank}</div>
        </li>
      ))}
    </ol>
  )
}

export function Standings({ rows, mode }) {
  const br = mode === 'battle_royale'
  return (
    <Table head={br ? ['Rank', 'Team', 'Matches', 'Wins', 'Placement pts', 'Kill pts', 'Kills', 'Total'] : ['Rank', 'Team', 'Played', 'Wins', 'Score difference']}>
      {rows.map((r) => (
        <tr key={r.team_id}>
          <td className="num px-4 py-3 font-display text-xl font-bold">{r.rank}</td>
          <td className="px-4 py-3"><div className="flex items-center gap-3"><TeamLogo team={r} size="h-8 w-8" /><span className="font-medium text-white">{r.team}</span></div></td>
          <td className="num px-4 py-3">{r.matches}</td>
          <td className="num px-4 py-3">{r.wins}</td>
          {br ? (<>
            <td className="num px-4 py-3">{r.placement_points}</td><td className="num px-4 py-3">{r.kill_points}</td>
            <td className="num px-4 py-3">{r.kills}</td><td className="num px-4 py-3 font-display text-lg font-bold text-ops-link">{r.total_points}</td>
          </>) : <td className="num px-4 py-3">{r.score_for - r.score_against > 0 ? '+' : ''}{r.score_for - r.score_against}</td>}
        </tr>
      ))}
    </Table>
  )
}
