import { useMutation, useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { createFuelJob, fetchFuelJob } from "./api"
import { fuelPayload, useFuel } from "./store"

export function useFuelSolve() {
  const clearResult = useFuel((state) => state.clearResult)
  const setSolution = useFuel((state) => state.setSolution)
  const setJobError = useFuel((state) => state.setJobError)
  const [jobId, setJobId] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      const state = useFuel.getState()
      return createFuelJob(fuelPayload(state))
    },
    onSuccess: (job) => setJobId(job.id),
    onError: (reason: unknown) => {
      setJobError(reason instanceof Error ? reason.message : "The solver failed")
    },
  })

  const job = useQuery({
    queryKey: ["fuel-job", jobId],
    queryFn: () => fetchFuelJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "ok" || status === "error") return false
      return 400
    },
  })

  useEffect(() => {
    const view = job.data
    if (!view || view.id !== jobId) return
    if (view.status === "ok" && view.result) setSolution(view.result)
    if (view.status === "error") setJobError(view.error ?? "The solver failed")
  }, [job.data, jobId, setJobError, setSolution])

  const running =
    mutation.isPending ||
    job.data?.status === "queued" ||
    job.data?.status === "running" ||
    (jobId !== null && !job.data && !job.isError)

  return {
    solve: () => {
      clearResult()
      mutation.mutate()
    },
    running,
  }
}
