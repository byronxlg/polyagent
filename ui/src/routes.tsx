/* eslint-disable react-refresh/only-export-components -- route file exports router config + internal components */
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  Link,
} from '@tanstack/react-router';
import { useState } from 'react';
import { toast } from 'sonner';
import { AlertCircle } from 'lucide-react';
import { AppSidebar } from '@/components/AppSidebar';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ActivityFeed } from '@/components/ActivityFeed';
import { DetailView } from '@/components/DetailView';
import { HomePage } from '@/pages/HomePage';
import { SimulationSetupPage } from '@/pages/SimulationSetupPage';
import { TasksPage } from '@/pages/TasksPage';
import { AgentsPage } from '@/pages/AgentsPage';
import { ModelsPage } from '@/pages/ModelsPage';
import { MessagesPage } from '@/pages/MessagesPage';
import { TransactionsPage } from '@/pages/TransactionsPage';
import { PrincipalsPage } from '@/pages/PrincipalsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { Toaster } from '@/components/ui/sonner';
import { useSimulationData, type SimulationData } from '@/hooks/useSimulationData';
import { api } from '@/lib/api';

interface RouterContext {
  simulationData: SimulationData;
  handleAcceptSubmission: (agentTaskId: string) => Promise<void>;
  handleDenySubmission: (agentTaskId: string) => Promise<void>;
  handleRunAgent: (agentId: string) => Promise<void>;
  processingSubmission: string | null;
  runningAgentId: string | null;
  handleUpdate: () => void;
}

function RootLayout() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [processingSubmission, setProcessingSubmission] = useState<string | null>(null);
  const [runningAgentId, setRunningAgentId] = useState<string | null>(null);

  const handleUpdate = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const simulationData = useSimulationData(refreshTrigger);

  const handleAcceptSubmission = async (agentTaskId: string) => {
    setProcessingSubmission(agentTaskId);
    try {
      await api.agentTasks.accept(agentTaskId);
      toast.success('Submission accepted');
      handleUpdate();
    } catch (error) {
      toast.error('Failed to accept submission');
      console.error('Failed to accept submission:', error);
    } finally {
      setProcessingSubmission(null);
    }
  };

  const handleDenySubmission = async (agentTaskId: string) => {
    setProcessingSubmission(agentTaskId);
    try {
      await api.agentTasks.deny(agentTaskId);
      toast.success('Submission denied');
      handleUpdate();
    } catch (error) {
      toast.error('Failed to deny submission');
      console.error('Failed to deny submission:', error);
    } finally {
      setProcessingSubmission(null);
    }
  };

  const handleRunAgent = async (agentId: string) => {
    setRunningAgentId(agentId);
    try {
      await api.agents.tick(agentId);
      toast.success(`Agent executed`);
      handleUpdate();
    } catch (error) {
      toast.error(`Failed to run agent`);
      console.error('Failed to run agent:', error);
    } finally {
      setRunningAgentId(null);
    }
  };

  return (
    <routerContext.Provider
      value={{
        simulationData,
        handleAcceptSubmission,
        handleDenySubmission,
        handleRunAgent,
        processingSubmission,
        runningAgentId,
        handleUpdate,
      }}
    >
      <SidebarProvider>
        <AppSidebar onUpdate={handleUpdate} simulationData={simulationData} />
        <SidebarInset>
          <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger className="-ml-1" />
          </header>
          <div className="flex-1 overflow-auto">
            <Outlet />
          </div>
        </SidebarInset>
        <Toaster position="bottom-right" />
      </SidebarProvider>
    </routerContext.Provider>
  );
}

// Create context for sharing data between routes
import { createContext, useContext } from 'react';

const routerContext = createContext<RouterContext | null>(null);

function useRouterContext() {
  const context = useContext(routerContext);
  if (!context) {
    throw new Error('useRouterContext must be used within RootLayout');
  }
  return context;
}

function IndexComponent() {
  const { handleUpdate } = useRouterContext();
  return <SimulationSetupPage onUpdate={handleUpdate} />;
}

function SimulationHomeComponent() {
  const { simulationData, handleUpdate } = useRouterContext();
  return <HomePage simulationData={simulationData} onUpdate={handleUpdate} />;
}

function ActivityComponent() {
  const { simulationData } = useRouterContext();
  return <ActivityFeed simulationData={simulationData} />;
}

function AgentComponent() {
  const { id } = simAgentRoute.useParams();
  const context = useRouterContext();
  return (
    <DetailView
      selected={{ type: 'agent', id }}
      simulationData={context.simulationData}
      onAcceptSubmission={context.handleAcceptSubmission}
      onDenySubmission={context.handleDenySubmission}
      onRunAgent={context.handleRunAgent}
      processingSubmission={context.processingSubmission}
      runningAgentId={context.runningAgentId}
    />
  );
}

function TaskComponent() {
  const { id } = simTaskRoute.useParams();
  const context = useRouterContext();
  return (
    <DetailView
      selected={{ type: 'task', id }}
      simulationData={context.simulationData}
      onAcceptSubmission={context.handleAcceptSubmission}
      onDenySubmission={context.handleDenySubmission}
      onRunAgent={context.handleRunAgent}
      processingSubmission={context.processingSubmission}
      runningAgentId={context.runningAgentId}
    />
  );
}

function ModelComponent() {
  const { id } = simModelRoute.useParams();
  const context = useRouterContext();
  return (
    <DetailView
      selected={{ type: 'model', id }}
      simulationData={context.simulationData}
      onAcceptSubmission={context.handleAcceptSubmission}
      onDenySubmission={context.handleDenySubmission}
      onRunAgent={context.handleRunAgent}
      processingSubmission={context.processingSubmission}
      runningAgentId={context.runningAgentId}
    />
  );
}

function TasksListComponent() {
  const { simulationData } = useRouterContext();
  return <TasksPage simulationData={simulationData} />;
}

function AgentsListComponent() {
  const { simulationData } = useRouterContext();
  return <AgentsPage simulationData={simulationData} />;
}

function ModelsListComponent() {
  const { simulationData } = useRouterContext();
  return <ModelsPage simulationData={simulationData} />;
}

function MessagesListComponent() {
  const { simulationData } = useRouterContext();
  return <MessagesPage simulationData={simulationData} />;
}

function TransactionsListComponent() {
  const { simulationData } = useRouterContext();
  return <TransactionsPage simulationData={simulationData} />;
}

function PrincipalsListComponent() {
  const { simulationData } = useRouterContext();
  return <PrincipalsPage simulationData={simulationData} />;
}

function PrincipalComponent() {
  const { id } = simPrincipalRoute.useParams();
  const context = useRouterContext();
  return (
    <DetailView
      selected={{ type: 'principal', id }}
      simulationData={context.simulationData}
      onAcceptSubmission={context.handleAcceptSubmission}
      onDenySubmission={context.handleDenySubmission}
      onRunAgent={context.handleRunAgent}
      processingSubmission={context.processingSubmission}
      runningAgentId={context.runningAgentId}
    />
  );
}

function SimulationLayout() {
  const { simulationId } = simulationRoute.useParams();
  const { simulationData } = useRouterContext();

  const simulation = simulationData.simulations.find(
    s => s.id === simulationId
  );

  if (!simulation) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              <CardTitle>Simulation Not Found</CardTitle>
            </div>
            <CardDescription>
              The simulation you're looking for doesn't exist
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Simulation #{simulationId} could not be found.
            </p>
            <Link to="/">
              <Button className="w-full">
                Return to Home
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <Outlet />;
}

// Route definitions
const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: IndexComponent,
});

// Simulation scoped routes
const simulationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/simulations/$simulationId',
  component: SimulationLayout,
});

const simIndexRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: '/',
  component: SimulationHomeComponent,
});

const simActivityRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'activity',
  component: ActivityComponent,
});

const simTasksListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'tasks',
  component: TasksListComponent,
});

const simTaskRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'tasks/$id',
  component: TaskComponent,
});

const simAgentsListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'agents',
  component: AgentsListComponent,
});

const simAgentRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'agents/$id',
  component: AgentComponent,
});

const simModelsListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'models',
  component: ModelsListComponent,
});

const simModelRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'models/$id',
  component: ModelComponent,
});

const simMessagesListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'messages',
  component: MessagesListComponent,
});

const simTransactionsListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'transactions',
  component: TransactionsListComponent,
});

const simPrincipalsListRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'principals',
  component: PrincipalsListComponent,
});

const simPrincipalRoute = createRoute({
  getParentRoute: () => simulationRoute,
  path: 'principals/$id',
  component: PrincipalComponent,
});

const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  component: NotFoundPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  simulationRoute.addChildren([
    simIndexRoute,
    simActivityRoute,
    simTasksListRoute,
    simTaskRoute,
    simAgentsListRoute,
    simAgentRoute,
    simModelsListRoute,
    simModelRoute,
    simMessagesListRoute,
    simTransactionsListRoute,
    simPrincipalsListRoute,
    simPrincipalRoute,
  ]),
  notFoundRoute,
]);

export const router = createRouter({ routeTree });

// Type declaration for router
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
