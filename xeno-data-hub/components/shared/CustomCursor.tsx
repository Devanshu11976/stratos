'use client'

import { useEffect, useRef } from 'react'

export default function CustomCursor() {
    const dotRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (window.matchMedia('(hover: none)').matches) return
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

        const dot = dotRef.current
        if (!dot) return

        let mx = -100
        let my = -100
        let isHovering = false

        const updateTransform = () => {
            dot.style.left = `${mx}px`
            dot.style.top = `${my}px`
            dot.style.transform = `translate(-50%, -50%) scale(${isHovering ? 2.5 : 1})`
            dot.style.opacity = isHovering ? '0.9' : '1'
        }

        const onMove = (e: MouseEvent) => {
            mx = e.clientX
            my = e.clientY
            updateTransform()
        }

        const onOver = (e: MouseEvent) => {
            const target = (e.target as Element).closest(
                'a, button, [role="button"], input, [data-cursor-hover]'
            )
            const next = !!target
            if (next !== isHovering) {
                isHovering = next
                updateTransform()
            }
        }

        window.addEventListener('mousemove', onMove, { passive: true })
        document.body.addEventListener('mouseover', onOver, { passive: true })

        return () => {
            window.removeEventListener('mousemove', onMove)
            document.body.removeEventListener('mouseover', onOver)
        }
    }, [])

    return (
        <div
            ref={dotRef}
            style={{
                position: 'fixed',
                pointerEvents: 'none',
                zIndex: 99999,
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--refine)',
                boxShadow: '0 0 8px var(--refine)',
                transform: 'translate(-50%, -50%)',
                transition: 'transform 0.15s ease, opacity 0.15s ease',
                mixBlendMode: 'normal',
                left: -100,
                top: -100,
                outline: '1px solid var(--refine)',
                outlineOffset: '2px',
            }}
        />
    )
}
