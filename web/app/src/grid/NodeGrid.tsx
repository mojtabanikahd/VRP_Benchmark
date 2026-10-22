import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table"
import { useMemo } from "react"

import { useStudio } from "../scenario/store"
import type { ScenarioNode } from "../scenario/types"

const column = createColumnHelper<ScenarioNode>()

export function NodeGrid() {
  const nodes = useStudio((state) => state.nodes)
  const variant = useStudio((state) => state.variant)
  const updateNode = useStudio((state) => state.updateNode)
  const select = useStudio((state) => state.select)
  const selectedId = useStudio((state) => state.selectedId)

  const columns = useMemo(() => {
    const numeric = (
      id: "x" | "y" | "demand" | "ready" | "due" | "service",
      header: string,
    ) =>
      column.accessor(id, {
        header,
        cell: (info) => (
          <input
            key={`${info.row.original.id}-${id}-${info.getValue()}`}
            className="w-full bg-transparent px-1 py-1 outline-none"
            defaultValue={info.getValue()}
            disabled={id === "demand" && info.row.original.role === "depot"}
            onBlur={(event) => {
              const value = Number(event.target.value)
              if (!Number.isFinite(value)) return
              updateNode(info.row.original.id, { [id]: id === "demand" ? Math.round(value) : value })
            }}
          />
        ),
      })
    const base = [
      column.display({
        id: "index",
        header: "#",
        cell: (info) => <span className="text-ink-soft">{info.row.index}</span>,
      }),
      column.accessor("role", { header: "Role" }),
      numeric("x", "X"),
      numeric("y", "Y"),
      numeric("demand", "Demand"),
    ]
    if (variant === "VRPTW") {
      base.push(numeric("ready", "Ready"), numeric("due", "Due"), numeric("service", "Service"))
    }
    return base
  }, [updateNode, variant])

  const table = useReactTable({ data: nodes, columns, getCoreRowModel: getCoreRowModel() })

  return (
    <div className="min-w-0 overflow-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="sticky top-0 bg-paper-2 text-[11px] uppercase tracking-[0.12em] text-ink-soft">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th key={header.id} className="px-2 py-2 font-medium">
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.original.id}
              onClick={() => select(row.original.id)}
              className={row.original.id === selectedId ? "bg-copper/10" : "hover:bg-ink/4"}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="border-t border-line px-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
