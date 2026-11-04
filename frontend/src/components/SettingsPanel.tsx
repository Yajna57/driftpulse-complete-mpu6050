import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TelegramSettings } from '../types'

interface Props {
  userId: string
  onClose: () => void
}

type Msg = { kind: 'ok' | 'err'; text: string } | null

const errText = (e: unknown) => (e instanceof Error ? e.message : 'Request failed')

export function SettingsPanel({ userId, onClose }: Props) {
  const [loaded, setLoaded] = useState<TelegramSettings | null>(null)
  const [token, setToken] = useState('')
  const [generalChat, setGeneralChat] = useState('')
  const [generalOn, setGeneralOn] = useState(true)
  const [userChat, setUserChat] = useState('')
  const [userOn, setUserOn] = useState(true)
  const [generalMsg, setGeneralMsg] = useState<Msg>(null)
  const [userMsg, setUserMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  function apply(s: TelegramSettings) {
    setLoaded(s)
    setGeneralChat(s.general.chat_id ?? '')
    setGeneralOn(s.general.enabled)
    setUserChat(s.user?.chat_id ?? '')
    setUserOn(s.user?.enabled ?? true)
    setToken('')
  }

  useEffect(() => {
    setLoaded(null); setGeneralMsg(null); setUserMsg(null)
    api.telegramSettings(userId).then(apply).catch((e) => setGeneralMsg({ kind: 'err', text: errText(e) }))
  }, [userId])

  async function run(setMsg: (m: Msg) => void, okText: string, job: () => Promise<TelegramSettings | { sent: boolean }>) {
    setBusy(true); setMsg(null)
    try {
      const result = await job()
      if ("bot_token_set" in result) apply(result)
      setMsg({ kind: 'ok', text: okText })
    } catch (e) {
      setMsg({ kind: 'err', text: errText(e) })
    } finally {
      setBusy(false)
    }
  }

  const saveGeneral = () => run(setGeneralMsg, 'Saved.', () =>
    api.saveTelegramGeneral({ chat_id: generalChat, enabled: generalOn, bot_token: token.trim() ? token : null }))
  const clearToken = () => run(setGeneralMsg, 'Token removed.', () =>
    api.saveTelegramGeneral({ chat_id: generalChat, enabled: generalOn, bot_token: '' }))
  const testGeneral = () => run(setGeneralMsg, 'Test message sent.', () => api.telegramTest(null))
  const saveUser = () => run(setUserMsg, 'Saved.', () =>
    api.saveTelegramUser(userId, { chat_id: userChat, enabled: userOn }))
  const testUser = () => run(setUserMsg, 'Test message sent.', () => api.telegramTest(userId))

  const note = (m: Msg) => (m ? <p className={m.kind === 'ok' ? 'settings-ok' : 'settings-err'}>{m.text}</p> : null)

  return (
    <section className="panel settings-panel">
      <div className="section-heading">
        <h3>Telegram alert settings</h3>
        <button className="secondary-button" onClick={onClose}>Close</button>
      </div>
      <p className="muted">
        Create a bot with @BotFather, press Start in the bot chat, then get your chat id from
        <code> https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates </code>
        (<code>message.chat.id</code>). For a group, add the bot to the group first.
        An alert goes to the user chat and the general chat, if both are set.
      </p>

      <div className="settings-grid">
        <div className="settings-block">
          <h4>General (all users)</h4>
          <label>Bot token
            <input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)}
              placeholder={loaded?.bot_token_set ? `Saved: ${loaded.bot_token_hint} (leave blank to keep)` : '123456:ABC...'} />
          </label>
          <label>General chat id
            <input value={generalChat} onChange={(e) => setGeneralChat(e.target.value)} placeholder="e.g. 987654321 or -100123456789" />
          </label>
          <label className="settings-check">
            <input type="checkbox" checked={generalOn} onChange={(e) => setGeneralOn(e.target.checked)} /> Send every user's alerts here
          </label>
          <div className="settings-actions">
            <button className="secondary-button" disabled={busy} onClick={saveGeneral}>Save</button>
            <button className="secondary-button" disabled={busy || !loaded?.bot_token_set || !loaded?.general.chat_id} onClick={testGeneral}>Send test</button>
            <button className="secondary-button" disabled={busy || !loaded?.bot_token_set} onClick={clearToken}>Remove token</button>
          </div>
          {note(generalMsg)}
        </div>

        <div className="settings-block">
          <h4>User {userId}</h4>
          <label>Personal chat id
            <input value={userChat} onChange={(e) => setUserChat(e.target.value)} placeholder="e.g. 987654321" />
          </label>
          <label className="settings-check">
            <input type="checkbox" checked={userOn} onChange={(e) => setUserOn(e.target.checked)} /> Send this user's alerts here
          </label>
          <div className="settings-actions">
            <button className="secondary-button" disabled={busy} onClick={saveUser}>Save</button>
            <button className="secondary-button" disabled={busy || !loaded?.bot_token_set || !loaded?.user?.chat_id} onClick={testUser}>Send test</button>
          </div>
          {note(userMsg)}
          {!loaded?.bot_token_set ? <p className="muted">Save the bot token first.</p> : null}
        </div>
      </div>
    </section>
  )
}
