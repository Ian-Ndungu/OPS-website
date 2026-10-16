import { Link } from 'react-router-dom'
import rulesPoster from '../assets/clan-rules.webp'

const rules = [
  ['Loyalty to OPS', ['Once you join OPS, you represent OPS.', 'No clan hopping or dual clans.']],
  ['Respect is mandatory', ['Respect all OPS members and leaders.', 'No insults, toxicity, or disrespect in chat or games.']],
  ['Activity', ['Be active in games and clan chat.', '7 days inactive without notice = removal.', 'Inform leaders if you’ll be offline.']],
  ['Clan Wars', ['Clan Wars participation is mandatory.', 'Give your best—OPS wins together.']],
  ['Teamwork first', ['No selfish play.', 'Support teammates in MP, BR, and Ranked.']],
  ['Fair play only', ['No hacks, cheats, or exploits.', 'Instant kick if caught cheating.']],
  ['Obey leadership', ['Follow instructions from OPS leaders and moderators.', 'Arguing with leadership will not be tolerated.']],
  ['Promotions & discipline', ['Promotions are earned through loyalty, performance, and discipline.', 'Warning → Final Warning → Kick.']],
]

export default function ClanRules() {
  return <div className="space-y-10">
    <header className="max-w-2xl space-y-4">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-ops-link">The OPSKe standard</p>
      <h1 className="font-display text-4xl font-extrabold text-white sm:text-6xl">Clan rules</h1>
      <p className="text-lg leading-relaxed text-ops-mute">Read these rules before applying. Every member represents the clan, in game and in chat.</p>
      <p className="font-display text-2xl font-bold text-ops-link">One Team. One Mission. OPS.</p>
    </header>
    <section aria-label="The eight clan rules">
      <ol className="grid gap-4 md:grid-cols-2">
        {rules.map(([title, points], i) => <li key={title} className="card flex items-start gap-4">
          <span className="num flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ops-accent font-display text-lg font-extrabold text-ops-on-accent" aria-hidden="true">{i + 1}</span>
          <div><h2 className="font-display text-xl font-bold text-white">{title}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-4 text-sm leading-relaxed text-ops-mute">{points.map((point) => <li key={point}>{point}</li>)}</ul>
          </div>
        </li>)}
      </ol>
    </section>
    <section className="card space-y-5" aria-labelledby="rules-poster-heading">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="rules-poster-heading" className="font-display text-2xl font-bold text-white">Official clan rules poster</h2><a className="btn-ghost" href={rulesPoster} target="_blank" rel="noopener noreferrer">Open full-size poster <span aria-hidden="true">↗</span></a></div>
      <img src={rulesPoster} width="1024" height="1536" loading="lazy" decoding="async" alt="OPS clan rules poster. The complete rules are listed in text above." className="mx-auto h-auto w-full max-w-2xl rounded-2xl" />
    </section>
    <section className="card flex flex-wrap items-center justify-between gap-5">
      <div><h2 className="font-display text-2xl font-bold text-white">Ready to represent OPSKe?</h2><p className="mt-2 text-ops-mute">Send your profile screenshot and join request. No website account needed.</p></div>
      <Link className="btn-primary" to="/join-clan">Apply to join</Link>
    </section>
  </div>
}
