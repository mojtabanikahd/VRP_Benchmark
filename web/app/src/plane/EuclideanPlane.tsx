import { Maximize2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Circle, Layer, Line, Rect, Stage, Text } from "react-konva"

import { fitCamera, gridStep, screenToWorld, zoomAt, type Camera } from "./camera"
import { RouteLayer } from "./RouteLayer"
import { useStudio } from "../scenario/store"

export function EuclideanPlane() {
  const host = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 800, height: 600 })
  const [camera, setCamera] = useState<Camera>({ ox: 400, oy: 300, scale: 16 })
  const nodes = useStudio((state) => state.nodes)
  const variant = useStudio((state) => state.variant)
  const selectedId = useStudio((state) => state.selectedId)
  const solution = useStudio((state) => state.solution)
  const selectedRoute = useStudio((state) => state.selectedRoute)
  const fitToken = useStudio((state) => state.fitToken)
  const addCustomer = useStudio((state) => state.addCustomer)
  const moveNode = useStudio((state) => state.moveNode)
  const select = useStudio((state) => state.select)
  const refit = useStudio((state) => state.refit)
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const cameraRef = useRef(camera)
  cameraRef.current = camera
  const pan = useRef<{ x: number; y: number; ox: number; oy: number; moved: boolean } | null>(null)

  useEffect(() => {
    const element = host.current
    if (!element) return
    const observer = new ResizeObserver(() => {
      setSize({ width: element.clientWidth, height: element.clientHeight })
    })
    observer.observe(element)
    setSize({ width: element.clientWidth, height: element.clientHeight })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    setCamera(fitCamera(nodesRef.current, size.width, size.height))
  }, [fitToken, size.width, size.height])

  const customers = nodes.filter((node) => node.role === "customer").length
  const step = gridStep(camera.scale)
  const worldLeft = (0 - camera.ox) / camera.scale
  const worldRight = (size.width - camera.ox) / camera.scale
  const worldTop = (camera.oy - 0) / camera.scale
  const worldBottom = (camera.oy - size.height) / camera.scale
  const lines: number[][] = []
  const startX = Math.floor(worldLeft / step) * step
  const startY = Math.floor(Math.min(worldTop, worldBottom) / step) * step
  const endY = Math.max(worldTop, worldBottom)
  for (let x = startX; x <= worldRight; x += step) lines.push([x, -worldBottom, x, -worldTop])
  for (let y = startY; y <= endY; y += step) lines.push([worldLeft, -y, worldRight, -y])

  return (
    <div ref={host} className="relative h-full w-full overflow-hidden bg-paper">
      <Stage
        width={size.width}
        height={size.height}
        onWheel={(event) => {
          event.evt.preventDefault()
          const pointer = event.target.getStage()?.getPointerPosition()
          if (!pointer) return
          const factor = event.evt.deltaY < 0 ? 1.08 : 0.92
          setCamera((current) => zoomAt(current, pointer.x, pointer.y, factor))
        }}
        onMouseDown={(event) => {
          if (event.target !== event.target.getStage()) return
          const pointer = event.target.getStage()?.getPointerPosition()
          if (!pointer) return
          pan.current = {
            x: pointer.x,
            y: pointer.y,
            ox: cameraRef.current.ox,
            oy: cameraRef.current.oy,
            moved: false,
          }
        }}
        onMouseMove={(event) => {
          if (!pan.current) return
          const pointer = event.target.getStage()?.getPointerPosition()
          if (!pointer) return
          const dx = pointer.x - pan.current.x
          const dy = pointer.y - pan.current.y
          if (Math.hypot(dx, dy) > 3) pan.current.moved = true
          const origin = pan.current
          setCamera((current) => ({ ...current, ox: origin.ox + dx, oy: origin.oy + dy }))
        }}
        onMouseUp={(event) => {
          const gesture = pan.current
          pan.current = null
          if (!gesture || gesture.moved) return
          if (event.target !== event.target.getStage()) return
          const pointer = event.target.getStage()?.getPointerPosition()
          if (!pointer) return
          const world = screenToWorld(cameraRef.current, pointer.x, pointer.y)
          addCustomer(world.x, world.y)
        }}
        onMouseLeave={() => {
          pan.current = null
        }}
      >
        <Layer x={camera.ox} y={camera.oy} scaleX={camera.scale} scaleY={camera.scale}>
          {lines.map((points, index) => (
            <Line
              key={index}
              points={points}
              stroke="rgba(20,24,28,0.08)"
              strokeWidth={1 / camera.scale}
              listening={false}
            />
          ))}
          {solution ? (
            <RouteLayer
              nodes={nodes}
              routes={solution.routes}
              routeDepots={
                solution.route_depots.length === solution.routes.length
                  ? solution.route_depots
                  : solution.routes.map(() => 0)
              }
              selectedRoute={selectedRoute}
              scale={camera.scale}
            />
          ) : null}
          {nodes.map((node) => {
            const selected = node.id === selectedId
            const radius = (node.role === "depot" ? 8 : 7 + Math.sqrt(node.demand) * 2.4) / camera.scale
            const y = -node.y
            return node.role === "depot" ? (
              <Rect
                key={node.id}
                x={node.x - radius}
                y={y - radius}
                width={radius * 2}
                height={radius * 2}
                fill="#14181c"
                stroke={selected ? "#c4622d" : "#f3efe6"}
                strokeWidth={(selected ? 2.5 : 1) / camera.scale}
                draggable
                onMouseDown={(event) => {
                  event.cancelBubble = true
                }}
                onClick={(event) => {
                  event.cancelBubble = true
                  select(node.id)
                }}
                onTap={(event) => {
                  event.cancelBubble = true
                  select(node.id)
                }}
                onDragEnd={(event) => moveNode(node.id, event.target.x() + radius, -(event.target.y() + radius))}
              />
            ) : (
              <Circle
                key={node.id}
                x={node.x}
                y={y}
                radius={radius}
                fill="#f7f3ea"
                stroke={selected ? "#c4622d" : "#14181c"}
                strokeWidth={(selected ? 2.4 : 1.2) / camera.scale}
                draggable
                onMouseDown={(event) => {
                  event.cancelBubble = true
                }}
                onClick={(event) => {
                  event.cancelBubble = true
                  select(node.id)
                }}
                onTap={(event) => {
                  event.cancelBubble = true
                  select(node.id)
                }}
                onDragEnd={(event) => moveNode(node.id, event.target.x(), -event.target.y())}
              />
            )
          })}
          {nodes.map((node, index) => {
            const radius = (node.role === "depot" ? 8 : 7 + Math.sqrt(node.demand) * 2.4) / camera.scale
            const caption =
              variant === "VRPTW" && node.role === "customer" ? `${node.ready}–${node.due}` : String(index)
            return (
              <Text
                key={`${node.id}-label`}
                x={node.x + radius + 2 / camera.scale}
                y={-node.y - 6 / camera.scale}
                text={caption}
                fontSize={12 / camera.scale}
                fontFamily="Geist, sans-serif"
                fill="#3e474f"
                listening={false}
              />
            )
          })}
        </Layer>
      </Stage>
      <div className="pointer-events-none absolute left-4 top-4 flex items-center gap-3 text-xs text-ink-soft">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 bg-ink" /> Depot
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-full border border-ink bg-paper" /> Customer
        </span>
      </div>
      {customers === 0 ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-8 text-center text-sm text-ink-soft">
          Click the plane to add a customer.
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => refit()}
        className="absolute right-4 top-4 inline-flex items-center gap-1.5 rounded-md border border-line bg-paper/90 px-2.5 py-1.5 text-xs text-ink shadow-sm hover:border-copper/40"
      >
        <Maximize2 className="size-3.5" />
        Fit
      </button>
    </div>
  )
}
