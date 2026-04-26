import { motion } from 'framer-motion'
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Glasses,
  Mail,
  RefreshCcw,
  ShieldCheck,
  TimerReset,
  Unplug,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import heroImage from './assets/hero.png'
import {
  disconnectGoogle,
  fetchGoogleHistory,
  fetchGoogleStatus,
  getGoogleConnectUrl,
  type GoogleStatus,
  type HistoryEvent,
} from './lib/api'

const ease: [number, number, number, number] = [0.16, 1, 0.3, 1]

const workflowCards = [
  {
    icon: Mail,
    title: 'Gmail dispatch',
    body: 'Let the glasses draft and trigger outbound email after the linked user confirms their identity.',
  },
  {
    icon: CalendarClock,
    title: 'Calendar control',
    body: 'Create and route scheduling requests through the same shared pair of glasses without re-pairing hardware.',
  },
  {
    icon: TimerReset,
    title: 'Task memory',
    body: 'Turn spoken reminders and to-dos into Google-backed actions tied to the currently connected site user.',
  },
] as const

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function DashboardHeader({
  status,
  refreshing,
  onRefresh,
  onDisconnect,
}: {
  status: GoogleStatus | null
  refreshing: boolean
  onRefresh: () => void
  onDisconnect: () => Promise<void>
}) {
  const connectedUser = status?.active_user

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease }}
      className="glass-panel relative overflow-hidden rounded-[2rem] border border-white/10 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.45)] md:p-8"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(225,224,204,0.16),transparent_35%),radial-gradient(circle_at_bottom_left,rgba(111,78,55,0.22),transparent_30%)]" />
      <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl space-y-4">
          <p className="text-[0.7rem] uppercase tracking-[0.35em] text-[#c9c6a6]/65">
            Shared Glasses Control Surface
          </p>
          <h1 className="max-w-2xl text-5xl leading-none tracking-[-0.05em] text-[#f4f1d8] md:text-7xl">
            Edith turns one pair of Meta glasses into a live Google workflow.
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-[#d3cfb3]/72 md:text-base">
            Anyone can use the glasses for conversation, but protected Google actions only
            unlock after they connect on the site. When a task matters, the glasses ask for a
            spoken confirmation before they continue.
          </p>
        </div>

        <div className="w-full max-w-md rounded-[1.75rem] border border-white/8 bg-black/40 p-5 backdrop-blur-xl">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full border border-[#d9d3aa]/20 bg-[#d9d3aa]/10">
                <Glasses className="h-5 w-5 text-[#efe9c6]" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-[#b9b48d]/60">
                  Active user
                </p>
                <p className="text-lg text-[#f2efd9]">
                  {connectedUser?.display_name ?? 'No Google account connected'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-xs uppercase tracking-[0.2em] text-[#d8d1ab] transition hover:border-[#d8d1ab]/40 hover:text-[#f4f1d8] disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          <div className="space-y-3 rounded-[1.5rem] bg-white/[0.03] p-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-4 w-4 text-[#efe9c6]" />
              <p className="text-sm text-[#d9d4bb]">
                {connectedUser
                  ? `${connectedUser.email} is currently action-enabled for the shared glasses.`
                  : 'No one is linked yet, so Gmail, Calendar, and Tasks actions stay locked.'}
              </p>
            </div>

            {connectedUser ? (
              <div className="grid gap-3 pt-2 sm:grid-cols-2">
                <div>
                  <p className="text-[0.68rem] uppercase tracking-[0.28em] text-[#b9b48d]/55">
                    Connected
                  </p>
                  <p className="mt-1 text-sm text-[#f2efd9]">
                    {formatTimestamp(connectedUser.connected_at)}
                  </p>
                </div>
                <div>
                  <p className="text-[0.68rem] uppercase tracking-[0.28em] text-[#b9b48d]/55">
                    Granted scopes
                  </p>
                  <p className="mt-1 text-sm text-[#f2efd9]">
                    {connectedUser.granted_scopes.length}
                  </p>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <a
              href={getGoogleConnectUrl()}
              className="group inline-flex flex-1 items-center justify-between rounded-full bg-[#e7e0b1] px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-black transition hover:bg-[#f4edbc]"
            >
              Connect Google
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
            </a>
            <button
              type="button"
              onClick={() => {
                void onDisconnect()
              }}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm uppercase tracking-[0.18em] text-[#e8e2bb] transition hover:border-[#e8e2bb]/40 hover:text-[#f5f1d8]"
            >
              <Unplug className="h-4 w-4" />
              Disconnect
            </button>
          </div>
        </div>
      </div>
    </motion.section>
  )
}

function HistoryTimeline({ history }: { history: HistoryEvent[] }) {
  return (
    <section className="grid gap-5 lg:grid-cols-[1.1fr,0.9fr]">
      <motion.article
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.75, ease }}
        className="glass-panel rounded-[2rem] border border-white/10 p-6 md:p-7"
      >
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <p className="text-[0.7rem] uppercase tracking-[0.35em] text-[#c9c6a6]/65">
              Action history
            </p>
            <h2 className="mt-2 text-3xl tracking-[-0.04em] text-[#f4f1d8]">
              Every confirmed glasses action, in one trail.
            </h2>
          </div>
          <div className="rounded-full border border-white/10 px-3 py-2 text-xs uppercase tracking-[0.25em] text-[#d0caa7]">
            {history.length} events
          </div>
        </div>

        <div className="space-y-4">
          {history.length === 0 ? (
            <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-[#c8c39f]">
              No Google workflow actions have been logged yet. Connect an account and ask the
              glasses to send an email, create a calendar event, or capture a task.
            </div>
          ) : (
            history
              .slice()
              .reverse()
              .map((event) => (
                <div
                  key={event.id}
                  className="rounded-[1.4rem] border border-white/8 bg-black/35 p-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-[#efe9c6]" />
                        <p className="text-sm uppercase tracking-[0.22em] text-[#bdb791]">
                          {event.intent.replaceAll('_', ' ')}
                        </p>
                      </div>
                      <p className="text-base leading-6 text-[#f2efd9]">{event.summary}</p>
                    </div>
                    <div className="text-left sm:text-right">
                      <p className="text-xs uppercase tracking-[0.24em] text-[#d0caa7]/65">
                        {event.status}
                      </p>
                      <p className="mt-1 text-sm text-[#c6c1a0]">
                        {formatTimestamp(event.timestamp)}
                      </p>
                    </div>
                  </div>
                  {event.actor_email ? (
                    <p className="mt-3 text-xs uppercase tracking-[0.2em] text-[#9d987a]">
                      {event.actor_email}
                    </p>
                  ) : null}
                </div>
              ))
          )}
        </div>
      </motion.article>

      <motion.aside
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.75, delay: 0.05, ease }}
        className="space-y-5"
      >
        <div className="glass-panel rounded-[2rem] border border-white/10 p-6">
          <p className="text-[0.7rem] uppercase tracking-[0.35em] text-[#c9c6a6]/65">
            Confirmation flow
          </p>
          <ol className="mt-5 space-y-4 text-sm leading-6 text-[#ddd7b8]">
            <li>1. Connect your Google account on the site.</li>
            <li>2. Ask the shared glasses to send mail, create an event, or set a task.</li>
            <li>3. The glasses ask, “Before I continue, just to confirm, are you &lt;name&gt;?”</li>
            <li>4. Say `yes` and the action proceeds immediately.</li>
          </ol>
        </div>

        {workflowCards.map(({ icon: Icon, title, body }, index) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, x: 18 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.65, delay: index * 0.08, ease }}
            className="glass-panel rounded-[1.75rem] border border-white/10 p-5"
          >
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.05]">
              <Icon className="h-5 w-5 text-[#efe9c6]" />
            </div>
            <h3 className="text-xl tracking-[-0.03em] text-[#f3efd7]">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-[#cbc5a2]">{body}</p>
          </motion.div>
        ))}
      </motion.aside>
    </section>
  )
}

export default function App() {
  const [status, setStatus] = useState<GoogleStatus | null>(null)
  const [history, setHistory] = useState<HistoryEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadDashboard() {
    setError(null)
    const [nextStatus, nextHistory] = await Promise.all([
      fetchGoogleStatus(),
      fetchGoogleHistory(),
    ])
    setStatus(nextStatus)
    setHistory(nextHistory.events)
  }

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        await loadDashboard()
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Could not reach the backend dashboard.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    const interval = window.setInterval(() => {
      void loadDashboard().catch((refreshError) => {
        if (!cancelled) {
          setError(
            refreshError instanceof Error
              ? refreshError.message
              : 'Could not refresh dashboard state.',
          )
        }
      })
    }, 15000)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await loadDashboard()
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : 'Could not refresh dashboard state.',
      )
    } finally {
      setRefreshing(false)
    }
  }

  async function handleDisconnect() {
    try {
      await disconnectGoogle()
      await loadDashboard()
    } catch (disconnectError) {
      setError(
        disconnectError instanceof Error
          ? disconnectError.message
          : 'Could not disconnect the active Google account.',
      )
    }
  }

  return (
    <main className="min-h-screen bg-[#050505] text-[#e7e3ca]">
      <div className="relative isolate overflow-hidden">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `linear-gradient(180deg, rgba(5, 5, 5, 0.2), rgba(5, 5, 5, 0.95)), url(${heroImage})`,
            backgroundPosition: 'center',
            backgroundSize: 'cover',
          }}
        />
        <div className="bg-noise absolute inset-0 opacity-20" />
        <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 md:px-8">
          <DashboardHeader
            status={status}
            refreshing={refreshing}
            onRefresh={() => {
              void handleRefresh()
            }}
            onDisconnect={handleDisconnect}
          />

          {loading ? (
            <div className="glass-panel rounded-[2rem] border border-white/10 p-8 text-sm uppercase tracking-[0.25em] text-[#d0caa7]">
              Loading dashboard state...
            </div>
          ) : null}

          {error ? (
            <div className="glass-panel rounded-[2rem] border border-[#9c4f44]/30 bg-[#1a0807]/80 p-5 text-sm text-[#f0c3ba]">
              {error}
            </div>
          ) : null}

          <HistoryTimeline history={history} />
        </div>
      </div>
    </main>
  )
}
