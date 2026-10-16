import { useState } from 'react'
import { api } from '../lib/api'
import { ErrorBox, Field } from '../components/ui'

export default function JoinClan() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    const form = e.currentTarget
    const data = new FormData(form)
    const file = data.get('screenshot')
    if (file.size > 5 * 1024 * 1024) { setError('Screenshot must be 5 MB or smaller.'); return }
    setBusy(true); setError('')
    try { setReceipt(await api.form('/api/clan/requests', data)); form.reset() }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <section className="mx-auto max-w-2xl space-y-6">
    <div><p className="text-sm font-semibold text-ops-link">JOIN THE CLAN</p>
      <h1 className="mt-3 font-display text-3xl sm:text-4xl font-extrabold text-white sm:text-5xl">Your next squad starts here.</h1>
      <p className="mt-4 leading-relaxed text-ops-mute">Apply to join OPSKe. No website account needed. Update your in-game profile name to include the clan tag, then send a clear screenshot showing your name and player ID.</p>
    </div>
    {receipt ? <div role="status" className="tile space-y-3"><h2 className="font-display text-2xl font-bold">Request received</h2><p>Your reference is #{receipt.id}. Your application is pending admin review. The team will use your contact details to follow up.</p><button className="btn-ghost" onClick={() => setReceipt(null)}>Send another request</button></div> :
      <form onSubmit={submit} className="space-y-5 rounded-[32px] bg-ops-card p-6 sm:p-8">
        <ErrorBox message={error} />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Game / division"><input className="input" name="game" required minLength={2} maxLength={80} placeholder="e.g. PUBG Mobile" /></Field>
          <Field label="Player ID / UID"><input className="input" name="player_id" required maxLength={80} /></Field>
          <Field label="Updated in-game name"><input className="input" name="gamer_tag" required minLength={2} maxLength={64} placeholder="Your name including the clan tag" /></Field>
          <Field label="Clan tag added to your name"><input className="input" name="clan_tag" required maxLength={32} placeholder="Enter the tag you added" /></Field>
          <Field label="Email"><input className="input" name="email" type="email" required maxLength={255} /></Field>
          <Field label="Phone / WhatsApp / Discord"><input className="input" name="contact" required minLength={3} maxLength={100} /></Field>
        </div>
        <Field label="Why do you want to join?"><textarea className="input min-h-32" name="message" required minLength={20} maxLength={3000} placeholder="Tell us about your experience, usual play times, and what you can bring to the clan." /></Field>
        <Field label="Profile screenshot (PNG, JPEG, or WebP · up to 5 MB)"><input className="input" name="screenshot" type="file" accept="image/png,image/jpeg,image/webp" required /><span className="mt-2 block text-sm text-ops-mute">Show your updated profile name, clan tag, and player ID. Only clan reviewers can view your screenshot and application.</span></Field>
        <label className="flex items-start gap-3 text-sm"><input className="mt-1" type="checkbox" name="name_updated" value="true" required /><span>I have updated my in-game name to include the clan tag, and the screenshot shows the change.</span></label>
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? 'Sending request…' : 'Request to join OPSKe'}</button>
        <p className="text-sm text-ops-mute">Submitting a request does not create a website account. Membership is subject to admin approval.</p>
      </form>}
  </section>
}
