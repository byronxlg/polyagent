import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { Agent, Task, Message, AgentTask, Model, Transaction, AgentToolUsage, AgentModelUsage, Tool, Simulation, Principal } from '@/lib/api';

export function useSimulationData(refreshTrigger: number) {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [currentSimulation, setCurrentSimulation] = useState<Simulation | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [principals, setPrincipals] = useState<Principal[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [agentTasks, setAgentTasks] = useState<AgentTask[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [agentToolUsage, setAgentToolUsage] = useState<AgentToolUsage[]>([]);
  const [agentModelUsage, setAgentModelUsage] = useState<AgentModelUsage[]>([]);
  const [agentBalances, setAgentBalances] = useState<Record<string, string>>({});
  const [agentTools, setAgentTools] = useState<Record<string, Tool[]>>({});
  const [isLoading, setIsLoading] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [simulationsRes, agentsRes, principalsRes, modelsRes, tasksRes, messagesRes, agentTasksRes, transactionsRes, toolUsageRes, modelUsageRes] = await Promise.all([
        api.simulations.list(),
        api.agents.list(),
        api.principals.list(),
        api.models.list(),
        api.tasks.list(),
        api.messages.list(),
        api.agentTasks.list(),
        api.transactions.list(),
        api.agentToolUsage.list(),
        api.agentModelUsage.list(),
      ]);

      setSimulations(simulationsRes.items);
      if (simulationsRes.items.length > 0 && !currentSimulation) {
        setCurrentSimulation(simulationsRes.items[0]);
      }

      setAgents(agentsRes.items);
      setPrincipals(principalsRes.items);
      setModels(modelsRes.items);
      setTasks(tasksRes.items);
      setMessages(messagesRes.items);
      setAgentTasks(agentTasksRes.items);
      setTransactions(transactionsRes.items);
      setAgentToolUsage(toolUsageRes.items);
      setAgentModelUsage(modelUsageRes.items);

      const balances: Record<string, string> = {};
      const tools: Record<string, Tool[]> = {};
      for (const agent of agentsRes.items) {
        const [balance, agentToolsData] = await Promise.all([
          api.agents.getBalance(agent.id),
          api.agents.getTools(agent.id),
        ]);
        balances[agent.id] = balance.balance;
        tools[agent.id] = agentToolsData;
      }
      setAgentBalances(balances);
      setAgentTools(tools);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [currentSimulation]);

  useEffect(() => {
    loadData();
  }, [refreshTrigger, loadData]);

  const getModelName = (modelId: string) => {
    return models.find((m) => m.id === modelId)?.name || 'Unknown';
  };

  const getAgentName = (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    return agent?.name || `Agent ${agentId.slice(0, 8)}`;
  };

  const getTaskDescription = (taskId: string) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return `Task ${taskId.slice(0, 8)}`;
    const shortDesc = task.description.length > 50
      ? task.description.slice(0, 50) + '...'
      : task.description;
    return shortDesc;
  };

  const getPrincipalName = (principalId: string) => {
    const agent = agents.find((a) => a.principal_id === principalId);
    if (agent) {
      return agent.name || `Agent ${agent.id.slice(0, 8)}`;
    }
    const principal = principals.find((p) => p.id === principalId);
    return principal?.username || `Principal ${principalId.slice(0, 8)}`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available':
        return 'bg-emerald-500';
      case 'in_progress':
        return 'bg-blue-500';
      case 'submitted':
        return 'bg-amber-500';
      case 'accepted':
        return 'bg-green-500';
      case 'denied':
        return 'bg-red-500';
      case 'closed':
        return 'bg-gray-500';
      case 'abandoned':
        return 'bg-orange-500';
      default:
        return 'bg-gray-500';
    }
  };

  return {
    simulations,
    currentSimulation,
    setCurrentSimulation,
    agents,
    principals,
    models,
    tasks,
    messages,
    agentTasks,
    transactions,
    agentToolUsage,
    agentModelUsage,
    agentBalances,
    agentTools,
    isLoading,
    loadData,
    getModelName,
    getAgentName,
    getTaskDescription,
    getPrincipalName,
    getStatusColor,
  };
}

export type SimulationData = ReturnType<typeof useSimulationData>;
