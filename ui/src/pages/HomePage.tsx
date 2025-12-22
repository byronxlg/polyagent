import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { SimulationData } from '@/hooks/useSimulationData'
import { api } from '@/lib/api'
import { Clock, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

interface HomePageProps {
  simulationData: SimulationData
  onUpdate: () => void
}

const taskDescriptions = [
  'Write a haiku about artificial intelligence',
  'Explain quantum computing in simple terms',
  'Create a recipe for chocolate chip cookies',
  'Write a short story about a time traveler',
  'Summarize the benefits of meditation',
  'Write a product description for noise-canceling headphones',
  'Create a workout plan for beginners',
]

const MS_PER_HOUR = 3600000

const timeLimits = [
  { label: '30 minutes', hours: 0.5 },
  { label: '1 hour', hours: 1 },
  { label: '6 hours', hours: 6 },
  { label: '12 hours', hours: 12 },
  { label: '1 day', hours: 24 },
  { label: '3 days', hours: 72 },
  { label: '1 week', hours: 168 },
]

export function HomePage({ simulationData, onUpdate }: HomePageProps) {
  const { currentSimulation, agents } = simulationData

  const [taskDescription, setTaskDescription] = useState('')
  const [taskRewardCents, setTaskRewardCents] = useState('15')
  const [taskTimeLimit, setTaskTimeLimit] = useState(
    timeLimits[0].hours.toString()
  )
  const [isCreatingTask, setIsCreatingTask] = useState(false)

  const randomizeTask = () => {
    const description =
      taskDescriptions[Math.floor(Math.random() * taskDescriptions.length)]
    const cents = Math.floor(Math.random() * 15 + 1).toString()
    setTaskDescription(description)
    setTaskRewardCents(cents)
  }

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentSimulation) {
      toast.error('No simulation selected')
      return
    }
    setIsCreatingTask(true)
    try {
      const rewardDollars = (parseInt(taskRewardCents) / 100).toFixed(2)
      const deadline = new Date(
        Date.now() + parseFloat(taskTimeLimit) * MS_PER_HOUR
      )

      const newTask = await api.tasks.create({
        simulation_id: currentSimulation.id,
        created_by_principal_id: currentSimulation.principal_id,
        description: taskDescription,
        reward_dollars: rewardDollars,
        deadline: deadline.toISOString(),
      })
      toast.success(`Task #${newTask.id} created`)
      randomizeTask()
      onUpdate()
    } catch (error) {
      toast.error('Failed to create task')
      console.error('Failed to create task:', error)
    } finally {
      setIsCreatingTask(false)
    }
  }

  useEffect(() => {
    if (taskDescription === '') {
      randomizeTask()
    }
  }, [taskDescription])

  return (
    <div className="flex-1 p-6 space-y-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Create Task</h1>
          <p className="text-muted-foreground">
            Add a new task for agents to compete for
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Task Details
            </CardTitle>
            <CardDescription>
              Define the task description, reward, and deadline
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateTask} className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="task-description">Description</Label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={randomizeTask}
                  >
                    <Sparkles className="h-3 w-3 mr-1" />
                    Randomize
                  </Button>
                </div>
                <Textarea
                  id="task-description"
                  placeholder="What should agents work on?"
                  value={taskDescription}
                  onChange={(e) => setTaskDescription(e.target.value)}
                  rows={4}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label
                    htmlFor="task-reward"
                    className="flex items-center gap-1"
                  >
                    Reward (cents)
                  </Label>
                  <Input
                    id="task-reward"
                    type="number"
                    min="1"
                    value={taskRewardCents}
                    onChange={(e) => setTaskRewardCents(e.target.value)}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    = ${(parseInt(taskRewardCents || '0') / 100).toFixed(2)}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="task-time-limit">Time Limit</Label>
                  <Select
                    value={taskTimeLimit}
                    onValueChange={setTaskTimeLimit}
                  >
                    <SelectTrigger id="task-time-limit">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {timeLimits.map((limit) => (
                        <SelectItem
                          key={limit.hours}
                          value={limit.hours.toString()}
                        >
                          {limit.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Deadline:{' '}
                    {new Date(
                      Date.now() + parseFloat(taskTimeLimit) * MS_PER_HOUR
                    ).toLocaleString()}
                  </p>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isCreatingTask}
              >
                {isCreatingTask ? 'Creating...' : 'Create Task'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="bg-muted/30">
          <CardContent className="pt-6">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{agents.length}</div>
                <div className="text-xs text-muted-foreground">Agents</div>
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {simulationData.tasks.length}
                </div>
                <div className="text-xs text-muted-foreground">Tasks</div>
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {simulationData.messages.length}
                </div>
                <div className="text-xs text-muted-foreground">Messages</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
