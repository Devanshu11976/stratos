'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { EASE_OUT, motionDuration } from '@/lib/motion'

/* ── Node data ── */
const STACK_NODES = [
  { id: 'litestar',   label: 'Litestar',   role: 'API Layer',         desc: 'Async HTTP layer — receives file uploads and streams validation jobs to workers.',  col: 0, row: 1 },
  { id: 'msgspec',    label: 'msgspec',    role: 'Serialization',     desc: 'Zero-copy struct serialization. Encodes and decodes job payloads at native speed.',  col: 1, row: 0 },
  { id: 'polars',     label: 'Polars',     role: 'Processing Engine', desc: 'Chunk-streamed DataFrame engine. Validates millions of rows without loading into RAM.', col: 1, row: 1 },
  { id: 'pandera',    label: 'Pandera',    role: 'Schema Validation', desc: 'Enforces 190+ typed validation rules per country — phone, date, currency, IDs.',   col: 1, row: 2 },
  { id: 'postgresql', label: 'PostgreSQL', role: 'Storage',           desc: 'Stores job metadata, validation results, and country stats for every processed file.', col: 2, row: 0 },
  { id: 'redis',      label: 'Redis',      role: 'Queue',             desc: 'Async job queue — decouples upload from processing for non-blocking throughput.',    col: 2, row: 1 },
  { id: 'groq',       label: 'Groq API',   role: 'AI Intelligence',   desc: 'LLM analysis of error patterns — generates plain-language executive summaries.',    col: 2, row: 2 },
]

/* ── Graph constants ── */
const EDGES: [string, string][] = [
  ['litestar', 'msgspec'],
  ['litestar', 'polars'],
  ['litestar', 'pandera'],
  ['msgspec',  'postgresql'],
  ['polars',   'redis'],
  ['pandera',  'groq'],
  ['polars',   'postgresql'],
]

// Multiple independent pulse paths for denser activity
const PULSE_PATHS = [
  ['litestar', 'polars',     'redis'],
  ['litestar', 'msgspec',    'postgresql'],
  ['litestar', 'pandera',    'groq'],
  ['polars',   'postgresql'],
]

const COL_X: Record<number, number> = { 0: 80,  1: 300, 2: 520 }
const ROW_Y: Record<number, number> = { 0: 50,  1: 165, 2: 280 }
const NODE_W = 130
const NODE_H = 48
const SVG_W  = 680
const SVG_H  = 370

function getNodeCenter(id: string) {
  const n = STACK_NODES.find((n) => n.id === id)!
  return { x: COL_X[n.col] + NODE_W / 2, y: ROW_Y[n.row] + NODE_H / 2 }
}

/* ── Stat cards data ── */
const STATS = [
  { value: '190+', label: 'Validation Rules',    accent: '#4c8dff' },
  { value: '40+',  label: 'Countries Supported', accent: '#9b6bff' },
  { value: '∞',    label: 'Streaming Processing',accent: '#4c8dff' },
  { value: 'LLM',  label: 'AI Insight Generation', accent: '#9b6bff' },
  { value: 'Auto', label: 'Automatic Chunking',  accent: '#f5b042' },
  { value: 'BG',   label: 'Async Background Jobs', accent: '#f5b042' },
]

/* ── Pipeline step SVG icons ── */
const STEP_ICONS: Record<string, React.ReactNode> = {
  Upload: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  Validate: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <polyline points="9 12 11 14 15 10"/>
    </svg>
  ),
  Process: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 3 21 3 21 8"/>
      <line x1="4" y1="20" x2="21" y2="3"/>
      <polyline points="21 16 21 21 16 21"/>
      <line x1="15" y1="15" x2="21" y2="21"/>
    </svg>
  ),
  Store: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Analyze: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  Export: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
}

/* ── Pipeline flow steps ── */
const FLOW_STEPS = [
  { label: 'Upload',   color: '#4c8dff', desc: 'CSV or XLSX streamed chunk by chunk' },
  { label: 'Validate', color: '#f472b6', desc: '190+ rules checked per record' },
  { label: 'Process',  color: '#9b6bff', desc: 'Polars transforms and normalises data' },
  { label: 'Store',    color: '#38bdf8', desc: 'Results persisted to PostgreSQL' },
  { label: 'Analyze',  color: '#f5b042', desc: 'Groq generates quality insights' },
  { label: 'Export',   color: '#10b981', desc: 'Clean CSV, error report, chunks ready' },
]

/* ── Ambient particle ── */
function Particle({ delay, seed }: { delay: number; seed: number }) {
  const x   = 40 + (seed * 137.508) % (SVG_W - 80)
  const dy  = -25 - (seed * 53) % 35
  const dur = 3.5 + (seed % 3)
  return (
    <motion.circle
      cx={x}
      cy={ROW_Y[1] + 10 + (seed * 71) % 100}
      r={1.1}
      fill={seed % 3 === 0 ? '#f5b042' : seed % 2 === 0 ? '#4c8dff' : '#9b6bff'}
      initial={{ opacity: 0, y: 0 }}
      animate={{ opacity: [0, 0.4, 0], y: [0, dy] }}
      transition={{ duration: dur, delay, repeat: Infinity, ease: 'easeOut', repeatDelay: 1.5 }}
    />
  )
}

/* ── Single edge pulse ── */
function EdgePulse({ from, to, active, pathIdx }: { from: string; to: string; active: boolean; pathIdx: number }) {
  const a = getNodeCenter(from)
  const b = getNodeCenter(to)
  const colors = ['#4c8dff', '#9b6bff', '#f5b042', '#4c8dff']
  const col = colors[pathIdx % colors.length]
  return (
    <AnimatePresence>
      {active && (
        <motion.circle
          key={`${from}-${to}-${pathIdx}`}
          r={3.5}
          fill={col}
          filter="url(#pulseBlur)"
          initial={{ cx: a.x, cy: a.y, opacity: 0, scale: 0.3 }}
          animate={{ cx: b.x, cy: b.y, opacity: [0, 0.9, 0.9, 0], scale: [0.3, 1, 1, 0.3] }}
          exit={{ opacity: 0 }}
          transition={{ duration: motionDuration(0.78), ease: [0.4, 0, 0.2, 1] }}
        />
      )}
    </AnimatePresence>
  )
}

function StackNode({ node }: { node: (typeof STACK_NODES)[number] }) {
  const [hovered, setHovered] = useState(false)
  const x = COL_X[node.col]
  const y = ROW_Y[node.row]
  const tipW = 190
  const tipX = Math.min(Math.max(x + NODE_W / 2 - tipW / 2, 4), SVG_W - tipW - 4)
  // Show tooltip below nodes in top row so it doesn't clip outside SVG
  const tipBelow = y < 80
  const tipY = tipBelow ? y + NODE_H + 8 : y - 72

  // Pre-split desc into max 2 lines of ~34 chars each at word boundaries
  const words = node.desc.split(' ')
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > 34 && cur) {
      lines.push(cur.trim())
      cur = w
      if (lines.length === 2) break
    } else {
      cur = cur ? cur + ' ' + w : w
    }
  }
  if (lines.length < 2 && cur) lines.push(cur.trim())

  return (
    <motion.g
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileHover={{ y: -6 }}
      transition={{ type: 'spring', stiffness: 220, damping: 28 }}
      style={{ cursor: 'default' }}
    >
      {/* Card */}
      <motion.rect
        x={x} y={y} width={NODE_W} height={NODE_H} rx={10}
        fill={hovered ? 'rgba(155,107,255,0.10)' : 'rgba(255,255,255,0.035)'}
        stroke={hovered ? 'rgba(155,107,255,0.55)' : 'rgba(255,255,255,0.10)'}
        strokeWidth={1}
        filter={hovered ? 'url(#nodeGlow)' : undefined}
        style={{ transition: 'fill 0.25s ease, stroke 0.25s ease' }}
      />
      {/* Label */}
      <text
        x={x + NODE_W / 2} y={y + NODE_H / 2 - 5}
        textAnchor="middle" dominantBaseline="middle"
        fill={hovered ? '#e8eaf0' : '#c8cdd8'}
        fontFamily="'IBM Plex Mono', monospace" fontSize={12.5}
        style={{ userSelect: 'none' }}
      >
        {node.label}
      </text>
      {/* Role sub-label */}
      <text
        x={x + NODE_W / 2} y={y + NODE_H / 2 + 10}
        textAnchor="middle" dominantBaseline="middle"
        fill={hovered ? 'rgba(155,107,255,0.9)' : 'rgba(255,255,255,0.3)'}
        fontFamily="'IBM Plex Mono', monospace" fontSize={9}
        letterSpacing={0.8}
        style={{ userSelect: 'none', textTransform: 'uppercase' as const }}
      >
        {node.role}
      </text>

      {/* Tooltip */}
      <AnimatePresence>
        {hovered && (
          <motion.g key="tip"
            initial={{ opacity: 0, y: tipBelow ? -4 : 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: motionDuration(0.16), ease: 'easeOut' }}
          >
            <rect x={tipX} y={tipY} width={tipW} height={54} rx={8}
              fill="rgba(8,9,14,0.97)" stroke="rgba(155,107,255,0.28)" strokeWidth={1}
            />
            <text x={tipX + 10} y={tipY + 14}
              fill="#9b6bff" fontFamily="'IBM Plex Mono', monospace"
              fontSize={9} letterSpacing={1.2}
              style={{ textTransform: 'uppercase' as const }}
            >
              {node.role}
            </text>
            {lines.map((line, i) => (
              <text key={i} x={tipX + 10} y={tipY + 28 + i * 13}
                fill="#8a909e" fontFamily="'IBM Plex Mono', monospace" fontSize={10}
              >
                {line}
              </text>
            ))}
          </motion.g>
        )}
      </AnimatePresence>
    </motion.g>
  )
}

/* ── Stat card ── */
function StatCard({ value, label, accent, delay }: { value: string; label: string; accent: string; delay: number }) {
  const [hov, setHov] = useState(false)
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: motionDuration(0.5), delay, ease: EASE_OUT }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: '1 1 130px', minWidth: 120,
        padding: '18px 16px',
        borderRadius: 14,
        border: `1px solid ${hov ? `${accent}44` : 'rgba(255,255,255,0.07)'}`,
        background: hov ? `${accent}0d` : 'rgba(255,255,255,0.025)',
        backdropFilter: 'blur(8px)',
        textAlign: 'center',
        transition: 'all 0.22s ease',
        transform: hov ? 'translateY(-4px)' : 'translateY(0)',
        boxShadow: hov ? `0 8px 28px ${accent}18` : '0 2px 12px rgba(0,0,0,0.2)',
        cursor: 'default',
      }}
    >
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: 20, fontWeight: 700,
        color: accent, marginBottom: 6, letterSpacing: '-0.01em',
      }}>
        {value}
      </div>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: 10,
        color: 'var(--mist-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', lineHeight: 1.4,
      }}>
        {label}
      </div>
    </motion.div>
  )
}

/* ── Pipeline flow step ── */
function FlowStep({ step, idx }: { step: typeof FLOW_STEPS[number]; idx: number }) {
  const [hov, setHov] = useState(false)
  const icon = STEP_ICONS[step.label]
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: motionDuration(0.45), delay: idx * 0.11, ease: EASE_OUT }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: '1 1 0',
        minWidth: 110,
        maxWidth: 180,
        padding: '18px 14px',
        borderRadius: 12,
        textAlign: 'center',
        border: `1px solid ${hov ? step.color : step.color + '30'}`,
        background: hov ? step.color + '18' : step.color + '0a',
        backdropFilter: 'blur(8px)',
        transition: 'all 0.25s ease',
        transform: hov ? 'translateY(-4px)' : 'translateY(0)',
        cursor: 'default',
        boxShadow: hov ? `0 10px 28px ${step.color}28` : 'none',
      }} className="flow-step-card"
    >
      {/* SVG icon, colored to match the step */}
      <div style={{
        color: hov ? step.color : step.color + 'bb',
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        marginBottom: 10, transition: 'color 0.25s ease',
        height: 24,
      }}>
        {icon}
      </div>
      <div style={{
        fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 600,
        color: hov ? step.color : 'var(--paper)', transition: 'color 0.25s ease',
        marginBottom: 6,
      }}>
        {step.label}
      </div>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: 9.5,
        color: 'var(--mist-dim)', lineHeight: 1.55,
      }}>
        {step.desc}
      </div>
    </motion.div>
  )
}

/* ── Main export ── */
export default function Architecture() {
  // Multiple independent pulse cursors — one per PULSE_PATH
  const [pulseSteps, setPulseSteps] = useState(PULSE_PATHS.map(() => 0))

  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = []
    const intervals: ReturnType<typeof setInterval>[] = []

    PULSE_PATHS.forEach((path, pi) => {
      const t = setTimeout(() => {
        const id = setInterval(() => {
          setPulseSteps((prev) => {
            const next = [...prev]
            next[pi] = (next[pi] + 1) % (path.length - 1)
            return next
          })
        }, 900 + pi * 180)
        intervals.push(id)
      }, pi * 420)
      timeouts.push(t)
    })

    return () => {
      timeouts.forEach(clearTimeout)
      intervals.forEach(clearInterval)
    }
  }, [])

  return (
    <section
      id="architecture"
      style={{
        position: 'relative',
        zIndex: 2,
        paddingBlock: 'clamp(80px, 10vw, 140px)',
        borderTop: '1px solid var(--line-soft)',
        overflow: 'hidden',
      }}
    >
      {/* Multi-layered ambient glow */}
      <div aria-hidden style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: [
          'radial-gradient(ellipse 700px 300px at 50% 40%, rgba(76,141,255,0.055) 0%, transparent 70%)',
          'radial-gradient(ellipse 400px 200px at 30% 60%, rgba(155,107,255,0.04) 0%, transparent 65%)',
          'radial-gradient(ellipse 300px 200px at 75% 55%, rgba(245,176,66,0.03) 0%, transparent 60%)',
        ].join(','),
      }} />

      <div style={{ width: '100%', maxWidth: 1280, margin: '0 auto', paddingInline: 32 }}>

        {/* ── Header ── */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: motionDuration(0.7), ease: EASE_OUT }}
          style={{ textAlign: 'center', marginBottom: 48 }}
        >
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 11,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: 'var(--refine)', marginBottom: 12,
          }}>
            Architecture
          </div>
          <h2 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 'clamp(1.4rem, 2.8vw, 2.1rem)',
            fontWeight: 600, letterSpacing: '0.03em', color: 'var(--paper)', marginBottom: 16,
          }}>
            POWERING THE VALIDATION ENGINE
          </h2>
          <p style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 'clamp(14px, 1.5vw, 16px)',
            color: 'var(--mist)', maxWidth: 620, margin: '0 auto', lineHeight: 1.7,
          }}>
            Every uploaded dataset flows through a streaming validation pipeline before being
            transformed into clean data, downloadable reports, and AI-powered insights.
          </p>
        </motion.div>

        {/* ── Stat cards ── */}
        <div style={{
          display: 'flex', gap: 12, flexWrap: 'wrap',
          justifyContent: 'center', marginBottom: 56,
        }}>
          {STATS.map((s, i) => (
            <StatCard key={s.label} {...s} delay={i * 0.06} />
          ))}
        </div>

        {/* ── Architecture graph ── */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 56 }} className="architecture-graph-container">
          <svg
            viewBox={`0 0 ${SVG_W} ${SVG_H}`}
            width="100%"
            style={{ maxWidth: SVG_W, overflow: 'visible' }}
            aria-label="Stack architecture diagram"
            className="architecture-svg"
          >
            <defs>
              <filter id="pulseBlur" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="2.8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="nodeGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="7" result="blur" />
                <feFlood floodColor="#9b6bff" floodOpacity="0.22" result="color" />
                <feComposite in="color" in2="blur" operator="in" result="glow" />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%"   stopColor="#4c8dff" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#9b6bff" stopOpacity="0.3" />
              </linearGradient>
            </defs>

            {/* Particles */}
            {Array.from({ length: 18 }, (_, i) => (
              <Particle key={i} seed={i + 1} delay={i * 0.36} />
            ))}

            {/* Edges */}
            {EDGES.map(([fromId, toId]) => {
              const a  = getNodeCenter(fromId)
              const b  = getNodeCenter(toId)
              const mx = (a.x + b.x) / 2
              const my = (a.y + b.y) / 2 - 16
              return (
                <path
                  key={`${fromId}-${toId}`}
                  d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                  fill="none" stroke="url(#edgeGrad)"
                  strokeWidth={1} strokeDasharray="3 5"
                />
              )
            })}

            {/* Multi-path pulses */}
            {PULSE_PATHS.map((path, pi) =>
              path.slice(0, -1).map((fromId, si) => (
                <EdgePulse
                  key={`p${pi}-s${si}`}
                  from={fromId}
                  to={path[si + 1]}
                  active={pulseSteps[pi] === si}
                  pathIdx={pi}
                />
              ))
            )}

            {/* Nodes */}
            {STACK_NODES.map((node) => (
              <StackNode key={node.id} node={node} />
            ))}
          </svg>
        </div>

        {/* ── Pipeline flow ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: motionDuration(0.6), ease: EASE_OUT }}
        >
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 11,
            letterSpacing: '0.14em', textTransform: 'uppercase',
            color: 'var(--mist-dim)', textAlign: 'center', marginBottom: 24,
          }}>
            Pipeline Flow
          </div>
          <div style={{
            display: 'flex',
            gap: 0,
            alignItems: 'stretch',
            justifyContent: 'center',
            flexWrap: 'nowrap',
            overflowX: 'auto',
            paddingBottom: 4,
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'thin',
          }} className="pipeline-flow-container">
            {FLOW_STEPS.map((step, i) => (
              <div key={step.label} style={{ display: 'flex', alignItems: 'center', minWidth: 0, flexShrink: 0 }} className="pipeline-flow-step-wrapper">
                <FlowStep step={step} idx={i} />
                {i < FLOW_STEPS.length - 1 && (
                  <div style={{
                    color: 'var(--mist-dim)', fontSize: 14, padding: '0 6px',
                    flexShrink: 0, userSelect: 'none', opacity: 0.5,
                  }}>
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.div>

      </div>

      <style>{`
        @media (max-width: 768px) {
          .pipeline-flow-container {
            flex-wrap: wrap !important;
            justify-content: center !important;
            gap: 12px !important;
          }
          .flow-step-card {
            flex: 1 1 140px !important;
            max-width: 160px !important;
            min-width: 140px !important;
          }
          .architecture-graph-container {
            overflow: visible !important;
            padding-bottom: 0 !important;
            margin-inline: 0 !important;
            padding-inline: 0 !important;
            display: flex !important;
            justify-content: center !important;
          }
          .architecture-svg {
            min-width: auto !important;
            max-width: 140% !important;
            width: 140% !important;
            height: auto !important;
            transform: none !important;
          }
        }
        @media (max-width: 480px) {
          .pipeline-flow-container {
            flex-direction: column !important;
            align-items: stretch !important;
          }
          .flow-step-card {
            flex: 1 1 auto !important;
            max-width: 100% !important;
            min-width: 100% !important;
            width: 100% !important;
          }
        }
      `}</style>
    </section>
  )
}
