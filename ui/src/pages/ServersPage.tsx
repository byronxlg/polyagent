import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { Loader2, Server as ServerIcon, Wrench } from 'lucide-react';
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
import { api, type Server } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

interface ServersPageProps {
  simulationData: SimulationData;
}

export function ServersPage({ simulationData }: ServersPageProps) {
  const { servers: initialServers, agentServers, currentSimulation } = simulationData;
  const [servers, setServers] = useState<Server[]>(initialServers);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    setServers(initialServers);
    setHasMore(initialServers.length >= 30);
  }, [initialServers]);

  const loadMore = async () => {
    setIsLoadingMore(true);
    try {
      const res = await api.servers.list(30, servers.length);
      setServers((prev) => [...prev, ...res.items]);
      setHasMore(res.has_more);
      setTotal(res.total);
    } catch (error) {
      console.error('Failed to load more servers:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Count agents per server
  const serverAgentCounts = servers.reduce<Record<string, number>>((acc, server) => {
    let count = 0;
    for (const agentServerList of Object.values(agentServers)) {
      if (agentServerList.some((s) => s.id === server.id)) {
        count++;
      }
    }
    acc[server.id] = count;
    return acc;
  }, {});

  // Group servers by type
  const systemServers = servers.filter((s) => s.server_type === 'system');
  const customServers = servers.filter((s) => s.server_type === 'custom');

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ServerIcon className="h-6 w-6" />
          MCP Servers
        </h1>
        <span className="text-sm text-muted-foreground">
          {servers.length}{total !== null ? ` of ${total}` : ''} servers
        </span>
      </div>

      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="w-24">Type</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="w-20 text-center">Agents</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {systemServers.length > 0 && (
              <TableRow className="bg-muted/30">
                <TableCell colSpan={4} className="py-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    System Servers ({systemServers.length})
                  </span>
                </TableCell>
              </TableRow>
            )}
            {systemServers.map((server) => (
              <TableRow key={server.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link
                    to="/simulations/$simulationId/servers/$id"
                    params={{ simulationId: String(currentSimulation?.id), id: String(server.id) }}
                    className="font-medium hover:underline flex items-center gap-2"
                  >
                    <Wrench className="h-4 w-4 text-muted-foreground" />
                    {server.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">system</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm max-w-md truncate">
                  {server.description}
                </TableCell>
                <TableCell className="text-center">
                  {serverAgentCounts[server.id] || 0}
                </TableCell>
              </TableRow>
            ))}
            {customServers.length > 0 && (
              <TableRow className="bg-muted/30">
                <TableCell colSpan={4} className="py-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Custom Servers ({customServers.length})
                  </span>
                </TableCell>
              </TableRow>
            )}
            {customServers.map((server) => (
              <TableRow key={server.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link
                    to="/simulations/$simulationId/servers/$id"
                    params={{ simulationId: String(currentSimulation?.id), id: String(server.id) }}
                    className="font-medium hover:underline flex items-center gap-2"
                  >
                    <Wrench className="h-4 w-4 text-muted-foreground" />
                    {server.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">custom</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm max-w-md truncate">
                  {server.description}
                </TableCell>
                <TableCell className="text-center">
                  {serverAgentCounts[server.id] || 0}
                </TableCell>
              </TableRow>
            ))}
            {servers.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No servers found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {hasMore && servers.length > 0 && (
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
