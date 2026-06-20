'use client'

import { useState } from 'react'

const DEMO_EMAIL = 'sanmatijain2204@gmail.com'

const NAV_LINKS = ['Pipeline', 'Architecture', 'Rules', 'Insights'] as const

export default function Navbar() {
    const [menuOpen, setMenuOpen] = useState(false)

    return (
        <nav
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                zIndex: 50,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '18px clamp(16px, 4vw, 48px)',
                background: 'rgba(10,11,14,0.55)',
                backdropFilter: 'blur(16px) saturate(140%)',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
            }}
        >
            {/* Logo */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    fontSize: 15,
                    fontWeight: 600,
                    letterSpacing: '0.02em',
                }}
            >
                <span
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, var(--ingest), var(--signal))',
                        boxShadow: '0 0 12px rgba(245,176,66,0.6)',
                        display: 'inline-block',
                        flexShrink: 0,
                    }}
                />
                XENO{' '}
                <span
                    className="logo-subtext"
                    style={{ color: 'var(--mist)', fontWeight: 400 }}
                >
                    / Data Intelligence Hub
                </span>
            </div>

            {/* Nav links — desktop */}
            <div
                className="nav-links-desktop"
                data-cursor-no-scale
                style={{
                    display: 'flex',
                    gap: 36,
                    fontSize: 14,
                    color: 'var(--mist)',
                }}
            >
                {NAV_LINKS.map((link) => (
                    <button
                        key={link}
                        type="button"
                        onClick={() => document.getElementById(link.toLowerCase())?.scrollIntoView({ behavior: 'smooth' })}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--mist)',
                            fontSize: 14,
                            cursor: 'pointer',
                            padding: 0,
                            transition: 'color 0.2s',
                        }}
                        onMouseEnter={(e) =>
                            ((e.target as HTMLElement).style.color = 'var(--paper)')
                        }
                        onMouseLeave={(e) =>
                            ((e.target as HTMLElement).style.color = 'var(--mist)')
                        }
                    >
                        {link}
                    </button>
                ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {/* Mobile menu toggle */}
                <button
                    type="button"
                    className="nav-menu-toggle"
                    aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                    aria-expanded={menuOpen}
                    onClick={() => setMenuOpen((o) => !o)}
                    style={{
                        display: 'none',
                        background: 'transparent',
                        border: '1px solid var(--line)',
                        borderRadius: 8,
                        padding: '8px 10px',
                        color: 'var(--mist)',
                        fontSize: 13,
                        cursor: 'pointer',
                    }}
                >
                    {menuOpen ? '✕' : '☰'}
                </button>

                {/* Book a demo → mailto */}
                <a
                    href={`mailto:${DEMO_EMAIL}?subject=Xeno%20Data%20Intelligence%20Hub%20Demo%20Request`}
                    aria-label="Book a demo — send us an email"
                    style={{
                        fontSize: 13.5,
                        fontWeight: 500,
                        padding: '9px 18px',
                        borderRadius: 8,
                        background:
                            'linear-gradient(135deg, rgba(76,141,255,0.18), rgba(155,107,255,0.18))',
                        border: '1px solid rgba(255,255,255,0.14)',
                        transition: 'border-color 0.2s',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                    }}
                    onMouseEnter={(e) =>
                        ((e.currentTarget as HTMLElement).style.borderColor =
                            'rgba(255,255,255,0.3)')
                    }
                    onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.borderColor =
                            'rgba(255,255,255,0.14)')
                    }
                >
                    Book a demo
                </a>
            </div>

            {/* Mobile nav drawer */}
            {menuOpen && (
                <div
                    className="nav-mobile-menu"
                    data-cursor-no-scale
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        background: 'rgba(10,11,14,0.95)',
                        backdropFilter: 'blur(16px)',
                        borderBottom: '1px solid rgba(255,255,255,0.05)',
                        padding: '16px clamp(16px, 4vw, 48px)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 16,
                    }}
                >
                    {NAV_LINKS.map((link) => (
                        <button
                            key={link}
                            type="button"
                            onClick={() => {
                                document.getElementById(link.toLowerCase())?.scrollIntoView({ behavior: 'smooth' })
                                setMenuOpen(false)
                            }}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'var(--mist)',
                                fontSize: 15,
                                cursor: 'pointer',
                                padding: 0,
                                textAlign: 'left',
                            }}
                        >
                            {link}
                        </button>
                    ))}
                </div>
            )}

            <style>{`
        @media (max-width: 860px) {
          .nav-links-desktop { display: none !important; }
          .nav-menu-toggle { display: block !important; }
        }
        @media (max-width: 640px) {
          .logo-subtext { display: none !important; }
        }
      `}</style>
        </nav>
    )
}
