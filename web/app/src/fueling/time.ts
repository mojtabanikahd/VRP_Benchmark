const DAY = 24 * 60

export function minutesToClock(minutes: number): string {
  const rounded = Math.round(minutes)
  const clamped = Math.max(0, Math.min(DAY - 1, rounded))
  const hours = Math.floor(clamped / 60)
  const mins = clamped % 60
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`
}

export function clockToMinutes(value: string): number {
  const [hours, mins] = value.split(":").map((part) => Number(part))
  if (!Number.isFinite(hours) || !Number.isFinite(mins)) return 0
  return Math.max(0, Math.min(DAY - 1, hours * 60 + mins))
}
