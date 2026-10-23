import { useEffect, useMemo, useRef, type ReactNode, type RefObject } from "react"
import { GeoJSON, MapContainer, Marker, TileLayer, useMap, useMapEvents, ZoomControl } from "react-leaflet"
import L from "leaflet"

import { ROUTE_COLORS, SELECTED_ROUTE } from "../scenario/types"
import { useFuel } from "./store"
import { formatRange } from "./time"

import type { RoadPath } from "./types"

import "leaflet/dist/leaflet.css"

const NO_PATHS: RoadPath[] = []
const HOVER_DELAY_MS = 400
let hoverTimer = 0
let hoverTip: L.Tooltip | null = null

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export function FuelMap() {
  const mode = useFuel((state) => state.mode)
  const setMode = useFuel((state) => state.setMode)
  const mapEpoch = useFuel((state) => state.mapEpoch)

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[20, 0]} zoom={3} className="absolute inset-0" zoomControl={false}>
        <ZoomControl position="topright" />
        <TileLayer attribution={OSM_ATTR} url={OSM} />
        <MapSize />
        <MapClicks />
        <FitMarkers />
        <FocusPoint />
        <DepotMarker key={`depot-${mapEpoch}`} />
        <MachineMarkers key={`machines-${mapEpoch}`} />
        <RoadLayer />
      </MapContainer>
      <div className="absolute left-3 top-3 z-[500] flex gap-1 rounded-md border border-line bg-paper p-1 shadow-sm">
        <Tool active={mode === "depot"} onClick={() => setMode("depot")}>
          Set depot
        </Tool>
        <Tool active={mode === "machine"} onClick={() => setMode("machine")}>
          Place machine
        </Tool>
        <Tool active={mode === "select"} onClick={() => setMode("select")}>
          Select
        </Tool>
      </div>
    </div>
  )
}

function Tool({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-md bg-ink px-2.5 py-1.5 text-sm text-paper"
          : "rounded-md px-2.5 py-1.5 text-sm text-ink-soft hover:bg-ink/5"
      }
    >
      {children}
    </button>
  )
}

function MapSize() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    const observer = new ResizeObserver(() => {
      map.invalidateSize()
    })
    observer.observe(container)
    map.invalidateSize()
    return () => observer.disconnect()
  }, [map])
  return null
}

function MapClicks() {
  const mode = useFuel((state) => state.mode)
  const placeDepot = useFuel((state) => state.placeDepot)
  const addMachine = useFuel((state) => state.addMachine)
  const select = useFuel((state) => state.select)
  useMapEvents({
    click(event) {
      const target = event.originalEvent?.target
      if (target instanceof Element && target.closest(".leaflet-marker-icon")) return
      if (mode === "depot") placeDepot(event.latlng.lat, event.latlng.lng)
      else if (mode === "machine") addMachine(event.latlng.lat, event.latlng.lng)
      else select(null)
    },
  })
  return null
}

function FocusPoint() {
  const map = useMap()
  const focusToken = useFuel((state) => state.focusToken)
  useEffect(() => {
    const { focusId, depot, machines } = useFuel.getState()
    if (!focusId) return
    const point = depot?.id === focusId ? depot : machines.find((machine) => machine.id === focusId)
    if (!point) return
    map.flyTo([point.lat, point.lng], Math.max(map.getZoom(), 15))
  }, [focusToken, map])
  return null
}

function FitMarkers() {
  const map = useMap()
  const fitToken = useFuel((state) => state.fitToken)
  useEffect(() => {
    const { depot, machines } = useFuel.getState()
    const points: [number, number][] = []
    if (depot) points.push([depot.lat, depot.lng])
    for (const machine of machines) points.push([machine.lat, machine.lng])
    if (points.length === 0) return
    if (points.length === 1) map.setView(points[0], 14)
    else map.fitBounds(points, { padding: [48, 48] })
  }, [fitToken, map])
  return null
}

function DepotMarker() {
  const depot = useFuel((state) => state.depot)
  const image = useFuel((state) => state.tanker.image)
  if (!depot || !image) return null
  return <PlacedMarker id={depot.id} name={depot.name} lat={depot.lat} lng={depot.lng} image={image} kind="depot" />
}

function MachineMarkers() {
  const machines = useFuel((state) => state.machines)
  const machineTypes = useFuel((state) => state.machineTypes)
  const solution = useFuel((state) => state.solution)
  const selectedRoute = useFuel((state) => state.selectedRoute)
  const numbers = useMemo(() => visitNumbers(solution?.routes ?? [], selectedRoute), [solution, selectedRoute])
  const visits = useMemo(
    () => visitWindows(solution?.routes ?? [], solution?.arrivals_min ?? [], solution?.leaves_min ?? [], selectedRoute),
    [solution, selectedRoute],
  )
  return (
    <>
      {machines.map((machine, index) => {
        const image = machineTypes.find((item) => item.id === machine.machineTypeId)?.image
        if (!image) return null
        const visit = numbers.get(index + 1)
        const window = visits.get(index + 1)
        return (
          <PlacedMarker
            key={machine.id}
            id={machine.id}
            name={machine.name}
            lat={machine.lat}
            lng={machine.lng}
            image={image}
            kind="machine"
          >
            {visit ? <StopBadge lat={machine.lat} lng={machine.lng} label={visit.label} color={visit.color} /> : null}
            {window ? (
              <TimeBadge lat={machine.lat} lng={machine.lng} label={formatRange(window.arrive, window.leave)} />
            ) : null}
          </PlacedMarker>
        )
      })}
    </>
  )
}

function PlacedMarker({
  id,
  name,
  lat,
  lng,
  image,
  kind,
  children,
}: {
  id: string
  name: string
  lat: number
  lng: number
  image: string
  kind: "depot" | "machine"
  children?: ReactNode
}) {
  const markerRef = useRef<L.Marker>(null)
  const selected = useFuel((state) => state.selectedId === id)
  const inspect = useFuel((state) => state.inspect)
  const moveDepot = useFuel((state) => state.moveDepot)
  const moveMachine = useFuel((state) => state.moveMachine)
  const icon = useMemo(() => pinIcon(image, selected), [image, selected])
  useNameTooltip(markerRef, name, `${image}:${selected}`)

  return (
    <>
      <Marker
        ref={markerRef}
        position={[lat, lng]}
        icon={icon}
        draggable
        bubblingMouseEvents={false}
        zIndexOffset={selected ? 1000 : 0}
        eventHandlers={{
          click: () => inspect(id),
          dragend: (event) => {
            const next = event.target.getLatLng()
            if (kind === "depot") moveDepot(next.lat, next.lng)
            else moveMachine(id, next.lat, next.lng)
          },
        }}
      />
      {children}
    </>
  )
}

function useNameTooltip(markerRef: RefObject<L.Marker | null>, name: string, revision: string) {
  useEffect(() => {
    const marker = markerRef.current
    if (!marker) return
    const bound = new Set<HTMLElement>()
    const open = () => {
      window.clearTimeout(hoverTimer)
      const map = (marker as unknown as { _map: L.Map | null })._map
      if (!map) return
      hoverTimer = window.setTimeout(() => {
        if (!hoverTip) {
          hoverTip = L.tooltip({
            direction: "right",
            offset: [14, -24],
            opacity: 1,
            className: "fuel-tip",
            interactive: false,
          })
        }
        hoverTip.setContent(escapeHtml(name))
        hoverTip.setLatLng(marker.getLatLng())
        if (!map.hasLayer(hoverTip)) hoverTip.addTo(map)
      }, HOVER_DELAY_MS)
    }
    const close = () => {
      window.clearTimeout(hoverTimer)
      hoverTip?.close()
    }
    const bind = () => {
      const next = marker.getElement()
      if (!next || bound.has(next)) return
      next.addEventListener("mouseenter", open)
      next.addEventListener("mouseleave", close)
      bound.add(next)
    }
    bind()
    const frame = window.requestAnimationFrame(bind)
    marker.on("dragstart", close)
    return () => {
      window.cancelAnimationFrame(frame)
      for (const el of bound) {
        el.removeEventListener("mouseenter", open)
        el.removeEventListener("mouseleave", close)
      }
      marker.off("dragstart", close)
      close()
    }
  }, [markerRef, name, revision])
}

function pinIcon(image: string, selected: boolean) {
  const size = selected ? 48 : 40
  return L.divIcon({
    className: "fuel-pin",
    html: `<img src="${escapeAttr(image)}" alt="" width="${size}" height="${size}" class="${selected ? "is-selected" : ""}" />`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
  })
}

function escapeHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function escapeAttr(value: string) {
  return escapeHtml(value).replace(/"/g, "&quot;")
}

function StopBadge({ lat, lng, label, color }: { lat: number; lng: number; label: number; color: string }) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: "fuel-stop",
        html: `<span style="background:${color}">${label}</span>`,
        iconSize: [22, 22],
        iconAnchor: [11, 52],
      }),
    [color, label],
  )
  return <Marker position={[lat, lng]} icon={icon} interactive={false} keyboard={false} />
}

function TimeBadge({ lat, lng, label }: { lat: number; lng: number; label: string }) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: "fuel-arrival",
        html: `<span>${escapeHtml(label)}</span>`,
        iconSize: [108, 18],
        iconAnchor: [-18, 36],
      }),
    [label],
  )
  return <Marker position={[lat, lng]} icon={icon} interactive={false} keyboard={false} />
}

function RoadLayer() {
  const storedPaths = useFuel((state) => state.solution?.paths)
  const paths = storedPaths ?? NO_PATHS
  const selectedRoute = useFuel((state) => state.selectedRoute)
  const selectRoute = useFuel((state) => state.selectRoute)
  const map = useMap()
  const fitted = useRef<string>("")

  useEffect(() => {
    if (paths.length === 0) {
      fitted.current = ""
      return
    }
    const signature = paths.map((path) => path.geometry.coordinates.length).join(":")
    if (fitted.current === signature) return
    fitted.current = signature
    map.fitBounds(latLngs(paths.flatMap((path) => path.geometry.coordinates)), { padding: [36, 36] })
  }, [map, paths])

  useEffect(() => {
    if (selectedRoute === null) return
    const path = paths[selectedRoute]
    if (!path) return
    map.fitBounds(latLngs(path.geometry.coordinates), { padding: [48, 48] })
  }, [map, paths, selectedRoute])

  return (
    <>
      {paths.map((path, index) => {
        const active = selectedRoute === index
        const color = active ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length]
        return (
          <GeoJSON
            key={`${index}-${path.geometry.coordinates.length}-${active ? "on" : "off"}`}
            data={path.geometry}
            style={{ color, weight: active ? 7 : 5, opacity: 0.92 }}
            eventHandlers={{ click: () => selectRoute(active ? null : index) }}
          />
        )
      })}
    </>
  )
}

function latLngs(coordinates: [number, number][]) {
  return coordinates.map(([lng, lat]) => [lat, lng] as [number, number])
}

function visitNumbers(routes: number[][], selectedRoute: number | null) {
  const numbers = new Map<number, { label: number; color: string }>()
  routes.forEach((route, index) => {
    const color = selectedRoute === index ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length]
    route.forEach((node, stop) => {
      numbers.set(node, { label: stop + 1, color })
    })
  })
  return numbers
}

function visitWindows(
  routes: number[][],
  arrivals: number[][],
  leaves: number[][],
  selectedRoute: number | null,
) {
  const labels = new Map<number, { arrive: number; leave: number }>()
  routes.forEach((route, index) => {
    if (selectedRoute !== null && selectedRoute !== index) return
    route.forEach((node, stop) => {
      const arrive = arrivals[index]?.[stop]
      const leave = leaves[index]?.[stop]
      if (typeof arrive === "number" && typeof leave === "number") labels.set(node, { arrive, leave })
    })
  })
  return labels
}
