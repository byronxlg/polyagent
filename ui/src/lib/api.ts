const API_BASE_URL = 'http://localhost:8000';
const DEFAULT_LIMIT = 30;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface Principal {
  id: string;
  username: string;
  principal_type: 'human' | 'ai_agent' | 'system';
  email: string | null;
  created_at: string;
}

export interface Simulation {
  id: string;
  principal_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Model {
  id: string;
  name: string;
  provider_name: string;
  provider: string;
  provider_model_id: string;
  description: string;
  is_reasoning: boolean;
  input_cost_per_million: string;
  output_cost_per_million: string;
}

export interface Agent {
  id: string;
  principal_id: string;
  simulation_id: string;
  model_id: string;
  created_by_principal_id: string;
  name: string | null;
  public_profile: string | null;
  memory_json: Record<string, unknown>;
  memory_text: string | null;
  is_running: boolean;
  created_at: string;
}

export type TaskStatus = 'available' | 'closed' | 'expired';

export type AgentTaskStatus = 'in_progress' | 'submitted' | 'accepted' | 'denied' | 'abandoned' | 'late' | 'not_selected';

export interface Task {
  id: string;
  simulation_id: string;
  description: string;
  reward_dollars: string;
  deadline: string;
  status: TaskStatus;
  created_at: string;
  closed_at: string | null;
}

export interface AgentTask {
  id: string;
  task_id: string;
  agent_id: string;
  status: AgentTaskStatus;
  result: string | null;
  created_at: string;
  submitted_at: string | null;
}

export interface Message {
  id: string;
  from_principal_id: string;
  to_principal_id: string;
  content: string;
  sent_at: string;
  received_at: string | null;
}

export interface Transaction {
  id: string;
  from_principal_id: string | null;
  to_principal_id: string | null;
  amount: string;
  reason: string;
  reference_id: string | null;
  timestamp: string;
}

export interface AgentBalance {
  agent_id: string;
  balance: string;
}

export interface AgentMcpUsage {
  id: string;
  agent_id: string;
  mcp_server_id: string;
  tool_name: string;
  input: string | null;
  output: string | null;
  timestamp: string;
}

// Alias for backward compatibility
export type AgentToolUsage = AgentMcpUsage;

export interface AgentModelUsage {
  id: string;
  agent_id: string;
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  total_cost: string;
  input: string;
  output: string;
  timestamp: string;
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  category: string | null;
  scope: string;
  created_by_principal_id: string;
}

export interface Server {
  id: string;
  name: string;
  description: string;
  server_type: 'system' | 'custom';
  transport: string;
  is_active: boolean;
  created_by_principal_id: string;
}

export type ActivityType = 'agent_task' | 'message' | 'transaction' | 'tool_usage' | 'model_usage';

export interface ActivityItem {
  id: string;
  type: ActivityType;
  timestamp: string;
  agent_id: string | null;
  data: Record<string, unknown>;
}

export interface ActivityResponse {
  items: ActivityItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export const api = {
  principals: {
    list: async (limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Principal>> => {
      const response = await fetch(`${API_BASE_URL}/principals?limit=${limit}&offset=${offset}`);
      return response.json();
    },
    get: async (id: string): Promise<Principal> => {
      const response = await fetch(`${API_BASE_URL}/principals/${id}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Principal not found');
        }
        throw new Error(`Failed to fetch principal: ${response.statusText}`);
      }
      return response.json();
    },
    create: async (data: { username: string; principal_type: 'human' | 'ai_agent' | 'system'; email?: string }): Promise<Principal> => {
      const response = await fetch(`${API_BASE_URL}/principals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
  },
  simulations: {
    list: async (limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Simulation>> => {
      const response = await fetch(`${API_BASE_URL}/simulations?limit=${limit}&offset=${offset}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch simulations: ${response.statusText}`);
      }
      return response.json();
    },
    get: async (id: string): Promise<Simulation> => {
      const response = await fetch(`${API_BASE_URL}/simulations/${id}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Simulation not found');
        }
        throw new Error(`Failed to fetch simulation: ${response.statusText}`);
      }
      return response.json();
    },
    create: async (data: { principal_id: string; name: string; description?: string }): Promise<Simulation> => {
      const response = await fetch(`${API_BASE_URL}/simulations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
    update: async (id: string, data: { name?: string; description?: string; status?: string }): Promise<Simulation> => {
      const response = await fetch(`${API_BASE_URL}/simulations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
    delete: async (id: string): Promise<{ message: string }> => {
      const response = await fetch(`${API_BASE_URL}/simulations/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete simulation');
      }
      return response.json();
    },
    reset: async (): Promise<{ message: string }> => {
      const response = await fetch(`${API_BASE_URL}/reset`, {
        method: 'DELETE',
      });
      return response.json();
    },
  },
  models: {
    list: async (limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Model>> => {
      const response = await fetch(`${API_BASE_URL}/models?limit=${limit}&offset=${offset}`);
      return response.json();
    },
    create: async (data: Omit<Model, 'id'>): Promise<Model> => {
      const response = await fetch(`${API_BASE_URL}/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
    delete: async (id: string): Promise<{ message: string }> => {
      const response = await fetch(`${API_BASE_URL}/models/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete model');
      }
      return response.json();
    },
  },
  agents: {
    list: async (limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Agent>> => {
      const response = await fetch(`${API_BASE_URL}/agents?limit=${limit}&offset=${offset}`);
      return response.json();
    },
    get: async (id: string): Promise<Agent> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Agent not found');
        }
        throw new Error(`Failed to fetch agent: ${response.statusText}`);
      }
      return response.json();
    },
    create: async (data: {
      simulation_id: string;
      model_id: string;
      created_by_principal_id: string;
      name?: string;
      initial_balance?: string;
      memory_json?: Record<string, unknown>;
      memory_text?: string;
    }): Promise<Agent> => {
      const response = await fetch(`${API_BASE_URL}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulation_id: data.simulation_id,
          model_id: data.model_id,
          created_by_principal_id: data.created_by_principal_id,
          name: data.name,
          initial_balance: data.initial_balance || '0.10',
          memory_json: data.memory_json || {},
          memory_text: data.memory_text || null,
        }),
      });
      return response.json();
    },
    update: async (id: string, data: { name?: string; public_profile?: string }): Promise<Agent> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
    getBalance: async (id: string): Promise<AgentBalance> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}/balance`);
      return response.json();
    },
    getServers: async (id: string): Promise<Server[]> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}/servers`);
      return response.json();
    },
    tick: async (id: string): Promise<{ message: string; result: string }> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}/tick`, {
        method: 'POST',
      });
      return response.json();
    },
    tickAll: async (): Promise<{ results: Array<{ agent_id: string; status: string; result?: string; message?: string }> }> => {
      const response = await fetch(`${API_BASE_URL}/agents/tick-all`, {
        method: 'POST',
      });
      return response.json();
    },
    tickAllBackground: async (): Promise<{ message: string }> => {
      const response = await fetch(`${API_BASE_URL}/agents/tick-all-background`, {
        method: 'POST',
      });
      return response.json();
    },
    delete: async (id: string): Promise<{ message: string }> => {
      const response = await fetch(`${API_BASE_URL}/agents/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete agent');
      }
      return response.json();
    },
  },
  tasks: {
    list: async (availableOnly = false, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Task>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (availableOnly) params.set('available_only', 'true');
      const response = await fetch(`${API_BASE_URL}/tasks?${params}`);
      return response.json();
    },
    create: async (data: { simulation_id: string; created_by_principal_id: string; description: string; reward_dollars: string; deadline: string }): Promise<Task> => {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to create task' }));
        throw new Error(error.detail || 'Failed to create task');
      }
      return response.json();
    },
    update: async (taskId: string, data: { deadline?: string; status?: string }): Promise<Task> => {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return response.json();
    },
  },
  agentTasks: {
    list: async (agentId?: string, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<AgentTask>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (agentId) params.set('agent_id', agentId);
      const response = await fetch(`${API_BASE_URL}/agent-tasks?${params}`);
      return response.json();
    },
    accept: async (agentTaskId: string): Promise<AgentTask> => {
      const response = await fetch(`${API_BASE_URL}/agent-tasks/${agentTaskId}/accept`, {
        method: 'POST',
      });
      return response.json();
    },
    deny: async (agentTaskId: string): Promise<AgentTask> => {
      const response = await fetch(`${API_BASE_URL}/agent-tasks/${agentTaskId}/deny`, {
        method: 'POST',
      });
      return response.json();
    },
  },
  messages: {
    list: async (agentId?: string, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Message>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (agentId) params.set('agent_id', agentId);
      const response = await fetch(`${API_BASE_URL}/messages?${params}`);
      return response.json();
    },
    getInbox: async (agentId: string): Promise<Message[]> => {
      const response = await fetch(`${API_BASE_URL}/agents/${agentId}/inbox`);
      return response.json();
    },
    send: async (data: { from_principal_id: string; to_principal_id: string; content: string }): Promise<Message> => {
      const response = await fetch(`${API_BASE_URL}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to send message');
      }
      return response.json();
    },
  },
  transactions: {
    list: async (agentId?: string, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<Transaction>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (agentId) params.set('agent_id', agentId);
      const response = await fetch(`${API_BASE_URL}/transactions?${params}`);
      return response.json();
    },
  },
  agentToolUsage: {
    list: async (agentId?: string, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<AgentMcpUsage>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (agentId) params.set('agent_id', agentId);
      const response = await fetch(`${API_BASE_URL}/agent-mcp-usage?${params}`);
      return response.json();
    },
  },
  agentModelUsage: {
    list: async (agentId?: string, limit = DEFAULT_LIMIT, offset = 0): Promise<PaginatedResponse<AgentModelUsage>> => {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (agentId) params.set('agent_id', agentId);
      const response = await fetch(`${API_BASE_URL}/agent-model-usage?${params}`);
      return response.json();
    },
  },
  activity: {
    list: async (options?: {
      agentId?: string;
      types?: ActivityType[];
      limit?: number;
      offset?: number;
    }): Promise<ActivityResponse> => {
      const params = new URLSearchParams();
      params.set('limit', String(options?.limit ?? DEFAULT_LIMIT));
      params.set('offset', String(options?.offset ?? 0));
      if (options?.agentId) params.set('agent_id', options.agentId);
      if (options?.types?.length) params.set('types', options.types.join(','));
      const response = await fetch(`${API_BASE_URL}/activity?${params}`);
      return response.json();
    },
  },
};
