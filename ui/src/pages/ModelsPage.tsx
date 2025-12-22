import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
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
import { api, type Model } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

interface ModelsPageProps {
  simulationData: SimulationData;
}

export function ModelsPage({ simulationData }: ModelsPageProps) {
  const { models: initialModels, agents, currentSimulation } = simulationData;
  const [models, setModels] = useState<Model[]>(initialModels);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    setModels(initialModels);
    setHasMore(initialModels.length >= 30);
  }, [initialModels]);

  const loadMore = async () => {
    setIsLoadingMore(true);
    try {
      const res = await api.models.list(30, models.length);
      setModels((prev) => [...prev, ...res.items]);
      setHasMore(res.has_more);
      setTotal(res.total);
    } catch (error) {
      console.error('Failed to load more models:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Count agents per model
  const modelAgentCounts = models.reduce<Record<string, number>>((acc, model) => {
    acc[model.id] = agents.filter((a) => a.model_id === model.id).length;
    return acc;
  }, {});

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Models</h1>
        <span className="text-sm text-muted-foreground">
          {models.length}{total !== null ? ` of ${total}` : ''} models
        </span>
      </div>

      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="w-24">Provider</TableHead>
              <TableHead className="w-36 text-right">Input Cost</TableHead>
              <TableHead className="w-36 text-right">Output Cost</TableHead>
              <TableHead className="w-20 text-center">Agents</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((model) => (
              <TableRow key={model.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link
                    to="/simulations/$simulationId/models/$id"
                    params={{ simulationId: String(currentSimulation?.id), id: String(model.id) }}
                    className="font-medium hover:underline"
                  >
                    {model.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Badge variant="outline">{model.provider_name}</Badge>
                    {model.is_reasoning && <Badge variant="secondary">Reasoning</Badge>}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  ${parseFloat(model.input_cost_per_million).toFixed(2)}/M
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  ${parseFloat(model.output_cost_per_million).toFixed(2)}/M
                </TableCell>
                <TableCell className="text-center">
                  {modelAgentCounts[model.id] || 0}
                </TableCell>
              </TableRow>
            ))}
            {models.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No models found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {hasMore && models.length > 0 && (
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
