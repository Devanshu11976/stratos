'use client'

import { useEffect, useState, useCallback, useRef, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Navbar from '@/components/shared/Navbar'
import CustomCursor from '@/components/shared/CustomCursor'
import { 
  Upload, 
  Zap, 
  Cpu, 
  Check, 
  Package, 
  Globe, 
  Phone, 
  CreditCard, 
  Calendar, 
  DollarSign, 
  BarChart2 
} from 'lucide-react'

import { apiFetch } from '@/lib/api'
import { cssDuration, cssDurationMs } from '@/lib/motion'
const POLL_MS = 3000

// ─── Types ────────────────────────────────────────────────────────────────────
type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

interface CountryStat { total: number; valid: number; invalid: number }

interface JobDetails {
  job_id: string
  status: JobStatus
  total_records: number | null
  valid_records: number | null
  invalid_records: number | null
  processing_time_ms: number | null
  country_stats: Record<string, CountryStat>
  validation_breakdown: Record<string, number>
}

interface ChunkInfo { url: string; record_count: number; file_size_bytes: number }

interface Downloads {
  clean_transactions_url: string | null
  clean_record_count: number | null
  clean_file_size_bytes: number | null
  error_report_url: string | null
  error_record_count: number | null
  error_file_size_bytes: number | null
  chunks: ChunkInfo[]
}

interface AIReport {
  quality_score: number
  common_errors: Array<{ field: string; error: string; count: number }>
  country_analysis: Record<string, { status: string; issue: string | null } | string>
  recommendations: string[]
  executive_summary: string
}

// ─── Utility helpers ──────────────────────────────────────────────────────────
function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

function fmtMs(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`
}

// ─── Count-up hook ────────────────────────────────────────────────────────────
function useCountUp(target: number, duration = cssDurationMs(900)): number {
  const [val, setVal] = useState(0)
  const raf = useRef<number | null>(null)
  useEffect(() => {
    if (target === 0) { setVal(0); return }
    const start = performance.now()
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - p, 3)
      setVal(Math.round(ease * target))
      if (p < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [target, duration])
  return val
}

// ─── Fade-in wrapper ──────────────────────────────────────────────────────────
function FadeIn({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const [vis, setVis] = useState(false)
  useEffect(() => { const t = setTimeout(() => setVis(true), delay); return () => clearTimeout(t) }, [delay])
  return (
    <div style={{
      opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(12px)',
      transition: `opacity ${cssDuration(0.45)}s ease, transform ${cssDuration(0.45)}s ease`,
    }}>
      {children}
    </div>
  )
}

// ─── Shared primitives ────────────────────────────────────────────────────────
function SectionCard({ title, children, delay = 0 }: { title: string; children: React.ReactNode; delay?: number }) {
  return (
    <FadeIn delay={delay}>
      <div style={{
        background: 'rgba(255,255,255,0.025)', border: '1px solid var(--line)',
        borderRadius: 20, padding: '28px 24px', marginBottom: 16,
      }}>
        <h3 style={{
          fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 700,
          letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--mist-dim)', marginBottom: 20,
        }}>{title}</h3>
        {children}
      </div>
    </FadeIn>
  )
}

function StatusBadge({ status }: { status: JobStatus | 'loading' }) {
  const map: Record<string, [string, string]> = {
    loading: ['var(--mist-dim)', 'Connecting…'],
    queued: ['var(--signal)', 'Queued'],
    processing: ['var(--ingest)', 'Processing'],
    completed: ['#10b981', 'Completed'],
    failed: ['#f87171', 'Failed'],
  }
  const [c, label] = map[status] ?? map.loading
  const pulse = status === 'queued' || status === 'processing'
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '8px 18px', borderRadius: 100,
      background: 'rgba(255,255,255,0.03)', border: `1px solid ${c}`, color: c,
      fontFamily: "'IBM Plex Mono',monospace", fontSize: 14, fontWeight: 600,
      boxShadow: `0 0 15px -3px ${c}33`,
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%', background: c,
        animation: pulse ? `pulse-dot ${cssDuration(1.5)}s infinite` : 'none',
        boxShadow: `0 0 8px ${c}`,
      }} />
      {label}
    </div>
  )
}

function PipelineTracker({ status }: { status: JobStatus | 'loading' }) {
  const steps = ['Uploaded', 'Queued', 'Processing', 'Finished']
  const activeIdx = status === 'queued' ? 1 : status === 'processing' ? 2 : status === 'completed' ? 3 : status === 'failed' ? 3 : 0
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative', maxWidth: 480, margin: '0 auto 36px' }}>
      <div style={{ position: 'absolute', top: 15, left: 30, right: 30, height: 2, background: 'var(--line)', zIndex: 0 }} />
      <div style={{
        position: 'absolute', top: 15, left: 30,
        width: `${Math.min((activeIdx / 3) * 100, 100)}%`, maxWidth: 'calc(100% - 60px)',
        height: 2, background: status === 'failed' ? '#f87171' : 'var(--refine)',
        transition: `width ${cssDuration(0.6)}s ease`, zIndex: 0,
      }} />
      {steps.map((label, i) => {
        const done = i < activeIdx || (i === 3 && status === 'completed')
        const active = i === activeIdx && status !== 'completed' && status !== 'failed'
        const fail = i === 3 && status === 'failed'
        const col = fail ? '#f87171' : (done || active ? 'var(--refine)' : 'var(--line)')
        return (
          <div key={label} style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: '#0a0b0e', border: `2px solid ${col}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, color: fail ? '#f87171' : (done ? 'var(--refine)' : (active ? 'var(--refine)' : 'var(--mist-dim)')),
              transition: 'all 0.3s ease',
            }}>
              {fail ? '✗' : done ? '✓' : active ? '●' : `0${i + 1}`}
            </div>
            <span style={{ fontSize: 11, color: done || active ? 'var(--mist)' : 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif" }}>
              {label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Animated metric card ─────────────────────────────────────────────────────
function MetricCard({ label, rawValue, display, accent }: {
  label: string; rawValue: number; display?: string; accent: string
}) {
  const animated = useCountUp(rawValue)
  const shown = display ?? animated.toLocaleString()
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid var(--line)',
      borderRadius: 16, padding: '22px 18px', textAlign: 'center', flex: 1, minWidth: 120,
      transition: 'border-color 0.2s, background 0.2s',
    }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = accent;
        (e.currentTarget as HTMLDivElement).style.background = `${accent}0d`
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--line)';
        (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.03)'
      }}>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 26, fontWeight: 700, color: accent, marginBottom: 6 }}>
        {shown}
      </div>
      <div style={{ fontSize: 11, color: 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif", letterSpacing: '0.05em', textTransform: 'uppercase' }}>
        {label}
      </div>
    </div>
  )
}

function QualityRing({ score }: { score: number }) {
  const r = 36, circ = 2 * Math.PI * r
  const color = score >= 80 ? '#10b981' : score >= 60 ? 'var(--signal)' : '#f87171'
  const animated = useCountUp(Math.round(score), 1200)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <svg width={96} height={96} viewBox="0 0 96 96">
        <circle cx={48} cy={48} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={7} />
        <circle cx={48} cy={48} r={r} fill="none" stroke={color} strokeWidth={7}
          strokeDasharray={`${(animated / 100) * circ} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 48 48)" style={{ transition: 'stroke-dasharray 0.05s linear' }} />
        <text x={48} y={53} textAnchor="middle" fontSize={18} fontWeight={700} fill={color}
          fontFamily="IBM Plex Mono,monospace">{animated}</text>
      </svg>
      <span style={{ fontSize: 11, color: 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif", textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Quality Score
      </span>
    </div>
  )
}

// ─── 1. Country Analysis Cards ────────────────────────────────────────────────
function CountryAnalysisSection({ countryStats, countryNames }: { countryStats: Record<string, CountryStat>; countryNames: Record<string, string> }) {
  const entries = Object.entries(countryStats)
  if (!entries.length) return null
  return (
    <SectionCard title="Country Analysis" delay={80}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {entries.filter(([code]) => code !== 'XX').map(([code, s]) => {
          const passRate = s.total ? (s.valid / s.total) * 100 : 0
          const col = passRate >= 80 ? '#10b981' : passRate >= 60 ? 'var(--signal)' : '#f87171'
          const name = code === 'XX' ? 'Unknown' : (countryNames[code] ?? code)
          return (
            <div key={code}
              style={{
                flex: '1 1 170px', minWidth: 160, maxWidth: 220,
                background: 'rgba(255,255,255,0.03)', border: `1px solid ${col}22`,
                borderRadius: 16, padding: '18px 16px',
                transition: 'border-color 0.2s, background 0.2s, transform 0.2s',
                cursor: 'default',
              }}
              onMouseEnter={e => {
                const el = e.currentTarget as HTMLDivElement
                el.style.borderColor = col; el.style.background = `${col}0d`; el.style.transform = 'translateY(-2px)'
              }}
              onMouseLeave={e => {
                const el = e.currentTarget as HTMLDivElement
                el.style.borderColor = `${col}22`; el.style.background = 'rgba(255,255,255,0.03)'; el.style.transform = 'translateY(0)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                <div>
                  <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 14, fontWeight: 600, color: 'var(--mist)', marginBottom: 2 }}>
                    {name}
                  </div>
                  <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, color: 'var(--mist-dim)' }}>{code}</div>
                </div>
                <div style={{
                  fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, fontWeight: 700,
                  color: col, background: `${col}18`, padding: '3px 8px', borderRadius: 6,
                }}>
                  {passRate.toFixed(0)}%
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  ['Total', s.total, 'var(--refine)'],
                  ['Valid', s.valid, '#10b981'],
                  ['Invalid', s.invalid, '#f87171'],
                ].map(([lbl, val, ac]) => (
                  <div key={lbl as string} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif" }}>{lbl as string}</span>
                    <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600, color: ac as string }}>
                      {(val as number).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12, height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.06)' }}>
                <div style={{ height: 3, borderRadius: 2, background: col, width: `${passRate}%`, transition: `width ${cssDuration(0.8)}s ease` }} />
              </div>
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}

// ─── 2. Download Center ───────────────────────────────────────────────────────
function DownloadCard({ icon, label, accent, url, recordCount, fileSizeBytes }: {
  icon: string; label: string; accent: string; url: string | null
  recordCount: number | null; fileSizeBytes: number | null
}) {
  const [hov, setHov] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const isDemo = !url

  const handleDownload = async () => {
    if (!url || downloading) return
    setDownloading(true)
    try {
      const res = await apiFetch(url)
      if (!res || !res.ok) throw new Error(`Download failed: ${res?.status ?? 'offline'}`)
      const blob = await res.blob()
      const blobUrl = URL.createObjectURL(blob)
      const disposition = res.headers.get('Content-Disposition')
      let filename = 'download.csv'
      if (disposition) {
        const match = disposition.match(/filename="?([^";\n]+)"?/)
        if (match) filename = match[1]
      } else {
        // Fallback: generate clean filename based on label
        const date = new Date().toISOString().split('T')[0]
        if (label === 'Clean Dataset') {
          filename = `clean_${date}.csv`
        } else if (label === 'Error Report') {
          filename = `errors_${date}.csv`
        } else if (label.startsWith('Chunk')) {
          filename = `chunk_${date}.csv`
        } else {
          filename = `export_${date}.csv`
        }
      }
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch (err) {
      console.error('Download error:', err)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div style={{
      flex: '1 1 160px', minWidth: 150, textDecoration: 'none',
      display: 'flex', flexDirection: 'column', gap: 10,
      padding: '16px 18px', borderRadius: 14,
      background: hov && !isDemo ? `${accent}0f` : 'rgba(255,255,255,0.03)',
      border: `1px solid ${hov && !isDemo ? accent : `${accent}33`}`,
      transition: 'all 0.18s ease', transform: hov && !isDemo ? 'translateY(-2px)' : 'translateY(0)',
      cursor: isDemo ? 'default' : 'pointer',
      opacity: isDemo ? 0.6 : 1,
    }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      onClick={!isDemo ? handleDownload : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18, lineHeight: 1 }}>{downloading ? '⏳' : icon}</span>
        <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600, color: accent }}>
          {downloading ? 'Downloading…' : label}
        </span>
        {isDemo && (
          <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono',monospace", color: 'var(--mist-dim)', marginLeft: 'auto', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            demo
          </span>
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {recordCount !== null && (
          <span style={{ fontSize: 11, color: 'var(--mist)', fontFamily: "'Space Grotesk',sans-serif" }}>
            {recordCount.toLocaleString()} records
          </span>
        )}
        {fileSizeBytes !== null && fileSizeBytes > 0 && (
          <span style={{ fontSize: 10, color: 'var(--mist-dim)', fontFamily: "'IBM Plex Mono',monospace" }}>
            {fmtBytes(fileSizeBytes)}
          </span>
        )}
      </div>
    </div>
  )
}

function DownloadCenter({ downloads }: { downloads: Downloads }) {
  const hasAny = downloads.clean_record_count || downloads.error_record_count || downloads.chunks.length > 0
  if (!hasAny) return null
  return (
    <SectionCard title="Download Results" delay={120}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {(downloads.clean_transactions_url || downloads.clean_record_count) && (
          <DownloadCard icon="✓" label="Clean Dataset" accent="#10b981"
            url={downloads.clean_transactions_url}
            recordCount={downloads.clean_record_count}
            fileSizeBytes={downloads.clean_file_size_bytes} />
        )}
        {downloads.error_report_url && (
          <DownloadCard icon="⚠" label="Error Report" accent="#f87171"
            url={downloads.error_report_url}
            recordCount={downloads.error_record_count}
            fileSizeBytes={downloads.error_file_size_bytes} />
        )}
        {(downloads.error_report_url === null && downloads.error_record_count) && (
          <DownloadCard icon="⚠" label="Error Report" accent="#f87171"
            url={null}
            recordCount={downloads.error_record_count}
            fileSizeBytes={downloads.error_file_size_bytes} />
        )}
        {downloads.chunks.map((c, i) => (
          <DownloadCard key={i} icon="▦" label={`Chunk ${i + 1}`} accent="var(--ingest)"
            url={c.url ?? null} recordCount={c.record_count} fileSizeBytes={c.file_size_bytes} />
        ))}
      </div>
    </SectionCard>
  )
}

// ─── 3. AI Insights ──────────────────────────────────────────────────────────
function AIInsightsSection({ report, qualityScore, countryNames }: { report: AIReport; qualityScore: number; countryNames: Record<string, string> }) {
  const highestErrorRegion = Object.entries(report.country_analysis).find(([, v]) => {
    const s = typeof v === 'string' ? v : (v as any)?.status ?? ''
    return s === 'failing'
  })?.[0] ?? Object.entries(report.country_analysis).find(([, v]) => {
    const s = typeof v === 'string' ? v : (v as any)?.status ?? ''
    return s === 'warning'
  })?.[0] ?? null

  const primaryIssues = report.common_errors.slice(0, 4).map(e =>
    `${e.field.replace(/_/g, ' ')} (${e.count})`
  )

  return (
    <SectionCard title="AI Insights" delay={100}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <div style={{
          flex: '2 1 280px',
          background: 'rgba(155,107,255,0.06)', border: '1px solid rgba(155,107,255,0.18)',
          borderRadius: 14, padding: '18px 20px',
        }}>
          <div style={{ fontSize: 10, fontFamily: "'IBM Plex Mono',monospace", color: 'rgba(155,107,255,0.7)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>
            Executive Summary
          </div>
          <p style={{ fontSize: 13, color: 'var(--mist)', lineHeight: 1.75, margin: 0 }}>
            {report.executive_summary}
          </p>
        </div>

        <div style={{ flex: '1 1 180px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{
            background: 'rgba(255,255,255,0.03)', border: '1px solid var(--line)',
            borderRadius: 14, padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 11, color: 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif", textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Quality Score
            </span>
            <span style={{
              fontFamily: "'IBM Plex Mono',monospace", fontSize: 22, fontWeight: 700,
              color: qualityScore >= 80 ? '#10b981' : qualityScore >= 60 ? 'var(--signal)' : '#f87171',
            }}>
              {qualityScore.toFixed(0)}<span style={{ fontSize: 13, opacity: 0.5 }}>/100</span>
            </span>
          </div>

          {highestErrorRegion && highestErrorRegion !== 'XX' && (
            <div style={{
              background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.2)',
              borderRadius: 14, padding: '12px 16px',
            }}>
              <div style={{ fontSize: 10, color: 'rgba(248,113,113,0.7)', fontFamily: "'IBM Plex Mono',monospace", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
                Highest Error Region
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f87171', fontFamily: "'Space Grotesk',sans-serif" }}>
                {countryNames[highestErrorRegion] ?? highestErrorRegion}
              </div>
            </div>
          )}
        </div>
      </div>

      {primaryIssues.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: 'var(--mist-dim)', fontFamily: "'IBM Plex Mono',monospace", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>
            Primary Issues
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {primaryIssues.map((issue, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 8,
                background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.2)',
                fontSize: 12, color: '#f87171', fontFamily: "'Space Grotesk',sans-serif",
              }}>
                <span style={{ opacity: 0.6 }}>•</span> {issue}
              </div>
            ))}
          </div>
        </div>
      )}

      {report.common_errors.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: 'var(--mist-dim)', fontFamily: "'IBM Plex Mono',monospace", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>
            Error Distribution
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {report.common_errors.slice(0, 6).map((e, i) => {
              const maxCount = report.common_errors[0]?.count ?? 1
              const pct = Math.round((e.count / maxCount) * 100)
              return (
                <div key={i} style={{
                  padding: '10px 14px', borderRadius: 10,
                  background: 'rgba(255,255,255,0.025)', border: '1px solid var(--line-soft)',
                  overflow: 'hidden',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: 'var(--signal)', background: 'rgba(255,184,0,0.1)', padding: '2px 6px', borderRadius: 4 }}>
                        {e.field}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--mist)' }}>{e.error}</span>
                    </div>
                    <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: '#f87171', background: 'rgba(248,113,113,0.1)', padding: '2px 8px', borderRadius: 6, flexShrink: 0 }}>
                      {e.count.toLocaleString()}
                    </span>
                  </div>
                  <div style={{ height: 2, borderRadius: 1, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                    <div style={{ height: 2, borderRadius: 1, background: '#f87171', width: `${pct}%`, maxWidth: '100%', transition: `width ${cssDuration(0.6)}s ease` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {report.recommendations.length > 0 && (
        <div>
          <div style={{ fontSize: 10, color: 'var(--mist-dim)', fontFamily: "'IBM Plex Mono',monospace", letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>
            Recommended Actions
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {report.recommendations.map((rec, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ color: 'var(--refine)', fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, paddingTop: 2, flexShrink: 0 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span style={{ fontSize: 13, color: 'var(--mist)', lineHeight: 1.65 }}>{rec}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}

// ─── 4. Pipeline Performance ──────────────────────────────────────────────────
function PerfTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  const [hov, setHov] = useState(false)
  return (
    <div style={{
      flex: '1 1 130px', minWidth: 120,
      background: hov ? 'rgba(155,107,255,0.06)' : 'rgba(255,255,255,0.03)',
      border: `1px solid ${hov ? 'rgba(155,107,255,0.35)' : 'var(--line)'}`,
      borderRadius: 14, padding: '18px 16px', textAlign: 'center',
      transition: 'all 0.18s ease', transform: hov ? 'translateY(-2px)' : 'translateY(0)',
    }}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 22, fontWeight: 700, color: 'var(--refine)', marginBottom: 4 }}>
        {value}
      </div>
      {sub && <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, color: 'var(--mist-dim)', marginBottom: 4 }}>{sub}</div>}
      <div style={{ fontSize: 10, color: 'var(--mist-dim)', fontFamily: "'Space Grotesk',sans-serif", textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
    </div>
  )
}

function PipelinePerformance({ job, downloads }: { job: JobDetails; downloads: Downloads | null }) {
  const ms = job.processing_time_ms ?? 0
  const total = job.total_records ?? 0
  const rps = ms > 0 && total > 0 ? Math.round((total / ms) * 1000) : null
  const countries = Object.keys(job.country_stats).length
  const ruleCount = Object.values(job.validation_breakdown).reduce((a, b) => a + b, 0)
  const chunks = downloads?.chunks.length ?? 0

  return (
    <SectionCard title="Pipeline Performance" delay={60}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <PerfTile label="Processing Time" value={ms ? fmtMs(ms) : '—'} />
        <PerfTile label="Records / Second" value={rps ? rps.toLocaleString() : '—'} sub="rec/s" />
        <PerfTile label="Countries Detected" value={countries ? countries.toString() : '—'} />
        <PerfTile label="Validation Checks" value={ruleCount ? `${ruleCount.toLocaleString()}+` : '—'} />
        <PerfTile label="Chunks Generated" value={chunks ? chunks.toString() : '0'} />
      </div>
    </SectionCard>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
function WorkspaceDashboard() {
  const searchParams = useSearchParams()
  const jobId = searchParams.get('job_id')
  const isDemo = searchParams.get('demo') === 'true'

  const [job, setJob] = useState<JobDetails | null>(null)
  const [report, setReport] = useState<AIReport | null>(null)
  const [downloads, setDownloads] = useState<Downloads | null>(null)
  const [status, setStatus] = useState<JobStatus | 'loading'>('loading')
  const [error, setError] = useState('')
  const terminalRef = useRef(false)
  const [countryNames, setCountryNames] = useState<Record<string, string>>({})

  useEffect(() => {
    apiFetch('/api/rules')
      .then(r => r?.ok ? r.json() : [])
      .then((rules: Array<{ country_code: string; country_name: string }>) => {
        const map: Record<string, string> = {}
        rules.forEach(r => { map[r.country_code.toUpperCase()] = r.country_name })
        setCountryNames(map)
      })
      .catch(() => { })
  }, [])

  useEffect(() => {
    if (!isDemo) return
    const t = setTimeout(() => {
      import('@/lib/mock-data').then(({ DEMO_JOB, DEMO_REPORT, DEMO_DOWNLOADS }) => {
        setJob(DEMO_JOB as unknown as JobDetails)
        setReport(DEMO_REPORT as AIReport)
        setDownloads(DEMO_DOWNLOADS as unknown as Downloads)
        setStatus('completed')
        terminalRef.current = true
      })
    }, 800)
    return () => clearTimeout(t)
  }, [isDemo])

  const fetchJob = useCallback(async () => {
    if (isDemo) return
    if (!jobId) { setStatus('failed'); setError('No job_id in URL.'); return }
    try {
      const res = await apiFetch(`/api/jobs/${jobId}`)
      if (!res) return
      if (res.status === 404) { setStatus('failed'); setError(`Job ${jobId} not found.`); return }
      if (!res.ok) throw new Error(`Server ${res.status}`)
      const data: JobDetails = await res.json()
      setJob(data)
      setStatus(data.status)
      if (data.status === 'completed' || data.status === 'failed') terminalRef.current = true
    } catch (e) { console.error('fetchJob', e) }
  }, [jobId, isDemo])

  const fetchReport = useCallback(async () => {
    if (isDemo || !jobId) return
    try { const r = await apiFetch(`/api/jobs/${jobId}/report`); if (r?.ok) setReport(await r.json()) }
    catch { /* non-fatal */ }
  }, [jobId, isDemo])

  const fetchDownloads = useCallback(async () => {
    if (isDemo || !jobId) return
    try { const r = await apiFetch(`/api/jobs/${jobId}/downloads`); if (r?.ok) setDownloads(await r.json()) }
    catch { /* non-fatal */ }
  }, [jobId, isDemo])

  useEffect(() => {
    if (isDemo) return
    fetchJob()
    const id = setInterval(() => {
      if (terminalRef.current) { clearInterval(id); return }
      fetchJob()
    }, POLL_MS)
    return () => clearInterval(id)
  }, [fetchJob, isDemo])

  useEffect(() => {
    if (isDemo) return
    if (status === 'completed') { fetchReport(); fetchDownloads() }
  }, [status, fetchReport, fetchDownloads, isDemo])

  const qualityScore = report?.quality_score ?? null

  return (
    <div style={{ position: 'relative', minHeight: '100vh', paddingTop: 100, paddingBottom: 80, paddingInline: 20, zIndex: 2 }}>
      <div className="bg-grid" />
      <div className="spotlight" style={{ background: 'radial-gradient(800px circle at 50% 20%, rgba(155,107,255,0.07), transparent 60%)' }} />

      <div style={{ width: '100%', maxWidth: 880, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <h1 style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 28, fontWeight: 600, marginBottom: 10 }}>
            Validation Workspace
          </h1>
          {isDemo && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontFamily: "'IBM Plex Mono',monospace", fontSize: 11,
              color: 'var(--signal)', background: 'rgba(245,176,66,0.08)',
              padding: '4px 12px', borderRadius: 6, border: '1px solid rgba(245,176,66,0.25)',
              marginBottom: 10, letterSpacing: '0.06em', textTransform: 'uppercase',
            }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--signal)', boxShadow: '0 0 6px var(--signal)', display: 'inline-block' }} />
              Demo Mode
            </div>
          )}
          {!isDemo && jobId && (
            <div style={{
              display: 'inline-block', fontFamily: "'IBM Plex Mono',monospace", fontSize: 12,
              color: 'var(--mist)', background: 'rgba(255,255,255,0.04)',
              padding: '5px 12px', borderRadius: 6, border: '1px solid var(--line-soft)', marginBottom: 20,
            }}>{jobId}</div>
          )}
          <div><StatusBadge status={status} /></div>
        </div>

        {/* Pipeline tracker */}
        <div id="pipeline">
          {status !== 'loading' && <PipelineTracker status={status as JobStatus} />}
        </div>

        {/* Loading */}
        {status === 'loading' && (
          <div style={{ textAlign: 'center', paddingBlock: 60 }}>
            <div style={{ width: 44, height: 44, border: '3px solid var(--line)', borderTopColor: 'var(--refine)', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
            <p style={{ color: 'var(--mist)', fontSize: 14 }}>Connecting to validation pipeline…</p>
          </div>
        )}

        {/* In-progress */}
        {(status === 'queued' || status === 'processing') && (
          <FadeIn>
            <div style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid var(--line-soft)', borderRadius: 16, padding: '24px 20px', textAlign: 'center', color: 'var(--mist)', fontSize: 14, lineHeight: 1.7, marginBottom: 16 }}>
              {status === 'queued'
                ? 'Waiting in the Redis task queue for an available worker…'
                : 'Running Polars validation — checking phone formats, date rules, duplicates, and generating output files…'}
            </div>
          </FadeIn>
        )}

        {/* Failed */}
        {status === 'failed' && (
          <FadeIn>
            <div style={{ background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 16, padding: '24px 20px', textAlign: 'center', color: '#f87171', fontSize: 14, lineHeight: 1.7, marginBottom: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Pipeline failed</div>
              <div style={{ opacity: 0.8, fontSize: 13 }}>{error || 'An error occurred during processing.'}</div>
            </div>
          </FadeIn>
        )}

        {/* Completed dashboard */}
        {status === 'completed' && job && (
          <>
            {/* Processing Metrics */}
            <FadeIn delay={0}>
              <div style={{
                background: 'rgba(255,255,255,0.025)', border: '1px solid var(--line)',
                borderRadius: 20, padding: '28px 24px', marginBottom: 16,
              }}>
                <h3 style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--mist-dim)', marginBottom: 20 }}>
                  Processing Metrics
                </h3>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                  {qualityScore !== null && (
                    <div style={{ display: 'flex', justifyContent: 'center', paddingRight: 8 }}>
                      <QualityRing score={qualityScore} />
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', flex: 1 }}>
                    <MetricCard label="Total Records" rawValue={job.total_records ?? 0} accent="var(--refine)" />
                    <MetricCard label="Valid Records" rawValue={job.valid_records ?? 0} accent="#10b981" />
                    <MetricCard label="Invalid Records" rawValue={job.invalid_records ?? 0} accent="#f87171" />
                    {(job.total_records ?? 0) > 0 && job.valid_records !== null && (
                      <MetricCard
                        label="Pass Rate"
                        rawValue={Math.round((job.valid_records / (job.total_records ?? 1)) * 100)}
                        display={`${((job.valid_records / (job.total_records ?? 1)) * 100).toFixed(1)}%`}
                        accent="var(--ingest)"
                      />
                    )}
                  </div>
                </div>
              </div>
            </FadeIn>

            {/* Pipeline Performance */}
            <PipelinePerformance job={job} downloads={downloads} />

            {/* Country Analysis */}
            {Object.keys(job.country_stats).length > 0 && (
              <CountryAnalysisSection countryStats={job.country_stats} countryNames={countryNames} />
            )}

            {/* Architecture */}
            <div id="architecture">
              <SectionCard title="Processing Architecture" delay={80}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '24px 20px',
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 16,
                  position: 'relative',
                }}>
                  {[
                    { label: 'Upload', icon: <Upload size={22} style={{ color: 'var(--refine)' }} />, color: 'var(--refine)' },
                    { label: 'Redis Queue', icon: <Zap size={22} style={{ color: 'var(--signal)' }} />, color: 'var(--signal)' },
                    { label: 'Worker', icon: <Cpu size={22} style={{ color: 'var(--ingest)' }} />, color: 'var(--ingest)' },
                    { label: 'Validator', icon: <Check size={24} style={{ color: '#10b981' }} />, color: '#10b981' },
                    { label: 'Output', icon: <Package size={22} style={{ color: 'var(--mist)' }} />, color: 'var(--mist)' },
                  ].map((step, i) => (
                    <div key={step.label} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, flex: 1 }}>
                        <div style={{
                          width: 60,
                          height: 60,
                          borderRadius: 16,
                          background: step.label === 'Validator' ? 'rgba(16,185,129,0.15)' : `${step.color}10`,
                          border: step.label === 'Validator' ? '2px solid #10b981' : `1px solid ${step.color}35`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 26,
                          boxShadow: step.label === 'Validator' ? '0 0 18px rgba(16,185,129,0.3)' : 'none',
                          animation: step.label === 'Validator' ? 'pulseGlow 2s ease-in-out infinite' : 'none',
                        }}>
                          {step.icon}
                        </div>
                        <span style={{ fontSize: 12, color: step.label === 'Validator' ? '#10b981' : 'var(--mist)', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 }}>
                          {step.label}
                        </span>
                      </div>
                      {i < 4 && (
                        <div style={{
                          width: 32,
                          height: 2,
                          background: 'linear-gradient(90deg, var(--line), var(--refine))',
                          flexShrink: 0,
                          opacity: 0.5,
                          position: 'relative',
                          overflow: 'hidden',
                        }}>
                          <div style={{
                            position: 'absolute',
                            inset: 0,
                            background: 'linear-gradient(90deg, transparent, var(--refine), transparent)',
                            animation: 'flowPulse 1.8s ease-in-out infinite',
                          }} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Flow pills */}
                <div style={{
                  marginTop: 14,
                  padding: '12px 16px',
                  background: 'rgba(255,255,255,0.015)',
                  borderRadius: 10,
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 6,
                  alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--mist-dim)', fontFamily: "'IBM Plex Mono', monospace", marginRight: 4 }}>
                    Flow:
                  </span>
                  {['Upload file', 'Redis Queue (RQ)', 'Worker Process', 'Polars Validation', 'Clean/Error Output'].map((flowStep, i) => (
                    <span key={flowStep} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        padding: '4px 10px',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid var(--line)',
                        borderRadius: 20,
                        fontSize: 11,
                        color: 'var(--mist)',
                        fontFamily: "'IBM Plex Mono', monospace",
                      }}>
                        {flowStep}
                      </span>
                      {i < 4 && <span style={{ color: 'var(--mist-dim)', fontSize: 11 }}>→</span>}
                    </span>
                  ))}
                </div>
              </SectionCard>
            </div>

            {/* Rules */}
            <div id="rules">
              <SectionCard title="Validation Rules Applied" delay={90}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
                  {[
                    { label: 'Country Detection', value: 'Inferred from country_code column', icon: <Globe size={18} style={{ color: '#4c8dff' }} />, color: '#4c8dff' },
                    { label: 'Phone Regex', value: 'Country-specific pattern (e.g., IN: ^\\d{10}$)', icon: <Phone size={18} style={{ color: '#9b6bff' }} />, color: '#9b6bff' },
                    { label: 'Payment Modes', value: 'Allowed modes per country (UPI, CARD, etc.)', icon: <CreditCard size={18} style={{ color: '#38bdf8' }} />, color: '#38bdf8' },
                    { label: 'Date Format', value: 'Expected format (DD/MM/YYYY, MM/DD/YYYY, etc.)', icon: <Calendar size={18} style={{ color: '#f5b042' }} />, color: '#f5b042' },
                    { label: 'Amount Limits', value: 'Min/max amount validation (0.01-1,000,000.0)', icon: <DollarSign size={18} style={{ color: '#eab308' }} />, color: '#eab308' },
                    { label: 'Quantity Limits', value: 'Min/max quantity validation (1-1000)', icon: <BarChart2 size={18} style={{ color: '#10b981' }} />, color: '#10b981' },
                  ].map((rule) => (
                    <div key={rule.label} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 14,
                      padding: '16px 18px',
                      background: 'rgba(255,255,255,0.02)',
                      borderRadius: 12,
                      border: '1px solid rgba(255,255,255,0.06)',
                      borderLeft: `3px solid ${rule.color}`,
                      transition: 'all 0.2s ease',
                      cursor: 'default',
                    }}
                      onMouseEnter={(e) => {
                        const el = e.currentTarget as HTMLDivElement
                        el.style.background = `${rule.color}0a`
                        el.style.boxShadow = `0 0 16px ${rule.color}18`
                        el.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        const el = e.currentTarget as HTMLDivElement
                        el.style.background = 'rgba(255,255,255,0.02)'
                        el.style.boxShadow = 'none'
                        el.style.transform = 'translateY(0)'
                      }}
                    >
                      <div style={{
                        width: 38,
                        height: 38,
                        borderRadius: '50%',
                        background: `${rule.color}15`,
                        border: `1px solid ${rule.color}30`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 20,
                        flexShrink: 0,
                      }}>
                        {rule.icon}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#ffffff',
                          fontFamily: "'Space Grotesk', sans-serif",
                          marginBottom: 3,
                        }}>
                          {rule.label}
                        </div>
                        <div style={{
                          fontSize: 11,
                          color: 'rgba(255,255,255,0.45)',
                          lineHeight: 1.5,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>
                          {rule.value}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </div>

            {/* AI Insights */}
            <div id="insights">
              {report && <AIInsightsSection report={report} qualityScore={qualityScore ?? 0} countryNames={countryNames} />}
            </div>

            {/* Downloads */}
            {downloads && <DownloadCenter downloads={downloads} />}
          </>
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
        @keyframes pulse-dot {
          0%,100% { opacity:1; transform:scale(1); }
          50% { opacity:0.4; transform:scale(0.85); }
        }
        @keyframes flowPulse {
          0%,100% { opacity: 0.3; }
          50% { opacity: 0.7; }
        }
        @keyframes pulseGlow {
          0%,100% { box-shadow: 0 0 0 rgba(16, 185, 129, 0); }
          50% { box-shadow: 0 0 12px rgba(16, 185, 129, 0.4); }
        }
        @media (max-width: 768px) {
          .rules-grid { grid-template-columns: 1fr !important; }
        }
        @media (max-width: 600px) {
          div[style*="maxWidth: 880px"] { padding-inline: 12px !important; }
        }
      `}</style>
    </div>
  )
}

// ─── Page export ──────────────────────────────────────────────────────────────
export default function WorkspacePage() {
  return (
    <>
      <CustomCursor />
      <Navbar />
      <Suspense fallback={
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#0a0b0e', color: 'var(--mist)', fontFamily: 'sans-serif', fontSize: 14,
        }}>
          Loading workspace…
        </div>
      }>
        <WorkspaceDashboard />
      </Suspense>
    </>
  )
}