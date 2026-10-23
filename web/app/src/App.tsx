import { Component, useEffect, useRef, useState, type ReactNode } from "react"
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelHandle } from "react-resizable-panels"

import { Inspector } from "./inspector/Inspector"
import { NodeGrid } from "./grid/NodeGrid"
import { EuclideanPlane } from "./plane/EuclideanPlane"
import { ResultDock } from "./dock/ResultDock"
import { FuelApp } from "./fueling/FuelApp"
import { Rail } from "./shell/Rail"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs"
import { useStudio } from "./scenario/store"

export function App() {
  const [mode, setMode] = useState<"studio" | "fueling">("studio")
  const fueling = mode === "fueling"
  return (
    <div
      className={fueling ? "fuel-ui flex h-dvh flex-col" : "flex h-dvh flex-col"}
      dir={fueling ? "rtl" : "ltr"}
      lang={fueling ? "fa" : "en"}
    >
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
        <ErrorBoundary key={mode}>{mode === "studio" ? <StudioWorkspace /> : <FuelApp />}</ErrorBoundary>
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

function StudioWorkspace() {
  const dockRef = useRef<ImperativePanelHandle>(null)
  const solution = useStudio((state) => state.solution)
  const jobError = useStudio((state) => state.jobError)
  const removeSelected = useStudio((state) => state.removeSelected)

  useEffect(() => {
    dockRef.current?.collapse()
  }, [])

  useEffect(() => {
    if (solution || jobError) dockRef.current?.expand()
  }, [jobError, solution])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return
      removeSelected()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [removeSelected])

  return (
    <PanelGroup direction="vertical" className="h-full">
      <Panel defaultSize={78} minSize={48}>
        <PanelGroup direction="horizontal">
          <Panel defaultSize={22} minSize={16} maxSize={34}>
            <Rail />
          </Panel>
          <PanelResizeHandle className="w-px bg-line transition-colors hover:bg-copper/50" />
          <Panel defaultSize={54} minSize={30}>
            <EuclideanPlane />
          </Panel>
          <PanelResizeHandle className="w-px bg-line transition-colors hover:bg-copper/50" />
          <Panel defaultSize={24} minSize={18} maxSize={40}>
            <Tabs defaultValue="inspector">
              <TabsList>
                <TabsTrigger value="inspector">Inspector</TabsTrigger>
                <TabsTrigger value="nodes">Nodes</TabsTrigger>
              </TabsList>
              <TabsContent value="inspector">
                <Inspector />
              </TabsContent>
              <TabsContent value="nodes">
                <NodeGrid />
              </TabsContent>
            </Tabs>
          </Panel>
        </PanelGroup>
      </Panel>
      <PanelResizeHandle className="h-px bg-line transition-colors hover:bg-copper/50" />
      <Panel ref={dockRef} defaultSize={22} minSize={14} collapsible collapsedSize={0}>
        <ResultDock />
      </Panel>
    </PanelGroup>
  )
}
