'use client'

import { useEffect, useRef } from 'react'

export default function CustomCursor() {
    const containerRef = useRef<HTMLDivElement>(null)
    const innerRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (window.matchMedia('(hover: none)').matches) return
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

        const container = containerRef.current
        const inner = innerRef.current
        if (!container || !inner) return

        let mx = -100
        let my = -100
        let isHovering = false

        const updateTransform = () => {
            container.style.transform = `translate3d(${mx}px, ${my}px, 0)`
            inner.style.transform = `translate(-50%, -50%) scale(${isHovering ? 1.5 : 1})`
            inner.style.opacity = isHovering ? '0.85' : '1'
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
            ref={containerRef}
            style={{
                position: 'fixed',
                left: 0,
                top: 0,
                pointerEvents: 'none',
                zIndex: 99999,
                transform: 'translate3d(-100px, -100px, 0)',
                willChange: 'transform',
            }}
        >
            <div
                ref={innerRef}
                style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: 'var(--refine)',
                    boxShadow: '0 0 8px var(--refine)',
                    transform: 'translate(-50%, -50%) scale(1)',
                    transition: 'transform 0.15s ease, opacity 0.15s ease',
                    mixBlendMode: 'normal',
                }}
            />
        </div>
    )
}

