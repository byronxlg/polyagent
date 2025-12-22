import { useState, useEffect } from 'react';
import { Link } from '@tanstack/react-router';
import { ArrowRight, Banknote, Loader2, Bot } from 'lucide-react';
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
import { api, type Transaction, type Principal } from '@/lib/api';
import type { SimulationData } from '@/hooks/useSimulationData';

interface TransactionsPageProps {
  simulationData: SimulationData;
}

export function TransactionsPage({ simulationData }: TransactionsPageProps) {
  const { transactions: initialTransactions, currentSimulation } = simulationData;
  const [transactions, setTransactions] = useState<Transaction[]>(initialTransactions);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [total, setTotal] = useState<number | null>(null);
  const [principals, setPrincipals] = useState<Record<string, Principal>>({});

  useEffect(() => {
    setTransactions(initialTransactions);
    setHasMore(initialTransactions.length >= 30);
  }, [initialTransactions]);

  useEffect(() => {
    const loadPrincipals = async () => {
      try {
        const res = await api.principals.list(1000, 0);
        const principalsMap = res.items.reduce<Record<string, Principal>>((acc, principal) => {
          acc[principal.id] = principal;
          return acc;
        }, {});
        setPrincipals(principalsMap);
      } catch (error) {
        console.error('Failed to load principals:', error);
      }
    };
    loadPrincipals();
  }, []);

  const loadMore = async () => {
    setIsLoadingMore(true);
    try {
      const res = await api.transactions.list(undefined, 30, transactions.length);
      setTransactions((prev) => [...prev, ...res.items]);
      setHasMore(res.has_more);
      setTotal(res.total);
    } catch (error) {
      console.error('Failed to load more transactions:', error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Sort transactions by timestamp descending (newest first)
  const sortedTransactions = [...transactions].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  // Calculate totals
  const totalAmount = transactions.reduce((sum, tx) => sum + parseFloat(tx.amount), 0);

  // Helper to get icon color based on principal type
  const getParticipantColor = (principalId: string | null) => {
    if (!principalId) return 'bg-red-500'; // System
    const principal = principals[principalId];
    if (!principal) return 'bg-emerald-500'; // Default to agent green
    if (principal.principal_type === 'human') return 'bg-orange-500'; // Human user
    return 'bg-emerald-500'; // AI agent
  };

  // Helper to render transaction participant
  const renderParticipant = (principalId: string | null) => {
    if (!principalId) {
      return (
        <span
          className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-500 text-white text-xs"
          title="System"
        >
          <Banknote className="h-3 w-3" />
        </span>
      );
    }

    const bgColor = getParticipantColor(principalId);
    return (
      <Link
        to="/simulations/$simulationId/principals/$id"
        params={{ simulationId: String(currentSimulation?.id), id: String(principalId) }}
        className={`inline-flex items-center justify-center w-6 h-6 rounded-full ${bgColor} text-white text-xs font-bold hover:opacity-80 transition-opacity`}
      >
        <Bot className="h-3 w-3" />
      </Link>
    );
  };

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Transactions</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {transactions.length}{total !== null ? ` of ${total}` : ''} transactions
          </span>
          <span className="text-sm font-mono text-emerald-400">
            ${totalAmount.toFixed(4)} total volume
          </span>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40">From / To</TableHead>
              <TableHead className="w-28 text-right">Amount</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead className="w-36">Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTransactions.map((tx) => (
              <TableRow key={tx.id}>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {renderParticipant(tx.from_principal_id)}
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                    {renderParticipant(tx.to_principal_id)}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono text-emerald-400">
                  ${parseFloat(tx.amount).toFixed(4)}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary" className="text-xs font-normal">
                    {tx.reason}
                  </Badge>
                  {tx.reference_id && (
                    <span className="text-xs text-muted-foreground ml-2">
                      ref: {tx.reference_id}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDateTimeShort(tx.timestamp)}
                </TableCell>
              </TableRow>
            ))}
            {transactions.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No transactions found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        {hasMore && transactions.length > 0 && (
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
