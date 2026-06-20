'use client'

import { useEffect, useRef, useState, memo, useCallback } from 'react'
import { motion, AnimatePresence, useInView } from 'framer-motion'
import { EASE_OUT, motionDuration } from '@/lib/motion'

/* ─────────────────────────────────────────
   SpotlightLabel — cursor-reactive radial glow on titles
   ───────────────────────────────────────── */
const SpotlightLabel = memo(function SpotlightLabel({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLSpanElement>(null)
  const glowRef = useRef<HTMLSpanElement>(null)
  const cachedRect = useRef<DOMRect | null>(null)
  const [hovered, setHovered] = useState(false)

  const onEnter = useCallback(() => {
    if (ref.current) cachedRect.current = ref.current.getBoundingClientRect()
    setHovered(true)
  }, [])

  const onMove = useCallback((e: React.MouseEvent<HTMLSpanElement>) => {
    if (!glowRef.current || !cachedRect.current) return
    const rect = cachedRect.current
    glowRef.current.style.background = `radial-gradient(ellipse 110px 70px at ${e.clientX - rect.left}px ${e.clientY - rect.top}px, rgba(76,141,255,0.18) 0%, rgba(155,107,255,0.10) 55%, transparent 80%)`
  }, [])

  const onLeave = useCallback(() => {
    setHovered(false)
    cachedRect.current = null
  }, [])

  return (
    <span
      ref={ref}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onMouseMove={onMove}
      style={{ position: 'relative', display: 'inline' }}
    >
      {children}
      <span
        ref={glowRef}
        aria-hidden
        style={{
          position: 'absolute',
          inset: '-14px -20px',
          borderRadius: 10,
          pointerEvents: 'none',
          opacity: hovered ? 1 : 0,
          transition: 'opacity 0.3s ease',
          willChange: 'background',
        }}
      />
    </span>
  )
})

const STAGES = [
  {
    num: '01',
    title: 'Ingest',
    desc: 'Drop in a CSV or Excel file, a few rows or a few million. Xeno streams it chunk by chunk — nothing loads fully into memory.',
    color: 'var(--ingest)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <circle cx="14" cy="30" r="3" fill="var(--ingest)" opacity="0.9" />
        <circle cx="26" cy="18" r="2.4" fill="var(--ingest)" opacity="0.7" />
        <circle cx="22" cy="44" r="2" fill="var(--ingest)" opacity="0.6" />
        <circle cx="38" cy="32" r="2.6" fill="var(--ingest)" opacity="0.8" />
        <path d="M50 30H88" stroke="var(--ingest)" strokeWidth="1.4" strokeDasharray="2 4" opacity="0.6" />
        <path d="M80 24L88 30L80 36" stroke="var(--ingest)" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    num: '02',
    title: 'Validate',
    desc: 'Every order, product, payment, phone number, and timestamp is checked against rules written for real-world messiness, not clean test data.',
    color: 'var(--ingest)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <rect x="20" y="14" width="14" height="14" rx="2" stroke="var(--refine)" strokeWidth="1.4" />
        <rect x="38" y="14" width="14" height="14" rx="2" fill="rgba(245,176,66,0.15)" stroke="var(--signal)" strokeWidth="1.4" />
        <rect x="56" y="14" width="14" height="14" rx="2" stroke="var(--refine)" strokeWidth="1.4" />
        <rect x="20" y="32" width="14" height="14" rx="2" stroke="var(--refine)" strokeWidth="1.4" />
        <rect x="38" y="32" width="14" height="14" rx="2" stroke="var(--refine)" strokeWidth="1.4" />
        <rect x="56" y="32" width="14" height="14" rx="2" fill="rgba(245,176,66,0.15)" stroke="var(--signal)" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    num: '03',
    title: 'Clean',
    desc: "Malformed rows are repaired where the fix is unambiguous, and set aside where it isn't. You see exactly what changed and why, row by row.",
    color: 'var(--refine)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <path d="M16 30H40" stroke="var(--refine)" strokeWidth="1.4" opacity="0.5" />
        <circle cx="44" cy="30" r="9" stroke="var(--refine)" strokeWidth="1.4" />
        <path d="M40 30L44 34L50 26" stroke="var(--signal)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M54 30H84" stroke="var(--refine)" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    num: '04',
    title: 'Enrich',
    desc: 'Country codes are resolved, currencies normalized, and duplicate orders linked together — restoring context the source file never had.',
    color: 'var(--refine)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <circle cx="30" cy="30" r="10" stroke="var(--refine)" strokeWidth="1.4" />
        <path d="M40 30H58" stroke="var(--refine)" strokeWidth="1.4" strokeDasharray="2 3" />
        <circle cx="66" cy="30" r="13" stroke="var(--signal)" strokeWidth="1.6" />
        <path d="M61 30L71 30M66 25L66 35" stroke="var(--signal)" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    num: '05',
    title: 'Analyze',
    desc: 'Groq reviews the dataset as a whole and writes a plain-language quality report — patterns and root causes, not just a list of broken rows.',
    color: 'var(--signal)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <rect x="20" y="38" width="8" height="10" fill="var(--signal)" opacity="0.5" />
        <rect x="32" y="28" width="8" height="20" fill="var(--signal)" opacity="0.7" />
        <rect x="44" y="16" width="8" height="32" fill="var(--signal)" />
        <rect x="56" y="30" width="8" height="18" fill="var(--signal)" opacity="0.7" />
        <rect x="68" y="22" width="8" height="26" fill="var(--signal)" opacity="0.85" />
      </svg>
    ),
  },
  {
    num: '06',
    title: 'Trust',
    desc: 'A clean export, an error report, and chunked files land wherever your downstream systems expect them. Ready to reconcile, not just review.',
    color: 'var(--signal)',
    visual: (
      <svg viewBox="0 0 100 60" fill="none" style={{ width: '100%', height: '100%' }}>
        <rect x="36" y="22" width="28" height="22" rx="4" stroke="var(--signal)" strokeWidth="1.6" />
        <path d="M42 22V17a8 8 0 0116 0v5" stroke="var(--signal)" strokeWidth="1.6" />
        <circle cx="50" cy="33" r="2.4" fill="var(--signal)" />
      </svg>
    ),
  },
]

/* ─────────────────────────────────────────
   VisualCard — glassmorphism + hover lift + border glow
   ───────────────────────────────────────── */
const VisualCard = memo(function VisualCard({
  visual,
  stageColor,
  isInView,
  index,
}: {
  visual: React.ReactNode
  stageColor: string
  isInView: boolean
  index: number
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      className="stage-visual"
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      initial={{ opacity: 0, scale: 0.88 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      whileHover={{ y: -5 }}
      transition={{
        opacity: { duration: 0.4, ease: EASE_OUT },
        scale: { duration: 0.4, ease: EASE_OUT },
        y: { type: 'spring', stiffness: 260, damping: 22 },
      }}
      style={{
        height: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: hovered ? 'rgba(255,255,255,0.045)' : 'rgba(255,255,255,0.02)',
        border: '1px solid',
        borderColor: hovered ? `rgba(155,107,255,0.28)` : 'var(--line)',
        borderRadius: 14,
        padding: '10px 16px',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
        boxShadow: hovered
          ? `0 8px 28px rgba(0,0,0,0.35), 0 0 0 1px rgba(155,107,255,0.15), 0 0 20px rgba(76,141,255,0.08)`
          : '0 2px 12px rgba(0,0,0,0.2)',
        transition: 'background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease',
        cursor: 'default',
        willChange: 'transform',
        transform: 'translateZ(0)',
      }}
    >
      {visual}
    </motion.div>
  )
})

/* ─────────────────────────────────────────
   Stage row — scan line + spotlight title
   ───────────────────────────────────────── */
const Stage = memo(function Stage({ stage, index }: { stage: (typeof STAGES)[0]; index: number }) {
  const ref = useRef<HTMLDivElement>(null)
  // Increased margin from -15% to -40% to trigger animations much earlier
  const isInView = useInView(ref, { once: true, margin: '-40% 0px', amount: 0.1 })
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      ref={ref}
      className="stage-row"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      initial={{ opacity: 0, x: -32 }}
      animate={isInView ? { opacity: 1, x: 0 } : {}}
      // Reduced duration from 0.65s to 0.4s, removed delay
      transition={{ duration: 0.4, ease: EASE_OUT }}
      style={{
        position: 'relative',
        overflow: 'hidden',
        display: 'grid',
        gridTemplateColumns: '96px 1fr 220px',
        gap: 40,
        alignItems: 'center',
        paddingBlock: 48,
        borderTop: '1px solid var(--line-soft)',
        willChange: 'transform',
        transform: 'translateZ(0)',
      }}
    >
      {/* ── Scan line — simplified background wash ── */}
      <AnimatePresence mode="wait">
        {hovered && (
          <motion.span
            aria-hidden
            key="scan-bg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'linear-gradient(90deg, rgba(76,141,255,0.055) 0%, rgba(155,107,255,0.055) 60%, transparent 100%)',
              pointerEvents: 'none',
            }}
          />
        )}
      </AnimatePresence>

      {/* ── Scan line — simplified top 1px edge ── */}
      <AnimatePresence mode="wait">
        {hovered && (
          <motion.span
            aria-hidden
            key="scan-line"
            initial={{ scaleX: 0, originX: 0 }}
            animate={{ scaleX: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: 1,
              background:
                'linear-gradient(90deg, rgba(76,141,255,0.45) 0%, rgba(155,107,255,0.45) 60%, transparent 100%)',
              pointerEvents: 'none',
              willChange: 'transform',
            }}
          />
        )}
      </AnimatePresence>

      {/* Stage number + dot */}
      <div
        style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 14,
          color: 'var(--mist-dim)',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          position: 'relative',
          zIndex: 2,
        }}
      >
        <motion.div
          animate={
            isInView
              ? {
                  scale: [1, 1.2, 1],
                  boxShadow: [
                    `0 0 0px ${stage.color}`,
                    `0 0 12px ${stage.color}`,
                    `0 0 8px ${stage.color}`,
                  ],
                }
              : {}
          }
          // Reduced duration from 0.8s to 0.4s, removed delay
          transition={{ duration: 0.4, ease: 'easeOut' }}
          style={{
            width: 13,
            height: 13,
            borderRadius: '50%',
            border: `2px solid ${isInView ? stage.color : 'var(--mist-dim)'}`,
            background: isInView ? stage.color : 'var(--void)',
            flexShrink: 0,
            transition: 'all 0.3s ease',
            willChange: 'transform',
          }}
        />
        {stage.num}
      </div>

      {/* Body */}
      <div style={{ position: 'relative', zIndex: 2 }}>
        <motion.h3
          initial={{ opacity: 0, y: 12 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          // Reduced duration from 0.5s to 0.35s, removed delay
          transition={{ duration: 0.35, ease: EASE_OUT }}
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 22,
            fontWeight: 600,
            marginBottom: 10,
            willChange: 'transform',
          }}
        >
          <SpotlightLabel>{stage.title}</SpotlightLabel>
        </motion.h3>
        <motion.p
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          // Reduced duration from 0.5s to 0.35s, reduced delay
          transition={{ duration: 0.35, delay: 0.05 }}
          style={{
            color: 'var(--mist)',
            fontSize: 15,
            lineHeight: 1.65,
            maxWidth: 520,
            willChange: 'transform',
          }}
        >
          {stage.desc}
        </motion.p>
      </div>

      {/* Visual card */}
      <div style={{ position: 'relative', zIndex: 2 }}>
        <VisualCard
          visual={stage.visual}
          stageColor={stage.color}
          isInView={isInView}
          index={index}
        />
      </div>
    </motion.div>
  )
}

const Pipeline = memo(function Pipeline() {
  const railRef = useRef<HTMLDivElement>(null)
  const cometRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const wrap = railRef.current
    const comet = cometRef.current
    if (!wrap || !comet) return

    let ticking = false
    let cachedHeight = 0
    let cachedTop = 0

    const measure = () => {
      const rect = wrap.getBoundingClientRect()
      cachedHeight = rect.height
      // Cache the absolute position relative to document
      cachedTop = rect.top + window.scrollY
    }

    const updateComet = () => {
      if (!cometRef.current) return
      const viewportCenter = window.scrollY + (window.innerHeight * 0.5)
      // Calculate progress using cached values and window.scrollY
      let progress = (viewportCenter - cachedTop) / cachedHeight
      progress = Math.max(0, Math.min(1, progress))
      cometRef.current.style.top = `${progress * cachedHeight}px`
      ticking = false
    }

    const onScroll = () => {
      if (!ticking) {
        ticking = true
        requestAnimationFrame(updateComet)
      }
    }

    const onResize = () => {
      measure()
      if (!ticking) {
        ticking = true
        requestAnimationFrame(updateComet)
      }
    }

    measure()
    updateComet()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onResize, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  const headerRef = useRef<HTMLDivElement>(null)
  // Increased margin from -10% to -30% to trigger animations earlier
  const headerInView = useInView(headerRef, { once: true, margin: '-30% 0px', amount: 0.1 })

  return (
    <section
      id="pipeline"
      style={{
        position: 'relative',
        zIndex: 2,
        paddingBlock: 'clamp(80px, 12vw, 160px)',
        overflow: 'hidden',
        willChange: 'transform',
        transform: 'translateZ(0)',
      }}
    >
      <div
        ref={railRef}
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 1280,
          margin: '0 auto',
          paddingInline: 'clamp(20px, 4vw, 32px)',
        }}
      >
        {/* Rail track line */}
        <div
          style={{
            position: 'absolute',
            left: 'clamp(20px, 4vw, 32px)',
            top: 0,
            bottom: 0,
            width: 1,
            background:
              'linear-gradient(to bottom, transparent, var(--line) 10%, var(--line) 90%, transparent)',
          }}
        />

        {/* Comet — scroll-driven glow dot on the rail */}
        <div
          ref={cometRef}
          style={{
            position: 'absolute',
            left: 'clamp(20px, 4vw, 32px)',
            top: 0,
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: 'var(--refine)',
            boxShadow: '0 0 14px 4px var(--refine)',
            transform: 'translate(-50%, -50%)',
            zIndex: 3,
            pointerEvents: 'none',
            willChange: 'top',
          }}
        />

        {/* Head */}
        <motion.div
          ref={headerRef}
          initial={{ opacity: 0, y: 32 }}
          animate={headerInView ? { opacity: 1, y: 0 } : {}}
          // Reduced duration from 0.8s to 0.5s
          transition={{ duration: 0.5, ease: EASE_OUT }}
          style={{ 
            maxWidth: 600, 
            marginBottom: 88, 
            paddingLeft: 'clamp(24px, 5vw, 56px)',
            willChange: 'transform',
            transform: 'translateZ(0)',
          }}
        >
          <div
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 12.5,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--refine)',
              marginBottom: 18,
            }}
          >
            The pipeline
          </div>
          <h2
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 'clamp(1.9rem, 3.6vw, 2.8rem)',
              fontWeight: 600,
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
            }}
          >
            Six stages stand between a messy export and a number you can report on.
          </h2>
          <p
            style={{
              marginTop: 18,
              color: 'var(--mist)',
              fontSize: 16,
              lineHeight: 1.65,
              maxWidth: 560,
            }}
          >
            Every file moves through the same ordered path — nothing skipped, nothing assumed.
          </p>
        </motion.div>

        {/* Stages */}
        <div style={{ paddingLeft: 'clamp(24px, 5vw, 56px)' }}>
          {STAGES.map((stage, i) => (
            <Stage key={stage.num} stage={stage} index={i} />
          ))}
          {/* Bottom border on last stage */}
          <div style={{ borderBottom: '1px solid var(--line-soft)', height: 0 }} />
        </div>
      </div>

      <style>{`
        @media (max-width: 860px) {
          .stage-row {
            grid-template-columns: 72px 1fr !important;
            gap: 20px !important;
          }
          .stage-visual { display: none !important; }
        }
      `}</style>
    </section>
  )
})

export default Pipeline
