import { useState, useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import { Loader2, ExternalLink, ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDateTimeShort } from '@/lib/utils'
import { api, type Task } from '@/lib/api'
import type { SimulationData } from '@/hooks/useSimulationData'

interface TaskListProps {
  initialTasks?: Task[]
  agentId?: string
  simulationData: SimulationData
  variant?: 'table' | 'compact'
  showLoadMore?: boolean
}

export function TaskList({
  initialTasks,
  agentId,
  simulationData,
  variant = 'table',
  showLoadMore = true,
}: TaskListProps) {
  const { tasks: allTasks, agentTasks, getStatusColor, currentSimulation, getTaskDescription } = simulationData
  const [tasks, setTasks] = useState<Task[]>(initialTasks || allTasks)
  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  // Filter tasks by agent if agentId is provided
  const filteredTasks = agentId
    ? tasks.filter((task) =>
        agentTasks.some((at) => at.task_id === task.id && at.agent_id === agentId)
      )
    : tasks

  // Get agent tasks for the filtered tasks
  const relevantAgentTasks = agentId
    ? agentTasks.filter((at) => at.agent_id === agentId)
    : agentTasks

  useEffect(() => {
    const sortedTasks = [...(initialTasks || allTasks)].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    setTasks(sortedTasks)
    setHasMore((initialTasks || allTasks).length >= 30)
  }, [initialTasks, allTasks])

  const loadMore = async () => {
    setIsLoadingMore(true)
    try {
      const res = await api.tasks.list(false, 30, tasks.length)
      setTasks((prev) => {
        const combined = [...prev, ...res.items]
        return combined.sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
      })
      setHasMore(res.has_more)
    } catch (error) {
      console.error('Failed to load more tasks:', error)
    } finally {
      setIsLoadingMore(false)
    }
  }

  // Count agents working on each task and check for pending submissions
  const taskAgentCounts = tasks.reduce<Record<string, number>>((acc, task) => {
    acc[task.id] = agentTasks.filter((at) => at.task_id === task.id).length
    return acc
  }, {})

  const taskPendingSubmissions = tasks.reduce<Record<string, number>>((acc, task) => {
    acc[task.id] = agentTasks.filter(
      (at) => at.task_id === task.id && at.status === 'submitted'
    ).length
    return acc
  }, {})

  if (variant === 'compact') {
    return (
      <div className="space-y-2">
        {relevantAgentTasks.length > 0 ? (
          relevantAgentTasks.map((at) => {
            const task = tasks.find((t) => t.id === at.task_id)
            const hasDetails = at.result || at.submitted_at
            return (
              <Collapsible key={at.id}>
                <div className="border rounded-lg overflow-hidden">
                  <CollapsibleTrigger asChild>
                    <div className="flex items-center gap-2 p-3 cursor-pointer hover:bg-muted/50 transition-colors">
                      <Badge className={`${getStatusColor(at.status)} text-xs flex-shrink-0`}>
                        {at.status}
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <Link
                          to="/simulations/$simulationId/tasks/$id"
                          params={{
                            simulationId: String(currentSimulation?.id),
                            id: String(at.task_id),
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-sm hover:underline cursor-pointer"
                        >
                          <span className="font-medium text-muted-foreground">"{getTaskDescription(at.task_id)}"</span>
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </Link>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        {task && (
                          <span className="text-xs font-mono text-emerald-400">
                            ${parseFloat(task.reward_dollars).toFixed(2)}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {formatDateTimeShort(at.created_at)}
                        </span>
                        {hasDetails && (
                          <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-180" />
                        )}
                      </div>
                    </div>
                  </CollapsibleTrigger>
                  {hasDetails && (
                    <CollapsibleContent>
                      <div className="px-3 pb-3 pt-2 border-t space-y-2">
                        {at.result && (
                          <div>
                            <span className="text-xs text-muted-foreground">Submission:</span>
                            <p className="text-sm mt-1 whitespace-pre-wrap">{at.result}</p>
                          </div>
                        )}
                        {at.submitted_at && (
                          <div className="text-xs text-muted-foreground">
                            Submitted: {formatDateTimeShort(at.submitted_at)}
                          </div>
                        )}
                      </div>
                    </CollapsibleContent>
                  )}
                </div>
              </Collapsible>
            )
          })
        ) : (
          <p className="text-sm text-muted-foreground text-center py-8">No tasks yet</p>
        )}
      </div>
    )
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Description</TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-24 text-right">Reward</TableHead>
            {!agentId && <TableHead className="w-20 text-center">Agents</TableHead>}
            {!agentId && <TableHead className="w-24 text-center">Pending</TableHead>}
            <TableHead className="w-36">Deadline</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredTasks.map((task) => (
            <TableRow key={task.id} className="cursor-pointer hover:bg-muted/50">
              <TableCell>
                <Link
                  to="/simulations/$simulationId/tasks/$id"
                  params={{
                    simulationId: String(currentSimulation?.id),
                    id: String(task.id),
                  }}
                  className="hover:underline"
                >
                  {task.description.length > 80
                    ? `${task.description.slice(0, 80)}...`
                    : task.description}
                </Link>
              </TableCell>
              <TableCell>
                <Badge className={`${getStatusColor(task.status)} text-xs`}>
                  {task.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right font-mono text-emerald-400">
                ${parseFloat(task.reward_dollars).toFixed(4)}
              </TableCell>
              {!agentId && (
                <TableCell className="text-center">
                  {taskAgentCounts[task.id] || 0}
                </TableCell>
              )}
              {!agentId && (
                <TableCell className="text-center">
                  {taskPendingSubmissions[task.id] > 0 ? (
                    <Badge className="bg-amber-500 text-xs">
                      {taskPendingSubmissions[task.id]}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
              )}
              <TableCell className="text-xs text-muted-foreground">
                {formatDateTimeShort(task.deadline)}
              </TableCell>
            </TableRow>
          ))}
          {filteredTasks.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={agentId ? 4 : 6}
                className="text-center text-muted-foreground py-8"
              >
                No tasks found
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      {showLoadMore && hasMore && tasks.length > 0 && !agentId && (
        <div className="flex justify-center py-4">
          <Button variant="outline" onClick={loadMore} disabled={isLoadingMore}>
            {isLoadingMore ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Loading...
              </>
            ) : (
              'Load More'
            )}
          </Button>
        </div>
      )}
    </>
  )
}
