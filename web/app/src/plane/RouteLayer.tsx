import Konva from "konva"
import { useEffect, useRef } from "react"
import { Line } from "react-konva"

import { ROUTE_COLORS, SELECTED_ROUTE, type ScenarioNode } from "../scenario/types"

function routePoints(nodes: ScenarioNode[], route: number[], depotIndex: number) {
  const points: number[] = []
  const push = (index: number) => {
    const node = nodes[index]
    if (!node) return
    points.push(node.x, -node.y)
  }
  push(depotIndex)
  for (const index of route) push(index)
  push(depotIndex)
  return points
}

function lengthOf(points: number[]) {
  let total = 0
  for (let index = 2; index < points.length; index += 2) {
    total += Math.hypot(points[index] - points[index - 2], points[index + 1] - points[index - 1])
  }
  return total
}

function RouteStroke({
  points,
  color,
  width,
  selected,
}: {
  points: number[]
  color: string
  width: number
  selected: boolean
}) {
  const ref = useRef<Konva.Line>(null)
  const signature = points.join(",")
  useEffect(() => {
    const line = ref.current
    if (!line) return
    const length = lengthOf(points)
    if (length <= 0) return
    line.dash([length, length])
    line.dashOffset(length)
    const tween = new Konva.Tween({
      node: line,
      duration: 0.55,
      dashOffset: 0,
      easing: Konva.Easings.EaseOut,
    })
    tween.play()
    return () => {
      tween.destroy()
    }
  }, [signature, points])

  return (
    <Line
      ref={ref}
      points={points}
      stroke={color}
      strokeWidth={width}
      lineCap="round"
      lineJoin="round"
      opacity={selected ? 1 : 0.9}
      listening={false}
    />
  )
}

export function RouteLayer({
  nodes,
  routes,
  routeDepots,
  selectedRoute,
  scale,
}: {
  nodes: ScenarioNode[]
  routes: number[][]
  routeDepots: number[]
  selectedRoute: number | null
  scale: number
}) {
  const drawn = routes
    .map((route, index) => ({
      index,
      points: routePoints(nodes, route, routeDepots[index] ?? 0),
      selected: selectedRoute === index,
    }))
    .filter((route) => route.points.length >= 4)
    .sort((a, b) => Number(a.selected) - Number(b.selected))

  return (
    <>
      {drawn.map((route) => (
        <RouteStroke
          key={`${route.index}-${route.points.join(":")}`}
          points={route.points}
          color={route.selected ? SELECTED_ROUTE : ROUTE_COLORS[route.index % ROUTE_COLORS.length]}
          width={(route.selected ? 3.2 : 2.1) / scale}
          selected={route.selected}
        />
      ))}
    </>
  )
}
