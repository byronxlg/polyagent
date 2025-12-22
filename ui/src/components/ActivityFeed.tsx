import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, Users, Clock, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Toggle } from '@/components/ui/toggle';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatDateTimeShort } from '@/lib/utils';
import { api, type ActivityItem as ApiActivityItem, type ActivityType } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

// Helper function to format JSON/objects with proper indentation
function formatJSON(value: string): string {
  try {
    // Try to parse as JSON first
    const parsed = JSON.parse(value);
    return JSON.stringify(parsed, null, 2);
  } catch {
    // If not valid JSON, try to evaluate as Python dict/literal
    try {
      // Replace Python syntax with JSON syntax more aggressively
      let jsonLike = value
        // Replace single quotes with double quotes (but be careful with quotes inside strings)
        .replace(/'/g, '"')
        // Replace Python boolean/null values
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
        .replace(/\bNone\b/g, 'null')
        // Remove UUID() wrapper - match the full UUID pattern
        .replace(/UUID\("([a-f0-9-]+)"\)/g, '"$1"')
        .replace(/UUID\(([a-f0-9-]+)\)/g, '"$1"');

      const parsed = JSON.parse(jsonLike);
      return JSON.stringify(parsed, null, 2);
    } catch (e) {
      // If all parsing fails, try basic pretty printing with line breaks
      try {
        let formatted = value
          .replace(/,\s*/g, ',\n  ')
          .replace(/\{/g, '{\n  ')
          .replace(/\}/g, '\n}')
          .replace(/\[/g, '[\n  ')
          .replace(/\]/g, '\n]');
        return formatted;
      } catch {
        // Last resort: return original
        return value;
      }
    }
  }
}

interface ActivityFeedProps {
  simulationData: SimulationData;
}

const typeConfig = {
  agent_task: { label: 'TASK', color: 'bg-purple-500', border: 'border-l-purple-500' },
  message: { label: 'MSG', color: 'bg-blue-500', border: 'border-l-blue-500' },
  transaction: { label: 'TXN', color: 'bg-emerald-500', border: 'border-l-emerald-500' },
  tool_usage: { label: 'TOOL', color: 'bg-amber-500', border: 'border-l-amber-500' },
  model_usage: { label: 'LLM', color: 'bg-rose-500', border: 'border-l-rose-500' },
};

interface ActivityItem {
  type: ActivityType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  timestamp: Date;
  id: string;
  agentId: string | null;
}

function apiItemToActivityItem(item: ApiActivityItem): ActivityItem {
  return {
    type: item.type,
    data: item.data,
    timestamp: new Date(item.timestamp),
    id: item.id,
    agentId: item.agent_id,
  };
}

function getAgentIdFromItem(item: ActivityItem): string | null {
  switch (item.type) {
    case 'agent_task':
      return item.data.agent_id as string;
    case 'message':
      return item.data.from_agent_id as string;
    case 'transaction':
      return (item.data.from_agent_id ?? item.data.to_agent_id) as string;
    case 'tool_usage':
    case 'model_usage':
      return item.data.agent_id as string;
    default:
      return null;
  }
}

export function ActivityFeed({ simulationData }: ActivityFeedProps) {
  const { agents, models, getStatusColor, getAgentName, getTaskDescription } = simulationData;

  const [activityItems, setActivityItems] = useState<ActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const [typeFilters, setTypeFilters] = useState<Set<ActivityType>>(
    new Set(['agent_task', 'message', 'transaction', 'tool_usage', 'model_usage'])
  );
  const [agentFilter, setAgentFilter] = useState<string>('all');
  const [groupByAgent, setGroupByAgent] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const fetchActivity = useCallback(async (offset = 0, append = false) => {
    const types = Array.from(typeFilters);
    if (types.length === 0) {
      setActivityItems([]);
      setTotal(0);
      setHasMore(false);
      setIsLoading(false);
      return;
    }

    try {
      const agentId = agentFilter === 'all' ? undefined : agentFilter === 'system' ? undefined : agentFilter;
      const res = await api.activity.list({
        types,
        agentId,
        limit: 30,
        offset,
      });
      const newItems = res.items.map(apiItemToActivityItem);

      // For system filter, do client-side filtering since backend doesn't support it
      const filteredItems = agentFilter === 'system'
        ? newItems.filter(item => item.agentId === null)
        : newItems;

      if (append) {
        setActivityItems(prev => [...prev, ...filteredItems]);
      } else {
        setActivityItems(filteredItems);
      }
      setTotal(res.total);
      setHasMore(res.has_more);
    } catch (error) {
      console.error('Failed to fetch activity:', error);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [typeFilters, agentFilter]);

  useEffect(() => {
    setIsLoading(true);
    fetchActivity(0, false);
  }, [fetchActivity]);

  const loadMore = async () => {
    setIsLoadingMore(true);
    await fetchActivity(activityItems.length, true);
  };

  const toggleTypeFilter = (type: ActivityType) => {
    setTypeFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const toggleExpanded = (id: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const typeFilterOptions: { key: ActivityType; label: string; color: string }[] = [
    { key: 'agent_task', label: 'Tasks', color: 'bg-purple-500' },
    { key: 'message', label: 'Msgs', color: 'bg-blue-500' },
    { key: 'transaction', label: 'Txns', color: 'bg-emerald-500' },
    { key: 'tool_usage', label: 'Tools', color: 'bg-amber-500' },
    { key: 'model_usage', label: 'LLM', color: 'bg-rose-500' },
  ];

  // Group items by agent if enabled
  const groupedItems = useMemo(() => {
    if (!groupByAgent) return null;

    const groups = new Map<string | null, ActivityItem[]>();
    for (const item of activityItems) {
      const agentId = getAgentIdFromItem(item);
      if (!groups.has(agentId)) {
        groups.set(agentId, []);
      }
      groups.get(agentId)!.push(item);
    }

    return Array.from(groups.entries()).sort((a, b) => {
      if (a[0] === null) return 1;
      if (b[0] === null) return -1;
      return a[0].localeCompare(b[0]);
    });
  }, [activityItems, groupByAgent]);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  };

  const renderAgentBadge = (agentId: string | null, variant: 'from' | 'to' | 'default' = 'default') => {
    if (agentId === null) {
      return <span className="text-xs text-muted-foreground font-mono">SYS</span>;
    }
    const bgColor = variant === 'default' ? 'bg-zinc-700' : variant === 'from' ? 'bg-zinc-700' : 'bg-zinc-600';
    return (
      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full ${bgColor} text-white text-xs font-bold`}>
        {agentId.slice(0, 4)}
      </span>
    );
  };

  const renderActivityItem = (item: ActivityItem, showAgent = true) => {
    const config = typeConfig[item.type];
    const isExpanded = expandedItems.has(item.id);

    if (item.type === 'agent_task') {
      const agentTask = item.data;
      const hasDetails = agentTask.result || agentTask.submitted_at;

      return (
        <Collapsible key={item.id} open={isExpanded} onOpenChange={() => toggleExpanded(item.id)}>
          <CollapsibleTrigger asChild>
            <div className={`flex items-center gap-3 p-3 rounded-md border-l-4 ${config.border} bg-muted/30 hover:bg-muted/60 cursor-pointer transition-all duration-150 hover:shadow-sm border border-transparent hover:border-border`}>
              {showAgent && renderAgentBadge(agentTask.agent_id)}
              <Badge className={`${config.color} text-[10px] px-1.5 py-0 h-5 font-bold`}>{config.label}</Badge>
              <span className="flex-1 text-sm truncate">
                <Badge className={`${getStatusColor(agentTask.status)} text-[10px] px-1.5 py-0 h-5 mr-2`}>
                  {agentTask.status}
                </Badge>
                <span className="text-muted-foreground">"{getTaskDescription(agentTask.task_id)}"</span>
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(item.timestamp)}</span>
              {hasDetails && <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />}
            </div>
          </CollapsibleTrigger>
          {hasDetails && (
            <CollapsibleContent>
              <div className={`ml-9 p-4 text-xs space-y-3 border-l-4 ${config.border} bg-zinc-800/50 rounded-b-md border border-border/50`}>
                {agentTask.submitted_at && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground font-semibold">Submitted:</span>
                    <span>{formatDateTimeShort(agentTask.submitted_at)}</span>
                  </div>
                )}
                {agentTask.result && (
                  <div>
                    <span className="text-muted-foreground font-semibold block mb-2">Result:</span>
                    <p className="mt-1 text-foreground p-3 bg-black/30 rounded border border-border/30">{agentTask.result}</p>
                  </div>
                )}
              </div>
            </CollapsibleContent>
          )}
        </Collapsible>
      );
    }

    if (item.type === 'message') {
      const message = item.data;
      return (
        <Collapsible key={item.id} open={isExpanded} onOpenChange={() => toggleExpanded(item.id)}>
          <CollapsibleTrigger asChild>
            <div className={`flex items-center gap-3 p-3 rounded-md border-l-4 ${config.border} bg-muted/30 hover:bg-muted/60 cursor-pointer transition-all duration-150 hover:shadow-sm border border-transparent hover:border-border`}>
              {showAgent && renderAgentBadge(message.from_agent_id)}
              <Badge className={`${config.color} text-[10px] px-1.5 py-0 h-5 font-bold`}>{config.label}</Badge>
              <span className="flex-1 text-sm truncate">
                <span className="text-muted-foreground">-&gt;</span>
                <span className="mx-1">{renderAgentBadge(message.to_agent_id, 'to')}</span>
                <span className="text-muted-foreground">"{message.content.slice(0, 50)}{message.content.length > 50 ? '...' : ''}"</span>
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(item.timestamp)}</span>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className={`ml-9 p-4 text-xs space-y-3 border-l-4 ${config.border} bg-zinc-800/50 rounded-b-md border border-border/50`}>
              <p className="text-foreground p-3 bg-black/30 rounded border border-border/30">{message.content}</p>
              {message.received_at && (
                <div className="flex gap-2 text-muted-foreground">
                  <span className="font-semibold">Received:</span>
                  <span>{formatDateTimeShort(message.received_at)}</span>
                </div>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      );
    }

    if (item.type === 'transaction') {
      const transaction = item.data;
      const amount = parseFloat(transaction.amount);
      const isPositive = transaction.to_agent_id !== null;

      return (
        <div key={item.id} className={`flex items-center gap-3 p-3 rounded-md border-l-4 ${config.border} bg-muted/30 border border-transparent`}>
          {showAgent && renderAgentBadge(transaction.from_agent_id)}
          <Badge className={`${config.color} text-[10px] px-1.5 py-0 h-5 font-bold`}>{config.label}</Badge>
          <span className="flex-1 text-sm truncate">
            <span className="text-muted-foreground">-&gt;</span>
            <span className="mx-1">{renderAgentBadge(transaction.to_agent_id, 'to')}</span>
            <span className={`font-mono font-semibold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
              ${amount.toFixed(4)}
            </span>
            <span className="text-muted-foreground ml-2">({transaction.reason})</span>
          </span>
          <span className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(item.timestamp)}</span>
        </div>
      );
    }

    if (item.type === 'tool_usage') {
      const toolUsage = item.data;
      const formattedInput = formatJSON(toolUsage.input);
      const formattedOutput = formatJSON(toolUsage.output);

      return (
        <Collapsible key={item.id} open={isExpanded} onOpenChange={() => toggleExpanded(item.id)}>
          <CollapsibleTrigger asChild>
            <div className={`flex items-center gap-3 p-3 rounded-md border-l-4 ${config.border} bg-muted/30 hover:bg-muted/60 cursor-pointer transition-all duration-150 hover:shadow-sm border border-transparent hover:border-border`}>
              {showAgent && renderAgentBadge(toolUsage.agent_id)}
              <Badge className={`${config.color} text-[10px] px-1.5 py-0 h-5 font-bold`}>{config.label}</Badge>
              <span className="flex-1 text-sm truncate">
                <span className="font-medium">{toolUsage.tool_name}</span>
                <span className="text-muted-foreground ml-2">({toolUsage.input.slice(0, 30)}{toolUsage.input.length > 30 ? '...' : ''})</span>
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(item.timestamp)}</span>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className={`ml-9 p-4 text-xs space-y-3 border-l-4 ${config.border} bg-zinc-800/50 rounded-b-md border border-border/50`}>
              <div>
                <span className="text-muted-foreground font-semibold block mb-2">Input:</span>
                {formattedInput.trim() === '' || formattedInput === '()' ? (
                  <span className="text-muted-foreground/50 text-xs italic">No input parameters</span>
                ) : (
                  <pre className="mt-1 p-3 bg-black/30 rounded font-mono text-xs text-foreground overflow-x-auto border border-border/30">{formattedInput}</pre>
                )}
              </div>
              <div>
                <span className="text-muted-foreground font-semibold block mb-2">Output:</span>
                <pre className="mt-1 p-3 bg-black/30 rounded font-mono text-xs text-foreground overflow-x-auto max-h-32 overflow-y-auto border border-border/30">{formattedOutput}</pre>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      );
    }

    if (item.type === 'model_usage') {
      const modelUsage = item.data;
      const model = models.find((m) => m.id === modelUsage.model_id);
      const cost = parseFloat(modelUsage.total_cost);

      return (
        <Collapsible key={item.id} open={isExpanded} onOpenChange={() => toggleExpanded(item.id)}>
          <CollapsibleTrigger asChild>
            <div className={`flex items-center gap-3 p-3 rounded-md border-l-4 ${config.border} bg-muted/30 hover:bg-muted/60 cursor-pointer transition-all duration-150 hover:shadow-sm border border-transparent hover:border-border`}>
              {showAgent && renderAgentBadge(modelUsage.agent_id)}
              <Badge className={`${config.color} text-[10px] px-1.5 py-0 h-5 font-bold`}>{config.label}</Badge>
              <span className="flex-1 text-sm truncate">
                <span className="font-medium">{model?.name || 'model'}</span>
                <span className="text-muted-foreground ml-2">
                  {modelUsage.input_tokens}+{modelUsage.output_tokens} tokens
                </span>
                <span className="font-mono text-red-400 ml-2">-${cost.toFixed(6)}</span>
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(item.timestamp)}</span>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
            </div>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className={`ml-9 p-4 text-xs space-y-3 border-l-4 ${config.border} bg-zinc-800/50 rounded-b-md border border-border/50`}>
              <div className="flex gap-4 pb-2 border-b border-border/30">
                <span className="text-muted-foreground">Tokens: <span className="text-foreground font-medium">{modelUsage.input_tokens} in / {modelUsage.output_tokens} out</span></span>
                <span className="text-muted-foreground">Cost: <span className="text-foreground font-mono font-medium">${cost.toFixed(6)}</span></span>
              </div>
              <div>
                <span className="text-muted-foreground font-semibold block mb-2">Input:</span>
                <pre className="mt-1 p-3 bg-black/30 rounded font-mono text-xs text-foreground overflow-x-auto max-h-24 overflow-y-auto border border-border/30">{modelUsage.input}</pre>
              </div>
              <div>
                <span className="text-muted-foreground font-semibold block mb-2">Output:</span>
                <pre className="mt-1 p-3 bg-black/30 rounded font-mono text-xs text-foreground overflow-x-auto max-h-24 overflow-y-auto border border-border/30">{modelUsage.output}</pre>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      );
    }

    return null;
  };

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex flex-col flex-1 min-h-0">
        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 className="text-2xl font-bold">Activity</h2>
          <span className="text-sm text-muted-foreground">
            {activityItems.length}{total > 0 ? ` of ${total}` : ''} items
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-4 flex-shrink-0">
          {/* Type filters */}
          <div className="flex items-center gap-1">
            {typeFilterOptions.map((option) => (
              <Toggle
                key={option.key}
                pressed={typeFilters.has(option.key)}
                onPressedChange={() => toggleTypeFilter(option.key)}
                size="sm"
                className="h-7 px-2 text-xs data-[state=on]:bg-zinc-700"
              >
                <span className={`w-2 h-2 rounded-full ${typeFilters.has(option.key) ? option.color : 'bg-zinc-500'} mr-1.5`} />
                {option.label}
              </Toggle>
            ))}
          </div>

          <div className="h-6 w-px bg-border" />

          {/* Agent filter */}
          <Select value={agentFilter} onValueChange={setAgentFilter}>
            <SelectTrigger className="w-32 h-7 text-xs">
              <SelectValue placeholder="All agents" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All agents</SelectItem>
              <SelectItem value="system">System only</SelectItem>
              {agents.map((agent) => (
                <SelectItem key={agent.id} value={String(agent.id)}>
                  {getAgentName(agent.id)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Group by dropdown */}
          <Select value={groupByAgent ? 'agent' : 'time'} onValueChange={(v) => setGroupByAgent(v === 'agent')}>
            <SelectTrigger className="w-36 h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="time">
                <span className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  Group by Time
                </span>
              </SelectItem>
              <SelectItem value="agent">
                <span className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5" />
                  Group by Agent
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Activity list */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="space-y-2 pr-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : groupByAgent && groupedItems ? (
              // Grouped view
              groupedItems.map(([agentId, items]) => (
                <div key={agentId ?? 'system'} className="mb-4">
                  <div className="flex items-center gap-2 mb-2 sticky top-0 bg-background py-1 z-10">
                    {agentId !== null ? (
                      <>
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-zinc-700 text-white text-sm font-bold">
                          {agentId.slice(0, 2).toUpperCase()}
                        </span>
                        <span className="text-sm font-medium">{getAgentName(agentId)}</span>
                      </>
                    ) : (
                      <>
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-zinc-800 text-zinc-400 text-xs font-mono">
                          SYS
                        </span>
                        <span className="text-sm font-medium text-muted-foreground">System</span>
                      </>
                    )}
                    <span className="text-xs text-muted-foreground">({items.length})</span>
                  </div>
                  <div className="space-y-2 ml-2 border-l-2 border-zinc-800 pl-3">
                    {items.map((item) => renderActivityItem(item, false))}
                  </div>
                </div>
              ))
            ) : (
              // Chronological view
              activityItems.map((item) => renderActivityItem(item, true))
            )}

            {!isLoading && activityItems.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                No activity to display
              </div>
            )}

            {!isLoading && hasMore && activityItems.length > 0 && (
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
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
