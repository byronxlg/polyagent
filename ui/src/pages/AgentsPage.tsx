import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { Loader2, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDateTimeShort } from '@/lib/utils';
import { api, type Agent } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

interface AgentsPageProps {
  simulationData: SimulationData;
}

export function AgentsPage({ simulationData }: AgentsPageProps) {
  const { agents: initialAgents, agentBalances, agentTasks, getModelName, currentSimulation } = simulationData;
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    setAgents(initialAgents);
    setHasMore(initialAgents.length >= 30);
  }, [initialAgents]);

  const loadMore = async () => {
    setIsLoadingMore(true);
    try {
      const res = await api.agents.list(30, agents.length);
      setAgents((prev) => [...prev, ...res.items]);
      setHasMore(res.has_more);
      setTotal(res.total);
    } catch (error) {
      console.error('Failed to load more agents:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Count tasks per agent
  const agentTaskCounts = agents.reduce<Record<string, number>>((acc, agent) => {
    acc[agent.id] = agentTasks.filter((at) => at.agent_id === agent.id).length;
    return acc;
  }, {});

  // Calculate submission approval rate per agent (accepted / total submissions)
  const agentApprovalRates = agents.reduce<Record<string, number | null>>((acc, agent) => {
    const tasks = agentTasks.filter((at) => at.agent_id === agent.id);
    const accepted = tasks.filter((at) => at.status === 'accepted').length;
    const submitted = tasks.filter((at) => at.status === 'submitted').length;
    const denied = tasks.filter((at) => at.status === 'denied').length;
    const notSelected = tasks.filter((at) => at.status === 'not_selected').length;
    const late = tasks.filter((at) => at.status === 'late').length;
    const totalSubmissions = accepted + submitted + denied + notSelected + late;
    acc[agent.id] = totalSubmissions > 0 ? (accepted / totalSubmissions) * 100 : null;
    return acc;
  }, {});

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Agents</h1>
        <span className="text-sm text-muted-foreground">
          {agents.length}{total !== null ? ` of ${total}` : ''} agents
        </span>
      </div>

      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="w-24">Status</TableHead>
              <TableHead className="w-28 text-right">Balance</TableHead>
              <TableHead className="w-20 text-center">Tasks</TableHead>
              <TableHead className="w-32 text-center">Approval Rate</TableHead>
              <TableHead className="w-36">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {agents.map((agent) => {
              const balance = parseFloat(agentBalances[agent.id] || '0');
              const approvalRate = agentApprovalRates[agent.id];
              return (
                <TableRow key={agent.id} className="cursor-pointer hover:bg-muted/50">
                  <TableCell>
                    <Link
                      to="/simulations/$simulationId/agents/$id"
                      params={{ simulationId: String(currentSimulation?.id), id: String(agent.id) }}
                      className="inline-flex items-center gap-2 hover:underline"
                    >
                      <span className="relative inline-flex items-center justify-center w-7 h-7 rounded-full bg-zinc-700 text-white text-xs font-bold">
                        {agent.is_running ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <User className="h-4 w-4" />
                        )}
                        {agent.is_running && (
                          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                        )}
                      </span>
                      {agent.name || <span className="text-muted-foreground">Unnamed</span>}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {getModelName(agent.model_id)}
                  </TableCell>
                  <TableCell>
                    {agent.is_running ? (
                      <Badge className="bg-amber-500 text-xs">Running</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">Idle</Badge>
                    )}
                  </TableCell>
                  <TableCell className={`text-right font-mono ${balance < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                    ${balance.toFixed(4)}
                  </TableCell>
                  <TableCell className="text-center">
                    {agentTaskCounts[agent.id] || 0}
                  </TableCell>
                  <TableCell className="text-center font-mono text-sm">
                    {approvalRate !== null ? (
                      <span className={approvalRate >= 50 ? 'text-emerald-400' : 'text-amber-400'}>
                        {approvalRate.toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDateTimeShort(agent.created_at)}
                  </TableCell>
                </TableRow>
              );
            })}
            {agents.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No agents found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {hasMore && agents.length > 0 && (
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
      </ScrollArea>
    </div>
  );
}
