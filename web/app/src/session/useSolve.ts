import { useMutation, useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { createJob, fetchJob } from "../lib/api"
import { scenarioPayload, useStudio } from "../scenario/store"

export function useSolve() {
  const solver = useStudio((state) => state.solver)
  const timeBudgetS = useStudio((state) => state.timeBudgetS)
  const seed = useStudio((state) => state.seed)
  const clearResult = useStudio((state) => state.clearResult)
  const setSolution = useStudio((state) => state.setSolution)
  const setJobError = useStudio((state) => state.setJobError)
  const [jobId, setJobId] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      const state = useStudio.getState()
      if (!state.solver) throw new Error("Choose a solver")
      return createJob({
        scenario: scenarioPayload(state),
        solver: state.solver,
        time_budget_s: state.timeBudgetS,
        seed: state.seed,
      })
    },
    onSuccess: (job) => setJobId(job.id),
  })

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId as string),
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
    error: mutation.error instanceof Error ? mutation.error.message : job.error instanceof Error ? job.error.message : null,
    solver,
    timeBudgetS,
    seed,
  }
}
