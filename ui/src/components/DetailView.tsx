import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { Play, ChevronLeft, ChevronRight, ExternalLink, ChevronDown, Loader2, Copy, Check, Users, ListTodo } from 'lucide-react';
import { toast } from 'sonner';
import Markdown from 'react-markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDateTime, formatDateTimeShort } from '@/lib/utils';
import type { SimulationData } from '@/hooks/useSimulationData';
import type { Tool, Transaction, Principal } from '@/lib/api';
import { api } from '@/lib/api';
import { TaskList } from '@/components/TaskList';
import { ResourceNotFound } from '@/components/ResourceNotFound';

export type SelectedItem =
  | { type: 'task'; id: string }
  | { type: 'agent'; id: string }
  | { type: 'model'; id: string }
  | { type: 'principal'; id: string }
  | null;

interface DetailViewProps {
  selected: SelectedItem;
  simulationData: SimulationData;
  onAcceptSubmission: (agentTaskId: string) => void;
  onDenySubmission: (agentTaskId: string) => void;
  onRunAgent: (agentId: string) => void;
  processingSubmission: string | null;
  runningAgentId: string | null;
}

// Group tools by category
function groupToolsByCategory(tools: Tool[]): Record<string, Tool[]> {
  return tools.reduce<Record<string, Tool[]>>((acc, tool) => {
    const category = tool.category || 'other';
    if (!acc[category]) acc[category] = [];
    acc[category].push(tool);
    return acc;
  }, {});
}

// ID Copy Button Component
function IDCopyButton({ id, label = 'ID' }: { id: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(id);
    setCopied(true);
    toast.success(`${label} copied to clipboard`);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border rounded-lg p-3 bg-muted/20">
      <div className="flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <span className="text-xs text-muted-foreground block mb-1">{label}</span>
          <p className="text-sm font-mono break-all">{id}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="h-8 w-8 p-0 flex-shrink-0"
        >
          {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}

// Agent detail view component
interface AgentDetailProps {
  agent: SimulationData['agents'][0];
  simulationData: SimulationData;
  onRunAgent: (agentId: string) => void;
  runningAgentId: string | null;
}

function AgentDetailView({ agent, simulationData, onRunAgent, runningAgentId }: AgentDetailProps) {
  const { models, agentTasks, transactions, messages, agentBalances, agentTools, agentToolUsage, agentModelUsage, getModelName } = simulationData;

  const balance = agentBalances[agent.id] || '0';
  const balanceNum = parseFloat(balance);
  const agentTransactions = transactions.filter(
    (t) => t.from_principal_id === agent.principal_id || t.to_principal_id === agent.principal_id
  );
  const agentMessages = messages.filter(
    (m) => m.from_principal_id === agent.principal_id || m.to_principal_id === agent.principal_id
  );
  const agentTasksList = agentTasks.filter((at) => at.agent_id === agent.id);
  const tools = agentTools[agent.id] || [];
  const toolsByCategory = groupToolsByCategory(tools);

  // Agent activity (tool usage and model usage)
  const toolUsages = agentToolUsage.filter((tu) => tu.agent_id === agent.id);
  const modelUsages = agentModelUsage.filter((mu) => mu.agent_id === agent.id);

  // Combine and sort activity by timestamp
  const agentActivity = [
    ...toolUsages.map((tu) => ({ type: 'tool' as const, data: tu, timestamp: new Date(tu.timestamp) })),
    ...modelUsages.map((mu) => ({ type: 'model' as const, data: mu, timestamp: new Date(mu.timestamp) })),
  ].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

  const model = models.find((m) => m.id === agent.model_id);

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex flex-col flex-1 min-h-0">
        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="relative inline-flex items-center justify-center w-10 h-10 rounded-full bg-zinc-700 text-white text-lg font-bold">
              {agent.is_running ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Users className="h-5 w-5" />
              )}
              {agent.is_running && (
                <span className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-amber-500 rounded-full animate-pulse" />
              )}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-2xl font-bold">
                  {agent.name || 'Agent'}
                </h2>
                {agent.is_running && (
                  <Badge className="bg-amber-500 text-xs">Running</Badge>
                )}
              </div>
              <span className="text-sm text-muted-foreground">{getModelName(agent.model_id)}</span>
            </div>
          </div>
          <Button
            onClick={() => onRunAgent(agent.id)}
            disabled={runningAgentId === agent.id || agent.is_running}
            size="sm"
            variant="outline"
          >
            <Play className={`h-4 w-4 mr-2 ${runningAgentId === agent.id ? 'animate-pulse' : ''}`} />
            Run
          </Button>
        </div>

        {/* Tabbed Content */}
        <Tabs defaultValue="profile" className="flex-1 flex flex-col min-h-0">
          <TabsList className="flex-shrink-0">
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="tasks">Tasks ({agentTasksList.length})</TabsTrigger>
            <TabsTrigger value="activity">Activity</TabsTrigger>
            <TabsTrigger value="usage">Usage ({agentActivity.length})</TabsTrigger>
            <TabsTrigger value="tools">Tools ({tools.length})</TabsTrigger>
            <TabsTrigger value="memory">Memory</TabsTrigger>
          </TabsList>

          {/* Profile Tab */}
          <TabsContent value="profile" className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="space-y-6 pr-4">
                {/* ID */}
                <IDCopyButton id={agent.id} label="Agent ID" />

                {/* High Level Details */}
                <div className="border rounded-lg p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-4">Details</h3>
                  <div className="space-y-4">
                    <div>
                      <span className="text-xs text-muted-foreground">Name</span>
                      <p className="text-base mt-1">{agent.name || <span className="text-muted-foreground italic">Unnamed</span>}</p>
                    </div>
                    {agent.public_profile && (
                      <div>
                        <span className="text-xs text-muted-foreground">Profile</span>
                        <p className="text-sm mt-1 whitespace-pre-wrap text-muted-foreground">{agent.public_profile}</p>
                      </div>
                    )}
                    <div>
                      <span className="text-xs text-muted-foreground">Model</span>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-base">{model?.name || 'Unknown'}</span>
                        {model && (
                          <>
                            <Badge variant="outline" className="text-xs">{model.provider_name}</Badge>
                            {model.is_reasoning && <Badge variant="secondary" className="text-xs">Reasoning</Badge>}
                          </>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Created</span>
                      <p className="text-sm mt-1">{formatDateTime(agent.created_at)}</p>
                    </div>
                  </div>
                </div>

                {/* Summary Stats */}
                <div className="border rounded-lg p-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-4">Summary</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Balance</span>
                      <p className={`text-2xl font-mono font-bold ${balanceNum < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                        ${balanceNum.toFixed(4)}
                      </p>
                    </div>
                    <div className="border-t pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-muted-foreground">Tasks</span>
                        <span className="text-lg font-semibold">{agentTasksList.length}</span>
                      </div>
                      {agentTasksList.length > 0 && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Accepted:</span>
                            <span>{agentTasksList.filter(at => at.status === 'accepted').length}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Submitted:</span>
                            <span>{agentTasksList.filter(at => at.status === 'submitted').length}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">In Progress:</span>
                            <span>{agentTasksList.filter(at => at.status === 'in_progress').length}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Denied:</span>
                            <span>{agentTasksList.filter(at => at.status === 'denied').length}</span>
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="border-t pt-4 flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Transactions</span>
                      <span className="text-lg font-semibold">{agentTransactions.length}</span>
                    </div>
                    <div className="border-t pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-muted-foreground">Messages</span>
                        <span className="text-lg font-semibold">{agentMessages.length}</span>
                      </div>
                      {agentMessages.length > 0 && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Sent:</span>
                            <span>{agentMessages.filter(m => m.from_principal_id === agent.principal_id).length}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Received:</span>
                            <span>{agentMessages.filter(m => m.to_principal_id === agent.principal_id).length}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Memory - Collapsible */}
                <Collapsible>
                  <div className="border rounded-lg overflow-hidden">
                    <CollapsibleTrigger className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted/50 transition-colors">
                      <h3 className="text-sm font-medium">Memory</h3>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {Object.keys(agent.memory_json || {}).length} keys, {agent.memory_text ? `${agent.memory_text.length} chars` : '0 chars'}
                        </Badge>
                        <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-180" />
                      </div>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="border-t p-4">
                        <div className="grid grid-cols-2 gap-4">
                          {/* Structured Memory (JSON) */}
                          <div>
                            <h4 className="text-xs font-semibold text-muted-foreground mb-2">Structured Memory</h4>
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                              {agent.memory_json && Object.keys(agent.memory_json).length > 0 ? (
                                Object.entries(agent.memory_json).map(([key, value]) => (
                                  <div key={key} className="p-2 bg-muted/50 rounded">
                                    <div className="text-xs font-medium text-muted-foreground mb-1 font-mono">{key}</div>
                                    <p className="text-xs whitespace-pre-wrap break-words">
                                      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                                    </p>
                                  </div>
                                ))
                              ) : (
                                <p className="text-xs text-muted-foreground text-center py-4">No structured memory</p>
                              )}
                            </div>
                          </div>

                          {/* Notes (Markdown) */}
                          <div>
                            <h4 className="text-xs font-semibold text-muted-foreground mb-2">Notes</h4>
                            <div className="p-2 bg-muted/50 rounded max-h-64 overflow-y-auto">
                              {agent.memory_text ? (
                                <div className="text-xs whitespace-pre-wrap">
                                  <Markdown>{agent.memory_text}</Markdown>
                                </div>
                              ) : (
                                <p className="text-xs text-muted-foreground text-center py-4">No notes</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Tasks Tab */}
          <TabsContent value="tasks" className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="pr-4">
                <TaskList
                  agentId={agent.id}
                  simulationData={simulationData}
                  variant="compact"
                  showLoadMore={false}
                />
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Activity Tab */}
          <TabsContent value="activity" className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="space-y-6 pr-4">
                {/* Transactions */}
                {agentTransactions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">Transactions ({agentTransactions.length})</h3>
                    <TransactionsTable transactions={agentTransactions} principalId={agent.principal_id} />
                  </div>
                )}

                {/* Messages */}
                {agentMessages.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">Messages</h3>
                    <div className="space-y-2">
                      {agentMessages.slice(0, 10).map((msg) => (
                        <div key={msg.id} className="p-2 border rounded-lg">
                          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                            <span>
                              {msg.from_principal_id === agent.principal_id
                                ? `To: ${msg.to_principal_id.slice(0, 8)}...`
                                : `From: ${msg.from_principal_id.slice(0, 8)}...`}
                            </span>
                            <span>{formatDateTimeShort(msg.sent_at)}</span>
                          </div>
                          <p className="text-sm">{msg.content}</p>
                        </div>
                      ))}
                      {agentMessages.length > 10 && (
                        <p className="text-xs text-muted-foreground text-center">
                          +{agentMessages.length - 10} more messages
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {agentTransactions.length === 0 && agentMessages.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">No activity yet</p>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Usage Tab */}
          <TabsContent value="usage" className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="space-y-2 pr-4">
                {agentActivity.length > 0 ? (
                  agentActivity.map((item) => {
                    if (item.type === 'tool') {
                      const tu = item.data;
                      return (
                        <Collapsible key={`tool-${tu.id}`}>
                          <div className="border rounded-lg overflow-hidden">
                            <CollapsibleTrigger asChild>
                              <div className="flex items-center gap-2 p-2 cursor-pointer hover:bg-muted/50 transition-colors">
                                <Badge className="bg-amber-500 text-[10px] px-1.5 py-0 h-4">TOOL</Badge>
                                <span className="text-sm font-medium">{tu.tool_name}</span>
                                <span className="text-xs text-muted-foreground flex-1 truncate">
                                  {tu.input.slice(0, 30)}{tu.input.length > 30 ? '...' : ''}
                                </span>
                                <span className="text-xs text-muted-foreground">{formatDateTimeShort(tu.timestamp)}</span>
                                <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-180" />
                              </div>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="px-3 pb-3 pt-0 border-t text-xs space-y-2">
                                <div className="mt-2">
                                  <span className="text-muted-foreground">Input:</span>
                                  <pre className="mt-1 p-2 bg-muted/50 rounded font-mono overflow-x-auto">{tu.input}</pre>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Output:</span>
                                  <pre className="mt-1 p-2 bg-muted/50 rounded font-mono overflow-x-auto max-h-32 overflow-y-auto">{tu.output}</pre>
                                </div>
                              </div>
                            </CollapsibleContent>
                          </div>
                        </Collapsible>
                      );
                    } else {
                      const mu = item.data;
                      const modelUsed = models.find((m) => m.id === mu.model_id);
                      const cost = parseFloat(mu.total_cost);
                      return (
                        <Collapsible key={`model-${mu.id}`}>
                          <div className="border rounded-lg overflow-hidden">
                            <CollapsibleTrigger asChild>
                              <div className="flex items-center gap-2 p-2 cursor-pointer hover:bg-muted/50 transition-colors">
                                <Badge className="bg-rose-500 text-[10px] px-1.5 py-0 h-4">LLM</Badge>
                                <span className="text-sm font-medium">{modelUsed?.name || 'Model'}</span>
                                <span className="text-xs text-muted-foreground">
                                  {mu.input_tokens}+{mu.output_tokens} tokens
                                </span>
                                <span className="text-xs font-mono text-red-400">-${cost.toFixed(6)}</span>
                                <span className="text-xs text-muted-foreground flex-1 text-right">{formatDateTimeShort(mu.timestamp)}</span>
                                <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-180" />
                              </div>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="px-3 pb-3 pt-0 border-t text-xs space-y-2">
                                <div className="mt-2">
                                  <span className="text-muted-foreground">Input:</span>
                                  <pre className="mt-1 p-2 bg-muted/50 rounded font-mono overflow-x-auto max-h-24 overflow-y-auto">{mu.input}</pre>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Output:</span>
                                  <pre className="mt-1 p-2 bg-muted/50 rounded font-mono overflow-x-auto max-h-24 overflow-y-auto">{mu.output}</pre>
                                </div>
                              </div>
                            </CollapsibleContent>
                          </div>
                        </Collapsible>
                      );
                    }
                  })
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-8">No usage data yet</p>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Tools Tab */}
          <TabsContent value="tools" className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="space-y-3 pr-4">
                {tools.length > 0 ? (
                  Object.entries(toolsByCategory).map(([category, categoryTools]) => (
                    <div key={category}>
                      <span className="text-xs text-muted-foreground capitalize">{category}</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {categoryTools.map((tool) => (
                          <Badge key={tool.id} variant="secondary" className="text-xs">
                            {tool.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-8">No tools available</p>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Memory Tab */}
          <TabsContent value="memory" className="flex-1 min-h-0">
            <div className="grid grid-cols-2 gap-4 h-full pr-4">
              {/* Structured Memory (JSON) */}
              <div className="flex flex-col h-full">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">Structured Memory</h3>
                  <Badge variant="outline" className="text-xs">
                    {Object.keys(agent.memory_json || {}).length} keys
                  </Badge>
                </div>
                <ScrollArea className="flex-1">
                  <div className="space-y-2">
                    {agent.memory_json && Object.keys(agent.memory_json).length > 0 ? (
                      Object.entries(agent.memory_json).map(([key, value]) => (
                        <div key={key} className="p-3 bg-muted/50 rounded">
                          <div className="text-xs font-medium text-muted-foreground mb-1 font-mono">{key}</div>
                          <p className="text-sm whitespace-pre-wrap break-words">
                            {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-8">No structured memory</p>
                    )}
                  </div>
                </ScrollArea>
              </div>

              {/* Notes (Markdown) */}
              <div className="flex flex-col h-full">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">Notes</h3>
                  <Badge variant="outline" className="text-xs">
                    {agent.memory_text ? `${agent.memory_text.length} chars` : 'empty'}
                  </Badge>
                </div>
                <ScrollArea className="flex-1">
                  <div className="p-3 bg-muted/50 rounded min-h-32">
                    {agent.memory_text ? (
                      <div className="text-sm whitespace-pre-wrap">
                        <Markdown>{agent.memory_text}</Markdown>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-8">No notes</p>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

// Transactions table with pagination
function TransactionsTable({
  transactions,
  principalId,
  pageSize = 10,
}: {
  transactions: Transaction[];
  principalId: string;
  pageSize?: number;
}) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(transactions.length / pageSize);
  const paginatedTransactions = transactions.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div>
      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">Amount</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead className="w-36 text-right">Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedTransactions.map((tx) => (
              <TableRow key={tx.id}>
                <TableCell>
                  <span className={`font-mono font-semibold ${tx.to_principal_id === principalId ? 'text-emerald-400' : 'text-red-400'}`}>
                    {tx.to_principal_id === principalId ? '+' : '-'}${parseFloat(tx.amount).toFixed(4)}
                  </span>
                </TableCell>
                <TableCell className="text-muted-foreground">{tx.reason}</TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">
                  {formatDateTimeShort(tx.timestamp)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-muted-foreground">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, transactions.length)} of {transactions.length}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs px-2">
              {page + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function DetailView({
  selected,
  simulationData,
  onAcceptSubmission,
  onDenySubmission,
  onRunAgent,
  processingSubmission,
  runningAgentId,
}: DetailViewProps) {
  const { agents, models, tasks, agentTasks, agentBalances, getStatusColor, getAgentName } = simulationData;
  const [principal, setPrincipal] = useState<Principal | null>(null);

  useEffect(() => {
    if (selected?.type === 'principal') {
      const loadPrincipal = async () => {
        try {
          const principalData = await api.principals.get(selected.id);
          setPrincipal(principalData);
        } catch (error) {
          console.error('Failed to load principal:', error);
        }
      };
      loadPrincipal();
    } else {
      setPrincipal(null);
    }
  }, [selected]);

  if (!selected) return null;

  if (selected.type === 'task') {
    const task = tasks.find((t) => t.id === selected.id);
    if (!task) return <ResourceNotFound resourceType="task" resourceId={selected.id} />;

    const taskAgentTasks = agentTasks.filter((at) => at.task_id === task.id);
    const pendingSubmission = taskAgentTasks.find((at) => at.status === 'submitted');
    const acceptedSubmission = taskAgentTasks.find((at) => at.status === 'accepted');

    return (
      <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
        <div className="flex flex-col flex-1 min-h-0">
          <div className="flex items-center gap-3 mb-4 flex-shrink-0">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-zinc-700 text-white text-lg font-bold">
              <ListTodo className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-2xl font-bold">Task</h2>
            </div>
            <Badge className={`${getStatusColor(task.status)} text-sm`}>{task.status}</Badge>
          </div>

          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-6 pr-4">
              {/* ID */}
              <IDCopyButton id={task.id} label="Task ID" />

              {/* Task Description and Response */}
              <div className="border rounded-lg p-6 bg-muted/30">
                <h3 className="text-sm font-medium text-muted-foreground mb-3">Task Description</h3>
                <p className="text-xl leading-relaxed">{task.description}</p>

                {acceptedSubmission && acceptedSubmission.result && (
                  <>
                    <div className="my-6 border-t" />
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">Response</h3>
                    <p className="text-xl leading-relaxed whitespace-pre-wrap mb-3">{acceptedSubmission.result}</p>
                    <div className="text-xs text-muted-foreground">
                      By {getAgentName(acceptedSubmission.agent_id)} • {formatDateTimeShort(acceptedSubmission.submitted_at!)}
                    </div>
                  </>
                )}
              </div>

              {/* Details */}
              <div className="grid grid-cols-2 gap-4">
                <div className="border rounded-lg p-4">
                  <span className="text-sm text-muted-foreground">Reward</span>
                  <p className="text-2xl font-mono font-semibold text-emerald-400">${parseFloat(task.reward_dollars).toFixed(4)}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <span className="text-sm text-muted-foreground">Working Agents</span>
                  <p className="text-2xl font-semibold">{taskAgentTasks.length}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <span className="text-sm text-muted-foreground">Deadline</span>
                  <p className="text-sm mt-1">{formatDateTime(task.deadline)}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <span className="text-sm text-muted-foreground">Created</span>
                  <p className="text-sm mt-1">{formatDateTime(task.created_at)}</p>
                </div>
              </div>

              {/* Pending Submission */}
              {pendingSubmission && (
                <div className="border-2 rounded-lg p-6 bg-amber-500/10 border-amber-500/50">
                  <h3 className="text-base font-semibold mb-4 flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-amber-500 animate-pulse" />
                    Pending Submission from {getAgentName(pendingSubmission.agent_id)}
                  </h3>
                  {pendingSubmission.result && (
                    <div className="mb-4">
                      <span className="text-sm font-medium text-muted-foreground">Submission:</span>
                      <div className="mt-2 p-4 bg-background/50 rounded-lg border">
                        <p className="text-base leading-relaxed whitespace-pre-wrap">{pendingSubmission.result}</p>
                      </div>
                    </div>
                  )}
                  <div className="text-sm text-muted-foreground mb-4">
                    Submitted: {formatDateTimeShort(pendingSubmission.submitted_at!)}
                  </div>
                  <div className="flex gap-3">
                    <Button
                      onClick={() => onAcceptSubmission(pendingSubmission.id)}
                      disabled={processingSubmission === pendingSubmission.id}
                      className="flex-1 bg-emerald-500 hover:bg-emerald-600 h-11"
                    >
                      Accept Submission
                    </Button>
                    <Button
                      onClick={() => onDenySubmission(pendingSubmission.id)}
                      disabled={processingSubmission === pendingSubmission.id}
                      variant="destructive"
                      className="flex-1 h-11"
                    >
                      Deny Submission
                    </Button>
                  </div>
                </div>
              )}

              {/* Submissions */}
              {taskAgentTasks.length > 0 && (
                <div>
                  <h3 className="text-base font-semibold mb-4">Submissions</h3>
                  <div className="space-y-3">
                    {taskAgentTasks.map((at) => (
                      <div key={at.id} className="p-4 border rounded-lg hover:bg-muted/30 transition-colors">
                        <div className="flex items-center gap-3 mb-2">
                          <Link
                            to="/simulations/$simulationId/agents/$id"
                            params={{ simulationId: String(simulationData.currentSimulation?.id), id: String(at.agent_id) }}
                            className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600 transition-colors cursor-pointer"
                          >
                            <Users className="h-4 w-4" />
                          </Link>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Link
                                to="/simulations/$simulationId/agents/$id"
                                params={{ simulationId: String(simulationData.currentSimulation?.id), id: String(at.agent_id) }}
                                className="inline-flex items-center gap-1 font-medium hover:underline cursor-pointer"
                              >
                                {getAgentName(at.agent_id)}
                                <ExternalLink className="h-3 w-3" />
                              </Link>
                              <Badge className={`${getStatusColor(at.status)}`}>{at.status}</Badge>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              Started {formatDateTimeShort(at.created_at)}
                            </span>
                          </div>
                        </div>
                        {at.result && (
                          <div className="mt-3 pt-3 border-t">
                            <span className="text-sm font-medium text-muted-foreground">Submission:</span>
                            <div className="mt-2 p-3 bg-muted/50 rounded">
                              <p className="text-base leading-relaxed whitespace-pre-wrap">{at.result}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </div>
    );
  }

  if (selected.type === 'agent') {
    const agent = agents.find((a) => a.id === selected.id);
    if (!agent) return <ResourceNotFound resourceType="agent" resourceId={selected.id} />;

    return (
      <AgentDetailView
        agent={agent}
        simulationData={simulationData}
        onRunAgent={onRunAgent}
        runningAgentId={runningAgentId}
      />
    );
  }

  if (selected.type === 'model') {
    const model = models.find((m) => m.id === selected.id);
    if (!model) return <ResourceNotFound resourceType="model" resourceId={selected.id} />;

    const modelAgents = agents.filter((a) => a.model_id === model.id);

    return (
      <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
        <div className="flex flex-col flex-1 min-h-0">
          <div className="flex items-center gap-3 mb-4 flex-shrink-0">
            <h2 className="text-2xl font-bold">{model.name}</h2>
            <Badge variant="outline">{model.provider_name}</Badge>
            {model.is_reasoning && <Badge variant="secondary">Reasoning</Badge>}
          </div>

          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-6 pr-4">
              {/* ID */}
              <IDCopyButton id={model.id} label="Model ID" />

              {/* Description */}
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Description</h3>
                <p className="text-sm">{model.description}</p>
              </div>

              {/* Costs */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 border rounded-lg">
                  <span className="text-sm text-muted-foreground">Input Cost</span>
                  <p className="text-lg font-mono">${parseFloat(model.input_cost_per_million).toFixed(2)}</p>
                  <span className="text-xs text-muted-foreground">per million tokens</span>
                </div>
                <div className="p-4 border rounded-lg">
                  <span className="text-sm text-muted-foreground">Output Cost</span>
                  <p className="text-lg font-mono">${parseFloat(model.output_cost_per_million).toFixed(2)}</p>
                  <span className="text-xs text-muted-foreground">per million tokens</span>
                </div>
              </div>

              {/* Agents using this model */}
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">
                  Agents using this model ({modelAgents.length})
                </h3>
                {modelAgents.length > 0 ? (
                  <div className="space-y-2">
                    {modelAgents.map((agent) => {
                      const agentBalance = parseFloat(agentBalances[agent.id] || '0');
                      return (
                        <div key={agent.id} className="flex items-center gap-3 p-2 border rounded-lg">
                          <Link
                            to="/simulations/$simulationId/agents/$id"
                            params={{ simulationId: String(simulationData.currentSimulation?.id), id: String(agent.id) }}
                            className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-700 text-white text-sm font-bold hover:bg-zinc-600 transition-colors cursor-pointer"
                          >
                            {agent.id}
                          </Link>
                          <Link
                            to="/simulations/$simulationId/agents/$id"
                            params={{ simulationId: String(simulationData.currentSimulation?.id), id: String(agent.id) }}
                            className="inline-flex items-center gap-1 text-sm flex-1 text-left hover:underline cursor-pointer"
                          >
                            {getAgentName(agent.id)}
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                          <span className={`font-mono text-sm ${agentBalance < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                            ${agentBalance.toFixed(4)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No agents using this model</p>
                )}
              </div>
            </div>
          </ScrollArea>
        </div>
      </div>
    );
  }

  if (selected.type === 'principal') {
    if (!principal) return <ResourceNotFound resourceType="principal" resourceId={selected.id} />;

    const principalAgents = agents.filter((a) => a.principal_id === principal.id);
    const getPrincipalTypeBadge = (principalType: string) => {
      const colors = {
        human: 'bg-blue-500',
        ai_agent: 'bg-purple-500',
        system: 'bg-gray-500',
      };
      return colors[principalType as keyof typeof colors] || 'bg-gray-500';
    };

    return (
      <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
        <div className="flex flex-col flex-1 min-h-0">
          <div className="flex items-center gap-3 mb-4 flex-shrink-0">
            <h2 className="text-2xl font-bold">{principal.username}</h2>
            <Badge className={`${getPrincipalTypeBadge(principal.principal_type)} text-xs`}>
              {principal.principal_type}
            </Badge>
          </div>

          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-6 pr-4">
              <IDCopyButton id={principal.id} label="Principal ID" />

              {principal.email && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Email</h3>
                  <p className="text-sm">{principal.email}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Created</h3>
                <p className="text-sm">{formatDateTime(principal.created_at)}</p>
              </div>

              {principalAgents.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">
                    Agents ({principalAgents.length})
                  </h3>
                  <div className="space-y-2">
                    {principalAgents.map((agent) => {
                      const agentBalance = parseFloat(agentBalances[agent.id] || '0');
                      return (
                        <div key={agent.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50">
                          <Link
                            to="/simulations/$simulationId/agents/$id"
                            params={{
                              simulationId: String(agent.simulation_id),
                              id: String(agent.id),
                            }}
                            className="inline-flex items-center gap-1 text-sm flex-1 text-left hover:underline cursor-pointer"
                          >
                            {getAgentName(agent.id)}
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                          <span className={`font-mono text-sm ${agentBalance < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                            ${agentBalance.toFixed(4)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </div>
    );
  }

  return null;
}
