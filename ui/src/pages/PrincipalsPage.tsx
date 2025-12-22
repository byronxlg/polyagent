import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { Loader2, User as UserIcon } from 'lucide-react';
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
import { api, type Principal } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

interface PrincipalsPageProps {
  simulationData: SimulationData;
}

export function PrincipalsPage({ simulationData }: PrincipalsPageProps) {
  const { currentSimulation } = simulationData;
  const [principals, setPrincipals] = useState<Principal[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    const loadPrincipals = async () => {
      try {
        const res = await api.principals.list(30, 0);
        const sortedPrincipals = [...res.items].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setPrincipals(sortedPrincipals);
        setHasMore(res.has_more);
        setTotal(res.total);
      } catch (error) {
        console.error('Failed to load principals:', error);
      }
    };
    loadPrincipals();
  }, []);

  const loadMore = async () => {
    setIsLoadingMore(true);
    try {
      const res = await api.principals.list(30, principals.length);
      setPrincipals((prev) => {
        const combined = [...prev, ...res.items];
        return combined.sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
      });
      setHasMore(res.has_more);
      setTotal(res.total);
    } catch (error) {
      console.error('Failed to load more principals:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

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
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Principals</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {principals.length}{total !== null ? ` of ${total}` : ''} principals
          </span>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead className="w-24">Type</TableHead>
              <TableHead>Email</TableHead>
              <TableHead className="w-36">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {principals.map((principal) => (
              <TableRow key={principal.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link
                    to="/simulations/$simulationId/principals/$id"
                    params={{ simulationId: String(currentSimulation?.id), id: String(principal.id) }}
                    className="hover:underline flex items-center gap-2"
                  >
                    <UserIcon className="h-4 w-4" />
                    {principal.username}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge className={`${getPrincipalTypeBadge(principal.principal_type)} text-xs`}>
                    {principal.principal_type}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {principal.email || '-'}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDateTimeShort(principal.created_at)}
                </TableCell>
              </TableRow>
            ))}
            {principals.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No principals found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {hasMore && principals.length > 0 && (
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
