import { Link } from 'react-router-dom'
import { api, fmtDate } from '../lib/api'
import { Empty, ErrorBox, Spinner, useAsync } from './ui'

function SectionHeading({ eyebrow, title, children }) {
  return <div className="max-w-2xl space-y-3">
    <p className="text-xs font-bold uppercase tracking-[0.18em] text-ops-link">{eyebrow}</p>
    <h2 className="font-display text-3xl font-extrabold text-white sm:text-4xl">{title}</h2>
    {children && <p className="leading-relaxed text-ops-mute">{children}</p>}
  </div>
}

function PostList({ data, empty, label }) {
  if (data.loading) return <Spinner />
  if (data.error) return <ErrorBox message={data.error} />
  if (!data.data?.length) return <Empty>{empty}</Empty>
  return <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label={label}>
    {data.data.map((post) => <li key={post.id} className="min-w-0">
      <Link to={`/announcements/${post.slug}`} className="group flex h-full flex-col overflow-hidden rounded-3xl bg-ops-card ring-1 ring-ops-line/50 transition-colors hover:bg-ops-raised">
        {post.image && <img src={post.image} alt="" loading="lazy" className="h-48 w-full bg-ops-raised object-contain" />}
        <div className="flex flex-1 flex-col items-start gap-3 p-5 sm:p-6">
          <span className="badge tone-info">{post.category}</span>
          <h3 className="font-display text-xl font-bold text-white">{post.title}</h3>
          <p className="text-sm leading-relaxed text-ops-mute">{post.summary}</p>
          <p className="text-xs text-ops-mute">Posted {fmtDate(post.published_at)}</p>
          <span className="mt-auto pt-2 text-sm font-semibold text-ops-link">Read update <span aria-hidden="true">→</span></span>
        </div>
      </Link>
    </li>)}
  </ul>
}

export function HomeActivity() {
  const scrims = useAsync(() => api.get('/api/announcements?category=Scrims&limit=3'))
  const highlights = useAsync(async () => {
    const groups = await Promise.all(['Clan News', 'Tournament Updates'].map((category) => api.get(`/api/announcements?category=${encodeURIComponent(category)}&limit=3`)))
    return groups.flat().sort((a, b) => new Date(b.published_at) - new Date(a.published_at)).slice(0, 3)
  })
  return <>
    <section className="space-y-6" aria-label="Scrims and registration">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeading eyebrow="Get in the game" title="Scrims & sign-ups">Find scrim announcements and registration details. Open each update for the event date, squad instructions, and current availability.</SectionHeading>
        <Link className="btn-ghost" to="/announcements?category=Scrims">All scrim updates</Link>
      </div>
      <PostList data={scrims} label="Latest scrim announcements" empty="No scrims announced yet. Check back here for the next registration update." />
    </section>
    <section className="space-y-6" aria-label="Clan highlights">
      <SectionHeading eyebrow="From the squad" title="Clan highlights">Tournament updates, squad stories, and moments shared by OPSKe admins.</SectionHeading>
      <PostList data={highlights} label="Latest clan highlights" empty="The next chapter is still being written. Clan news and tournament highlights will appear here when published." />
    </section>
  </>
}

export function HomeCommunity() {
  return <>
    <section className="grid gap-8 rounded-[32px] bg-ops-accent p-6 text-ops-on-accent sm:p-10 lg:grid-cols-[1.2fr_1fr] lg:items-center" aria-labelledby="join-clan-heading">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em]">Find your squad</p>
        <h2 id="join-clan-heading" className="mt-3 font-display text-3xl font-extrabold sm:text-5xl">Make your next move with OPSKe.</h2>
        <p className="mt-4 max-w-[54ch] leading-relaxed">Ready to join the clan? Tell us about your game, your experience, and why you want to be part of the team. You can apply without creating a website account.</p>
        <Link to="/join-clan" className="btn-ghost mt-6 !bg-ops-bg !text-white">Apply to join OPSKe <span aria-hidden="true">→</span></Link>
      </div>
      <ol className="space-y-4 rounded-3xl bg-black/10 p-5 sm:p-6">
        {[
          ['Update your name', 'Add the clan tag to your in-game profile name.'],
          ['Show your profile', 'Upload a clear screenshot showing your updated name and player ID.'],
          ['Send your request', 'Add your contact details and join message. An admin will review your application.'],
        ].map(([title, detail], i) => <li key={title} className="flex items-start gap-3"><span className="num flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ops-bg font-bold text-white">{i + 1}</span><div><h3 className="font-semibold">{title}</h3><p className="mt-1 text-sm leading-relaxed">{detail}</p></div></li>)}
      </ol>
    </section>
    <section className="card space-y-5" aria-labelledby="home-rules-heading">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-ops-link">One Team. One Mission. OPS.</p>
      <div className="flex flex-wrap items-end justify-between gap-4"><div><h2 id="home-rules-heading" className="font-display text-3xl font-extrabold text-white">Represent the clan. Respect the squad.</h2><p className="mt-3 max-w-2xl leading-relaxed text-ops-mute">Stay loyal, take part in Clan Wars, support your teammates, and keep it fair. Our eight rules set the standard for every OPSKe member.</p></div><Link className="btn-ghost" to="/clan-rules">View clan rules</Link></div>
    </section>
    <section className="grid gap-6 lg:grid-cols-2" aria-label="About and community">
      <article className="card space-y-5">
        <SectionHeading eyebrow="About OPSKe" title="A place to play and belong." />
        <p className="leading-relaxed text-ops-mute">OPSKe brings clan updates, official tournament results, and member services into one place. Follow the competition, keep up with your squad, and take the next step when you’re ready to join.</p>
        <dl className="space-y-4 text-sm">
          <div><dt className="font-semibold text-white">Games & divisions</dt><dd className="mt-1 text-ops-mute">See the games featured in our tournament results. Tell us your game and player ID when applying.</dd></div>
          <div><dt className="font-semibold text-white">Before you apply</dt><dd className="mt-1 text-ops-mute">Have your updated in-game name, clan tag, profile screenshot, and contact details ready. Read the clan rules before sending your request.</dd></div>
        </dl>
        <div className="flex flex-wrap gap-x-5 gap-y-2"><Link className="link inline-block py-2 text-sm font-semibold" to="/clan-rules">Read the clan rules</Link><Link className="link inline-block py-2 text-sm font-semibold" to="/results">Explore tournament results</Link></div>
      </article>
      <article className="card space-y-5">
        <SectionHeading eyebrow="Stay connected" title="Keep up with the clan." />
        <p className="leading-relaxed text-ops-mute">Follow @opskegamer on TikTok for more from OPSKe, and check clan announcements for scrim registration and team updates.</p>
        <div className="flex flex-wrap gap-3">
          <a className="btn-primary" href="https://www.tiktok.com/@opskegamer" target="_blank" rel="noopener noreferrer">Follow on TikTok <span aria-hidden="true">↗</span></a>
          <Link className="btn-ghost" to="/announcements">Clan announcements</Link>
        </div>
        <p className="border-t border-ops-line pt-5 text-sm leading-relaxed text-ops-mute">Want to join the clan? Send an application so an admin can review your profile. No website account needed.</p>
      </article>
    </section>
  </>
}
