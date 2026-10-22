export interface Camera {
  ox: number
  oy: number
  scale: number
}

export interface Point {
  x: number
  y: number
}

export function fitCamera(nodes: Point[], width: number, height: number, pad = 64): Camera {
  if (width < 40 || height < 40) return { ox: 0, oy: 0, scale: 16 }
  const xs = nodes.map((node) => node.x)
  const ys = nodes.map((node) => node.y)
  let minX = Math.min(...xs)
  let maxX = Math.max(...xs)
  let minY = Math.min(...ys)
  let maxY = Math.max(...ys)
  if (!Number.isFinite(minX)) return { ox: width / 2, oy: height / 2, scale: 16 }
  if (maxX - minX < 1) {
    minX -= 1
    maxX += 1
  }
  if (maxY - minY < 1) {
    minY -= 1
    maxY += 1
  }
  const scale = Math.min((width - pad * 2) / (maxX - minX), (height - pad * 2) / (maxY - minY))
  const contentW = scale * (maxX - minX)
  const contentH = scale * (maxY - minY)
  const ox = (width - contentW) / 2 - scale * minX
  const oy = (height + contentH) / 2 + scale * minY
  return { ox, oy, scale }
}

export function zoomAt(camera: Camera, sx: number, sy: number, factor: number): Camera {
  const scale = Math.min(400, Math.max(0.05, camera.scale * factor))
  const worldX = (sx - camera.ox) / camera.scale
  const worldY = (camera.oy - sy) / camera.scale
  return {
    scale,
    ox: sx - worldX * scale,
    oy: sy + worldY * scale,
  }
}

export function screenToWorld(camera: Camera, sx: number, sy: number): Point {
  return {
    x: (sx - camera.ox) / camera.scale,
    y: (camera.oy - sy) / camera.scale,
  }
}

export function gridStep(scale: number) {
  const raw = 56 / Math.max(scale, 0.0001)
  const power = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 5, 10].map((multiplier) => multiplier * power).find((step) => step >= raw) ?? raw
}
