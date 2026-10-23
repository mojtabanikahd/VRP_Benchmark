import { useEffect, useMemo, useRef, type ReactNode } from "react"
import { GeoJSON, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents, ZoomControl } from "react-leaflet"
import L from "leaflet"

import { ROUTE_COLORS, SELECTED_ROUTE } from "../scenario/types"
import { mapClickHeld, MarkerFields } from "./FuelForm"
import { useFuel } from "./store"

import type { RoadPath } from "./types"

import "leaflet/dist/leaflet.css"

const NO_PATHS: RoadPath[] = []

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export function FuelMap() {
  const mode = useFuel((state) => state.mode)
  const setMode = useFuel((state) => state.setMode)
  const selectedId = useFuel((state) => state.selectedId)
  const removeSelected = useFuel((state) => state.removeSelected)

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[20, 0]} zoom={3} className="absolute inset-0" zoomControl={false}>
        <ZoomControl position="topright" />
        <TileLayer attribution={OSM_ATTR} url={OSM} />
        <MapSize />
        <MapClicks />
        <FitMarkers />
        <FocusPoint />
        <DepotMarker />
        <MachineMarkers />
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
        <button
          type="button"
          disabled={!selectedId}
          onClick={() => removeSelected()}
          className={
            selectedId
              ? "rounded-md px-2.5 py-1.5 text-sm text-ink-soft hover:bg-ink/5"
              : "rounded-md px-2.5 py-1.5 text-sm text-ink-soft/40"
          }
        >
          Remove
        </button>
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
      if (mapClickHeld()) return
      const target = event.originalEvent?.target
      if (target instanceof Element && target.closest(".leaflet-popup")) return
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
  const tankerTypes = useFuel((state) => state.tankerTypes)
  const tankerTypeId = useFuel((state) => state.tankerTypeId)
  const image = tankerTypes.find((item) => item.id === tankerTypeId)?.image
  if (!depot || !image) return null
  return <PlacedMarker id={depot.id} lat={depot.lat} lng={depot.lng} image={image} kind="depot" />
}

function MachineMarkers() {
  const machines = useFuel((state) => state.machines)
  const machineTypes = useFuel((state) => state.machineTypes)
  const solution = useFuel((state) => state.solution)
  const selectedRoute = useFuel((state) => state.selectedRoute)
  const numbers = useMemo(() => visitNumbers(solution?.routes ?? [], selectedRoute), [solution, selectedRoute])
  return (
    <>
      {machines.map((machine, index) => {
        const image = machineTypes.find((item) => item.id === machine.machineTypeId)?.image
        if (!image) return null
        const visit = numbers.get(index + 1)
        return (
          <PlacedMarker key={machine.id} id={machine.id} lat={machine.lat} lng={machine.lng} image={image} kind="machine">
            {visit ? <StopBadge lat={machine.lat} lng={machine.lng} label={visit.label} color={visit.color} /> : null}
          </PlacedMarker>
        )
      })}
    </>
  )
}

function PlacedMarker({
  id,
  lat,
  lng,
  image,
  kind,
  children,
}: {
  id: string
  lat: number
  lng: number
  image: string
  kind: "depot" | "machine"
  children?: ReactNode
}) {
  const markerRef = useRef<L.Marker>(null)
  const popupId = useFuel((state) => state.popupId)
  const select = useFuel((state) => state.select)
  const setPopup = useFuel((state) => state.setPopup)
  const moveDepot = useFuel((state) => state.moveDepot)
  const moveMachine = useFuel((state) => state.moveMachine)
  const icon = useMemo(
    () =>
      L.icon({
        iconUrl: image,
        iconSize: [40, 40],
        iconAnchor: [20, 40],
        popupAnchor: [0, -36],
      }),
    [image],
  )

  useEffect(() => {
    if (popupId === id) markerRef.current?.openPopup()
    else markerRef.current?.closePopup()
  }, [id, popupId])

  return (
    <>
      <Marker
        ref={markerRef}
        position={[lat, lng]}
        icon={icon}
        draggable
        eventHandlers={{
          click: () => select(id),
          dragend: (event) => {
            const next = event.target.getLatLng()
            if (kind === "depot") moveDepot(next.lat, next.lng)
            else moveMachine(id, next.lat, next.lng)
          },
          popupclose: () => {
            if (useFuel.getState().popupId === id) setPopup(null)
          },
        }}
      >
        <Popup className="fuel-popup" minWidth={280} autoPan>
          <MarkerFields id={id} />
        </Popup>
      </Marker>
      {children}
    </>
  )
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
    const color =
      selectedRoute === index ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length]
    route.forEach((node, stop) => {
      numbers.set(node, { label: stop + 1, color })
    })
  })
  return numbers
}
