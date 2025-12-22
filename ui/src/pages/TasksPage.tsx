import { Link } from '@tanstack/react-router';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { TaskList } from '@/components/TaskList';
import type { SimulationData } from '@/hooks/useSimulationData';

interface TasksPageProps {
  simulationData: SimulationData;
}

export function TasksPage({ simulationData }: TasksPageProps) {
  const { tasks, currentSimulation } = simulationData;

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {tasks.length} tasks
          </span>
          <Link
            to="/simulations/$simulationId"
            params={{ simulationId: String(currentSimulation?.id) }}
          >
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              New Task
            </Button>
          </Link>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <TaskList
          initialTasks={tasks}
          simulationData={simulationData}
          variant="table"
          showLoadMore={true}
        />
      </ScrollArea>
    </div>
  );
}
