'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

interface ValidationCoreProps {
    intensity?: number
}

export default function ValidationCore({ intensity = 0 }: ValidationCoreProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const intensityRef = useRef(intensity)

    useEffect(() => {
        intensityRef.current = intensity
    }, [intensity])

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

        let animId = 0
        let renderer: THREE.WebGLRenderer | null = null
        let scene: THREE.Scene | null = null
        let camera: THREE.PerspectiveCamera | null = null
        let points: THREE.Points | null = null
        let geometry: THREE.BufferGeometry | null = null
        let material: THREE.PointsMaterial | null = null
        let innerRingGeom: THREE.TorusGeometry | null = null
        let innerRingMat: THREE.MeshBasicMaterial | null = null
        let middleRingGeom: THREE.TorusGeometry | null = null
        let middleRingMat: THREE.MeshBasicMaterial | null = null
        let outerRingGeom: THREE.TorusGeometry | null = null
        let outerRingMat: THREE.MeshBasicMaterial | null = null
        let reactorGroup: THREE.Group | null = null
        let innerRing: THREE.Mesh | null = null
        let middleRing: THREE.Mesh | null = null
        let outerRing: THREE.Mesh | null = null

        let grid: Float32Array
        let noisePhase: Float32Array
        let baseX: Float32Array
        let baseY: Float32Array
        let baseZ: Float32Array
        let speed: Float32Array
        let fadeOut: Float32Array
        let resetY: Float32Array
        let resetZ: Float32Array
        let COUNT = 0

        let orderFactor = 0
        let targetOrder = 0
        let mouseX = 0
        let mouseY = 0
        let t0 = performance.now()
        let disposed = false

        let cachedCanvasW = 0
        let cachedCanvasH = 0
        let coreX = 0
        let coreY = 0
        let needsLayoutRefresh = true

        let removeScrollEnd: (() => void) | null = null
        let removeResize: (() => void) | null = null
        let removeMouseMove: (() => void) | null = null
        let portalObserver: ResizeObserver | null = null

        const cBlue = { r: 76 / 255, g: 141 / 255, b: 255 / 255 }
        const cPurple = { r: 155 / 255, g: 107 / 255, b: 255 / 255 }
        const cGold = { r: 245 / 255, g: 176 / 255, b: 66 / 255 }
        const animSpeed = 1.1 // Increased to 2x from original 0.55

        const waitForDimensions = (): Promise<{ w: number; h: number }> => {
            return new Promise((resolve) => {
                const check = () => {
                    if (disposed) return
                    const rect = canvas.getBoundingClientRect()
                    if (rect.width > 10 && rect.height > 10) {
                        resolve({ w: rect.width, h: rect.height })
                    } else {
                        const parent = canvas.parentElement
                        const parentRect = parent?.getBoundingClientRect()
                        if (parentRect && parentRect.width > 10 && parentRect.height > 10) {
                            resolve({ w: parentRect.width, h: parentRect.height })
                        } else if (window.innerWidth > 0 && window.innerHeight > 0) {
                            resolve({ w: window.innerWidth, h: window.innerHeight })
                        } else {
                            requestAnimationFrame(check)
                        }
                    }
                }
                check()
            })
        }

        const refreshLayout = () => {
            if (!canvas || !camera) return
            const cRect = canvas.getBoundingClientRect()
            if (cRect.width < 1 || cRect.height < 1) return

            cachedCanvasW = cRect.width
            cachedCanvasH = cRect.height

            camera.aspect = cachedCanvasW / cachedCanvasH
            camera.updateProjectionMatrix()
            renderer?.setSize(cachedCanvasW, cachedCanvasH)

            const portalEl = document.getElementById('upload-portal-container')
            if (portalEl) {
                const rect = portalEl.getBoundingClientRect()
                const centerX = rect.left + rect.width / 2
                const centerY = rect.top + rect.height / 2
                const localX = centerX - cRect.left
                const localY = centerY - cRect.top
                const ndcX = (localX / cachedCanvasW) * 2 - 1
                const ndcY = -(localY / cachedCanvasH) * 2 + 1
                const vFOV = (camera.fov * Math.PI) / 180
                const heightAtZ0 = 2 * Math.tan(vFOV / 2) * camera.position.z
                const widthAtZ0 = heightAtZ0 * (cachedCanvasW / cachedCanvasH)
                coreX = ndcX * (widthAtZ0 / 2)
                coreY = ndcY * (heightAtZ0 / 2)
            } else if (cachedCanvasW > 980) {
                coreX = 4
                coreY = 0
            } else {
                coreX = 0
                coreY = -2
            }

            needsLayoutRefresh = false
        }

        const loadThree = async () => {
            try {
                const { w, h } = await waitForDimensions()
                if (disposed) return

                COUNT = w < 600 ? 120 : (w < 760 ? 175 : 450)

                scene = new THREE.Scene()
                camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 100)
                camera.position.z = 18

                renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: w > 600, powerPreference: 'high-performance' })
                renderer.setPixelRatio(Math.min(window.devicePixelRatio, w > 600 ? 2 : 1.5))
                renderer.setSize(w, h)
                // Enable hardware acceleration
                renderer.domElement.style.transform = 'translateZ(0)'
                renderer.domElement.style.willChange = 'transform'

                reactorGroup = new THREE.Group()
                scene.add(reactorGroup)

                innerRingGeom = new THREE.TorusGeometry(1.6, 0.04, 8, 64)
                innerRingMat = new THREE.MeshBasicMaterial({
                    color: new THREE.Color('#4c8dff'),
                    transparent: true,
                    opacity: 0.55,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                })
                innerRing = new THREE.Mesh(innerRingGeom, innerRingMat)
                reactorGroup.add(innerRing)

                middleRingGeom = new THREE.TorusGeometry(2.1, 0.03, 8, 64)
                middleRingMat = new THREE.MeshBasicMaterial({
                    color: new THREE.Color('#9b6bff'),
                    transparent: true,
                    opacity: 0.5,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                })
                middleRing = new THREE.Mesh(middleRingGeom, middleRingMat)
                reactorGroup.add(middleRing)

                outerRingGeom = new THREE.TorusGeometry(2.6, 0.02, 6, 64)
                outerRingMat = new THREE.MeshBasicMaterial({
                    color: new THREE.Color('#f5b042'),
                    transparent: true,
                    opacity: 0.45,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                })
                outerRing = new THREE.Mesh(outerRingGeom, outerRingMat)
                reactorGroup.add(outerRing)

                baseX = new Float32Array(COUNT)
                baseY = new Float32Array(COUNT)
                baseZ = new Float32Array(COUNT)
                speed = new Float32Array(COUNT)
                noisePhase = new Float32Array(COUNT)
                grid = new Float32Array(COUNT * 3)
                fadeOut = new Float32Array(COUNT)
                resetY = new Float32Array(COUNT)
                resetZ = new Float32Array(COUNT)
                const colors = new Float32Array(COUNT * 3)

                const cols = Math.ceil(Math.sqrt(COUNT * (w / h)))
                const rows = Math.ceil(COUNT / cols)

                for (let i = 0; i < COUNT; i++) {
                    baseX[i] = (Math.random() - 0.5) * 36
                    baseY[i] = (Math.random() - 0.5) * 12
                    baseZ[i] = (Math.random() - 0.5) * 6
                    speed[i] = (0.05 + Math.random() * 0.08) * animSpeed
                    noisePhase[i] = Math.random() * Math.PI * 2
                    resetY[i] = baseY[i]
                    resetZ[i] = baseZ[i]
                    fadeOut[i] = 1

                    const gx = i % cols
                    const gy = Math.floor(i / cols)
                    grid[i * 3 + 0] = (gx / (cols - 1) - 0.5) * 22
                    grid[i * 3 + 1] = (gy / (rows - 1) - 0.5) * 13
                    grid[i * 3 + 2] = 0

                    colors[i * 3 + 0] = 0.3
                    colors[i * 3 + 1] = 0.55
                    colors[i * 3 + 2] = 1.0
                }

                geometry = new THREE.BufferGeometry()
                const positions = new Float32Array(COUNT * 3)
                geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
                geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

                material = new THREE.PointsMaterial({
                    size: 0.16,
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.9,
                    sizeAttenuation: true,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                })

                points = new THREE.Points(geometry, material)
                scene.add(points)

                const heroSection = canvas.parentElement
                let lastScrollY = 0
                let scrollThrottleTimer: ReturnType<typeof setTimeout> | null = null
                let cachedHeroTop = 0
                let cachedHeroHeight = 0

                const measureHero = () => {
                    if (!heroSection) return
                    const rect = heroSection.getBoundingClientRect()
                    cachedHeroTop = rect.top + window.scrollY  // convert to page-space offset
                    cachedHeroHeight = rect.height
                }

                measureHero()

                const onScroll = () => {
                    if (!heroSection) return
                    
                    const currentScrollY = window.scrollY
                    const isMobile = window.innerWidth < 768
                    
                    // Throttle scroll events to reduce processing frequency
                    if (Math.abs(currentScrollY - lastScrollY) < 5 && scrollThrottleTimer) return
                    lastScrollY = currentScrollY
                    
                    // On mobile, delay the animation trigger to give users time to scroll
                    const scrollThreshold = isMobile ? 150 : 60
                    if (currentScrollY < scrollThreshold) {
                        targetOrder = 0
                        return
                    }
                    
                    // Use throttling instead of debounce for more responsive feel
                    if (!scrollThrottleTimer) {
                        scrollThrottleTimer = setTimeout(() => {
                            scrollThrottleTimer = null
                            if (disposed || !heroSection || cachedHeroHeight <= 0) return
                            // Use cached hero dimensions — no getBoundingClientRect here
                            const relativeTop = cachedHeroTop - window.scrollY
                            // On mobile, use a larger divisor to slow down the animation
                            const divisor = isMobile ? 0.9 : 0.6
                            const progress = Math.min(
                                1,
                                Math.max(0, -relativeTop / (cachedHeroHeight * divisor))
                            )
                            if (!isNaN(progress)) targetOrder = progress
                        }, 50)
                    }
                }

                const onMouseMove = (e: MouseEvent) => {
                    mouseX = e.clientX / window.innerWidth - 0.5
                    mouseY = e.clientY / window.innerHeight - 0.5
                }

                window.addEventListener('scroll', onScroll, { passive: true })
                window.addEventListener('mousemove', onMouseMove, { passive: true })
                removeScrollEnd = () => {
                    window.removeEventListener('scroll', onScroll)
                    if (scrollThrottleTimer) clearTimeout(scrollThrottleTimer)
                }
                removeMouseMove = () => window.removeEventListener('mousemove', onMouseMove)

                requestAnimationFrame(() => {
                    if (!disposed) onScroll()
                })

                needsLayoutRefresh = true
                refreshLayout()

                const portalEl = document.getElementById('upload-portal-container')
                if (portalEl) {
                    portalObserver = new ResizeObserver(() => {
                        needsLayoutRefresh = true
                    })
                    portalObserver.observe(portalEl)
                }

                const onResize = () => {
                    needsLayoutRefresh = true
                    measureHero()  // Re-cache hero section dimensions on resize
                }
                window.addEventListener('resize', onResize, { passive: true })
                removeResize = () => window.removeEventListener('resize', onResize)

                const posAttr = geometry.attributes.position as THREE.BufferAttribute
                const colorAttr = geometry.attributes.color as THREE.BufferAttribute

                const animate = () => {
                    if (disposed || !renderer || !scene || !camera || !geometry || !material) return
                    animId = requestAnimationFrame(animate)
                    const now = performance.now()
                    const dt = (now - t0) / 1000
                    t0 = now

                    if (needsLayoutRefresh) refreshLayout()

                    const isMobile = window.innerWidth < 768
                    const lerpSpeed = targetOrder < orderFactor ? 0.04 : (isMobile ? 0.015 : 0.025)
                    orderFactor += (targetOrder - orderFactor) * lerpSpeed
                    if (orderFactor < 0.015) orderFactor = 0
                    const currentIntensity = intensityRef.current
                    
                    // Cache frequently used values to avoid redundant calculations
                    const rotSpeedMult = 1 + currentIntensity * 2
                    const animSpeedDt = animSpeed * dt
                    const oneMinusOrderFactor = 1 - orderFactor
                    const pullBase = 18 // Cache constant for pull calculation

                    if (reactorGroup) {
                        reactorGroup.position.set(coreX, coreY, 0)
                        reactorGroup.scale.setScalar(oneMinusOrderFactor)
                    }

                    if (innerRing) {
                        innerRing.rotation.x += animSpeedDt * 0.8 * rotSpeedMult
                        innerRing.rotation.y += animSpeedDt * 1.2 * rotSpeedMult
                    }
                    if (middleRing) {
                        middleRing.rotation.y -= animSpeedDt * 1.0 * rotSpeedMult
                        middleRing.rotation.z += animSpeedDt * 0.5 * rotSpeedMult
                    }
                    if (outerRing) {
                        outerRing.rotation.x -= animSpeedDt * 0.6 * rotSpeedMult
                        outerRing.rotation.z -= animSpeedDt * 1.4 * rotSpeedMult
                    }

                    if (innerRingMat) innerRingMat.opacity = 0.55 * oneMinusOrderFactor * (1 + currentIntensity * 0.45)
                    if (middleRingMat) middleRingMat.opacity = 0.5 * oneMinusOrderFactor * (1 + currentIntensity * 0.5)
                    if (outerRingMat) outerRingMat.opacity = 0.45 * oneMinusOrderFactor * (1 + currentIntensity * 0.55)

                    for (let i = 0; i < COUNT; i++) {
                        const ix = i * 3
                        const iy = i * 3 + 1
                        const iz = i * 3 + 2

                        if (fadeOut[i] < 1) {
                            fadeOut[i] = Math.min(1, fadeOut[i] + dt * 4 * animSpeed)
                        } else {
                            baseX[i] += speed[i] * (1 + currentIntensity * 1.0)
                            if (baseX[i] > 18) {
                                baseX[i] = -18
                                baseY[i] = resetY[i]
                                baseZ[i] = resetZ[i]
                                fadeOut[i] = 0
                            }
                        }

                        const particleFade = fadeOut[i]
                        const fx = baseX[i]
                        let fy = baseY[i]
                        let fz = baseZ[i]

                        const dx = fx - coreX
                        const dxSquared = dx * dx
                        const pull = Math.exp(-dxSquared / pullBase)

                        fy = fy * (1 - pull) + coreY * pull
                        fz = fz * (1 - pull)

                        if (pull > 0.01) {
                            const swirlSpeed = now * 0.002 + noisePhase[i]
                            const swirlRadius = (1.5 + Math.sin(now * 0.0006 + noisePhase[i]) * 0.3) * pull
                            const sinSwirl = Math.sin(swirlSpeed)
                            const cosSwirl = Math.cos(swirlSpeed)
                            fy += sinSwirl * swirlRadius
                            fz += cosSwirl * swirlRadius
                        }

                        const wiggle = (1 - pull) * 0.35
                        const noiseSpeed = 0.0006
                        const ny = Math.sin(now * noiseSpeed + noisePhase[i]) * wiggle
                        const nz = Math.cos(now * 0.0009 + noisePhase[i]) * wiggle

                        const flowX = fx
                        const flowY = fy + ny
                        const flowZ = fz + nz

                        const gridX = grid[ix]
                        const gridY = grid[iy]
                        const gridZ = grid[iz]

                        // On mobile, reduce the grid transition to prevent glitches
                        const mobileOrderFactor = isMobile ? orderFactor * 0.3 : orderFactor
                        let finalX = flowX + (gridX - flowX) * mobileOrderFactor
                        let finalY = flowY + (gridY - flowY) * mobileOrderFactor
                        let finalZ = flowZ + (gridZ - flowZ) * mobileOrderFactor

                        if (particleFade < 1) {
                            const shrink = 0.3 + particleFade * 0.7
                            finalX = coreX + (finalX - coreX) * shrink
                            finalY = coreY + (finalY - coreY) * shrink
                            finalZ *= shrink
                        }

                        posAttr.array[ix] = finalX
                        posAttr.array[iy] = finalY
                        posAttr.array[iz] = finalZ

                        let r: number, g: number, b: number
                        const transX = finalX - coreX
                        const transitionWidth = 3.0

                        if (transX < -transitionWidth) {
                            r = cBlue.r; g = cBlue.g; b = cBlue.b
                        } else if (transX > transitionWidth) {
                            r = cGold.r; g = cGold.g; b = cGold.b
                        } else {
                            const t = (transX + transitionWidth) / (2 * transitionWidth)
                            if (t < 0.5) {
                                const nt = t / 0.5
                                r = cBlue.r + (cPurple.r - cBlue.r) * nt
                                g = cBlue.g + (cPurple.g - cBlue.g) * nt
                                b = cBlue.b + (cPurple.b - cBlue.b) * nt
                            } else {
                                const nt = (t - 0.5) / 0.5
                                r = cPurple.r + (cGold.r - cPurple.r) * nt
                                g = cPurple.g + (cGold.g - cPurple.g) * nt
                                b = cPurple.b + (cGold.b - cPurple.b) * nt
                            }
                        }

                        const fadeMul = particleFade
                        colorAttr.array[ix] = r * fadeMul
                        colorAttr.array[iy] = g * fadeMul
                        colorAttr.array[iz] = b * fadeMul
                    }

                    posAttr.needsUpdate = true
                    colorAttr.needsUpdate = true

                    material.size = (0.16 + currentIntensity * 0.14) * oneMinusOrderFactor

                    camera.position.x += (mouseX * 2 - camera.position.x) * 0.02
                    camera.position.y += (-mouseY * 1.4 - camera.position.y) * 0.02
                    camera.lookAt(0, 0, 0)

                    renderer.render(scene, camera)
                }

                t0 = performance.now()
                animate()
            } catch (err) {
                console.error('[ValidationCore] Three.js init failed:', err)
            }
        }

        loadThree()

        return () => {
            disposed = true
            cancelAnimationFrame(animId)
            removeScrollEnd?.()
            removeMouseMove?.()
            removeResize?.()
            portalObserver?.disconnect()
            innerRingGeom?.dispose()
            innerRingMat?.dispose()
            middleRingGeom?.dispose()
            middleRingMat?.dispose()
            outerRingGeom?.dispose()
            outerRingMat?.dispose()
            geometry?.dispose()
            material?.dispose()
            renderer?.dispose()
        }
    }, [])

    return (
        <canvas
            ref={canvasRef}
            id="hero-canvas"
            style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                zIndex: 0,
                opacity: 0.95,
                transform: 'translateZ(0)',
                willChange: 'transform',
            }}
        />
    )
}
