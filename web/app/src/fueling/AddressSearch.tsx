import { useState, type FormEvent } from "react"

import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { searchAddresses, type FuelPlace } from "./api"
import { copy, persianError } from "./copy"

export function AddressSearch({ onPick }: { onPick: (place: FuelPlace) => void }) {
  const [query, setQuery] = useState("")
  const [places, setPlaces] = useState<FuelPlace[]>([])
  const [selected, setSelected] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const choose = (index: number, found = places) => {
    const place = found[index]
    if (!place) return
    setSelected(index)
    onPick(place)
  }

  const search = async (event: FormEvent) => {
    event.preventDefault()
    const text = query.trim()
    if (!text || pending) return
    setPending(true)
    setError(null)
    try {
      const found = await searchAddresses(text)
      setPlaces(found)
      setSelected(0)
      if (found.length === 0) setError(copy.addressNotFound)
      else onPick(found[0])
    } catch (caught) {
      setPlaces([])
      const message = caught instanceof Error ? caught.message : ""
      setError(persianError(message))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-[600] flex justify-start ps-14 pe-[22rem]">
      <div className="pointer-events-auto w-full max-w-md" dir="rtl">
        <form onSubmit={search} className="flex gap-1 rounded-md border border-line bg-paper p-1 shadow-sm">
          <Input
            value={query}
            placeholder={copy.addressPlaceholder}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={copy.addressPlaceholder}
          />
          <Button type="submit" size="sm" disabled={pending || query.trim() === ""}>
            {pending ? copy.searchingAddress : copy.searchAddress}
          </Button>
        </form>
        {error ? <p className="mt-1 rounded-md bg-paper px-2 py-1 text-sm text-ink-soft shadow-sm">{error}</p> : null}
        {places.length > 0 ? (
          <ul className="mt-1 max-h-48 overflow-auto rounded-md border border-line bg-paper py-1 shadow-sm">
            {places.map((place, index) => (
              <li key={`${place.lat},${place.lng},${index}`}>
                <button
                  type="button"
                  onClick={() => choose(index)}
                  className={
                    index === selected
                      ? "w-full whitespace-normal px-2.5 py-1.5 text-right text-sm leading-5 text-ink bg-ink/5"
                      : "w-full whitespace-normal px-2.5 py-1.5 text-right text-sm leading-5 text-ink-soft hover:bg-ink/5"
                  }
                >
                  {place.label}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
