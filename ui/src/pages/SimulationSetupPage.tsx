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
import { api, type Model } from '@/lib/api'
import { useNavigate } from '@tanstack/react-router'
import { Plus, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

interface SimulationSetupPageProps {
  onUpdate: () => void
}

interface AgentConfig {
  id: string
  name: string
  modelId: string
  provider: string
  initialBalance: string
}

const randomNames = [
  'Alice',
  'Bob',
  'Carol',
  'David',
  'Eve',
  'Frank',
  'Grace',
  'Hank',
  'Ivy',
  'Jack',
  'Kate',
  'Leo',
  'Maya',
  'Noah',
  'Olivia',
  'Peter',
]

export function SimulationSetupPage({ onUpdate }: SimulationSetupPageProps) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const [models, setModels] = useState<Model[]>([])
  const [agents, setAgents] = useState<AgentConfig[]>([])

  const loadModels = useCallback(async () => {
    try {
      const res = await api.models.list(100, 0)
      setModels(res.items)
    } catch (error) {
      console.error('Failed to load models:', error)
    }
  }, [])

  useEffect(() => {
    loadModels()
  }, [loadModels])

  const providers = Array.from(new Set(models.map((m) => m.provider)))
  const providerNames = Object.fromEntries(
    models.map((m) => [m.provider, m.provider_name])
  )

  const addAgent = () => {
    const randomName =
      randomNames[Math.floor(Math.random() * randomNames.length)]
    const randomBalance = (Math.random() * 0.2 + 0.05).toFixed(2)
    const firstModel = models.length > 0 ? models[0] : null

    setAgents([
      ...agents,
      {
        id: Math.random().toString(36).substring(7),
        name: randomName,
        modelId: firstModel?.id || '',
        provider: firstModel?.provider || '',
        initialBalance: randomBalance,
      },
    ])
  }

  const removeAgent = (id: string) => {
    setAgents(agents.filter((a) => a.id !== id))
  }

  const updateAgent = (id: string, field: keyof AgentConfig, value: string) => {
    setAgents(
      agents.map((a) => {
        if (a.id === id) {
          const updated = { ...a, [field]: value }
          if (field === 'provider') {
            const firstModelForProvider = models.find(
              (m) => m.provider === value
            )
            if (firstModelForProvider) {
              updated.modelId = firstModelForProvider.id
            }
          }
          return updated
        }
        return a
      })
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error('Please enter a simulation name')
      return
    }

    if (agents.length === 0) {
      toast.error('Please add at least one agent')
      return
    }

    setIsCreating(true)
    try {
      // System principal ID (from seed data)
      const systemPrincipalId = 'a603702c-1e2f-4324-bd98-3c8e3232b477'

      // Create simulation owned by system principal
      const simulation = await api.simulations.create({
        principal_id: systemPrincipalId,
        name: name.trim(),
        description: description.trim() || undefined,
      })

      // Create each agent (backend handles Principal creation)
      for (const agent of agents) {
        await api.agents.create({
          simulation_id: simulation.id,
          model_id: agent.modelId,
          created_by_principal_id: systemPrincipalId,
          name: agent.name || undefined,
          initial_balance: agent.initialBalance,
        })
      }

      toast.success(
        `Simulation "${simulation.name}" created with ${agents.length} agent(s)`
      )
      onUpdate()
      navigate({ to: `/simulations/${simulation.id}` })
    } catch (error) {
      toast.error('Failed to create simulation')
      console.error('Failed to create simulation:', error)
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="flex-1 p-6 space-y-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Create New Simulation</h1>
          <p className="text-muted-foreground">
            Set up a new agent ecosystem simulation with initial agents
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Simulation Details</CardTitle>
              <CardDescription>
                Basic information about your simulation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="sim-name">Simulation Name</Label>
                <Input
                  id="sim-name"
                  placeholder="Default Simulation"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sim-description">Description (optional)</Label>
                <Textarea
                  id="sim-description"
                  placeholder="Describe the purpose of this simulation..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Agents</CardTitle>
              <CardDescription>
                Add agents to participate in the simulation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {agents.map((agent, index) => {
                const filteredModels = models.filter(
                  (m) => m.provider === agent.provider
                )
                return (
                  <div
                    key={agent.id}
                    className="p-4 border rounded-lg space-y-4 relative"
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="font-medium">Agent {index + 1}</h3>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeAgent(agent.id)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        <Input
                          value={agent.name}
                          onChange={(e) =>
                            updateAgent(agent.id, 'name', e.target.value)
                          }
                          placeholder="Agent name"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Initial Balance ($)</Label>
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          value={agent.initialBalance}
                          onChange={(e) =>
                            updateAgent(
                              agent.id,
                              'initialBalance',
                              e.target.value
                            )
                          }
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Provider</Label>
                        <Select
                          value={agent.provider}
                          onValueChange={(value) =>
                            updateAgent(agent.id, 'provider', value)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select provider" />
                          </SelectTrigger>
                          <SelectContent>
                            {providers.map((provider) => (
                              <SelectItem key={provider} value={provider}>
                                {providerNames[provider]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label>Model</Label>
                        <Select
                          value={agent.modelId}
                          onValueChange={(value) =>
                            updateAgent(agent.id, 'modelId', value)
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select model" />
                          </SelectTrigger>
                          <SelectContent>
                            {filteredModels.map((model) => (
                              <SelectItem key={model.id} value={model.id}>
                                {model.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                )
              })}

              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={addAgent}
                disabled={models.length === 0}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Agent
              </Button>
            </CardContent>
          </Card>

          <Button
            type="submit"
            className="w-full"
            disabled={isCreating || agents.length === 0}
          >
            {isCreating
              ? 'Creating...'
              : `Create Simulation with ${agents.length} Agent(s)`}
          </Button>
        </form>
      </div>
    </div>
  )
}
