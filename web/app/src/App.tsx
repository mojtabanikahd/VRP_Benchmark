import { Component, useState, type ReactNode } from "react"

import { FuelApp } from "./fueling/FuelApp"
import { FuelStoreProvider, fuelStore, studioStore } from "./fueling/store"

export function App() {
  const [mode, setMode] = useState<"studio" | "fueling">("studio")
  const store = mode === "studio" ? studioStore : fuelStore
  return (
    <div className="fuel-ui flex h-dvh flex-col" dir="rtl" lang="fa">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-paper px-4">
        <p className="font-display text-xl leading-none text-ink">VRP Studio</p>
        <div className="flex gap-1">
          <ModeButton active={mode === "studio"} onClick={() => setMode("studio")}>
            Studio
          </ModeButton>
          <ModeButton active={mode === "fueling"} onClick={() => setMode("fueling")}>
            سوخت‌رسانی
          </ModeButton>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        <ErrorBoundary key={mode}>
          <FuelStoreProvider store={store}>
            <FuelApp />
          </FuelStoreProvider>
        </ErrorBoundary>
      </div>
    </div>
  )
}

function ErrorBoundary({ children }: { children: ReactNode }) {
  return <Boundary>{children}</Boundary>
}

class Boundary extends Component<{ children: ReactNode }, { message: string | null }> {
  state = { message: null as string | null }

  static getDerivedStateFromError(error: unknown) {
    return { message: error instanceof Error ? error.message : String(error) }
  }

  render() {
    if (this.state.message) {
      return <p className="p-6 text-sm text-copper">{this.state.message}</p>
    }
    return this.props.children
  }
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-md bg-ink px-3 py-1.5 text-sm text-paper"
          : "rounded-md px-3 py-1.5 text-sm text-ink-soft hover:bg-ink/5"
      }
    >
      {children}
    </button>
  )
}
