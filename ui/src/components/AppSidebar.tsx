import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from '@tanstack/react-router'
import { toast } from 'sonner'
import {
  Home,
  List,
  UserCircle,
  Bot,
  Box,
  MessageSquare,
  ArrowRightLeft,
  Plus,
  Play,
  RefreshCw,
  Activity,
  Server,
} from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarSeparator,
} from '@/components/ui/sidebar'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronRight } from 'lucide-react'
import { NavUser } from '@/components/NavUser'
import { api } from '@/lib/api'
import type { SimulationData } from '@/hooks/useSimulationData'

interface AppSidebarProps {
  onUpdate: () => void
  simulationData: SimulationData
}

const getNavItems = (simulationId: string | null) => {
  if (!simulationId) return [];
  const baseUrl = `/simulations/${simulationId}`;
  return [
    { title: 'Home', url: baseUrl, icon: Home, path: '' },
    { title: 'Activity', url: `${baseUrl}/activity`, icon: Activity, path: '/activity' },
    { title: 'Tasks', url: `${baseUrl}/tasks`, icon: List, path: '/tasks' },
    { title: 'Agents', url: `${baseUrl}/agents`, icon: Bot, path: '/agents' },
    { title: 'Principals', url: `${baseUrl}/principals`, icon: UserCircle, path: '/principals' },
    { title: 'Models', url: `${baseUrl}/models`, icon: Box, path: '/models' },
    { title: 'Servers', url: `${baseUrl}/servers`, icon: Server, path: '/servers' },
    { title: 'Conversations', url: `${baseUrl}/messages`, icon: MessageSquare, path: '/messages' },
    { title: 'Transactions', url: `${baseUrl}/transactions`, icon: ArrowRightLeft, path: '/transactions' },
  ];
};

export function AppSidebar({ onUpdate, simulationData }: AppSidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [isRunningAgents, setIsRunningAgents] = useState(false)

  const handleRunAllAgents = async () => {
    setIsRunningAgents(true)
    try {
      await api.agents.tickAllBackground()
      toast.success('All agents triggered')
      setTimeout(() => onUpdate(), 1000)
    } catch (error) {
      toast.error('Failed to trigger agents')
      console.error('Failed to trigger agents:', error)
    } finally {
      setIsRunningAgents(false)
    }
  }

  const handleNewSimulation = () => {
    simulationData.setCurrentSimulation(null)
    navigate({ to: '/' })
    toast.info('Create a new simulation')
  }

  const { agents, models, tasks, servers, simulations, setCurrentSimulation } = simulationData

  // Get simulation ID from router params (type-safe, no regex needed)
  const params = useParams({ strict: false })
  const simulationIdFromPath = ('simulationId' in params ? params.simulationId : null) as string | null

  const navItems = getNavItems(simulationIdFromPath)

  return (
    <Sidebar>
      <SidebarHeader>
        <div className="px-2">
          <span className="text-lg font-bold">PolyAgent</span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton asChild isActive={location.pathname === item.url}>
                    <Link to={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                  {item.path === '/tasks' && tasks.length > 0 && (
                    <SidebarMenuBadge>{tasks.length}</SidebarMenuBadge>
                  )}
                  {item.path === '/agents' && agents.length > 0 && (
                    <SidebarMenuBadge>{agents.length}</SidebarMenuBadge>
                  )}
                  {item.path === '/models' && models.length > 0 && (
                    <SidebarMenuBadge>{models.length}</SidebarMenuBadge>
                  )}
                  {item.path === '/servers' && servers.length > 0 && (
                    <SidebarMenuBadge>{servers.length}</SidebarMenuBadge>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Actions</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={handleRunAllAgents}
                  disabled={isRunningAgents || agents.length === 0}
                >
                  <Play className={`h-4 w-4 ${isRunningAgents ? 'animate-pulse' : ''}`} />
                  <span>{isRunningAgents ? 'Running...' : 'Run All Agents'}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton onClick={onUpdate}>
                  <RefreshCw className="h-4 w-4" />
                  <span>Refresh Data</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <Collapsible defaultOpen className="group/collapsible">
          <SidebarGroup>
            <SidebarGroupLabel asChild>
              <CollapsibleTrigger>
                Simulations
                <ChevronRight className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
              </CollapsibleTrigger>
            </SidebarGroupLabel>
            <CollapsibleContent>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton onClick={handleNewSimulation}>
                      <Plus className="h-4 w-4" />
                      <span>New Simulation</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  {simulations.map((sim) => (
                    <SidebarMenuItem key={sim.id}>
                      <SidebarMenuButton
                        asChild
                        isActive={simulationIdFromPath === sim.id}
                      >
                        <Link
                          to="/simulations/$simulationId"
                          params={{ simulationId: String(sim.id) }}
                          onClick={() => {
                            setCurrentSimulation(sim)
                            toast.info(`Switched to ${sim.name}`)
                          }}
                        >
                          <span>{sim.name}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </CollapsibleContent>
          </SidebarGroup>
        </Collapsible>

        {simulationIdFromPath && (
          <>
            <SidebarSeparator />

            <SidebarGroup>
              <SidebarGroupLabel>Create</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link
                        to="/simulations/$simulationId"
                        params={{ simulationId: String(simulationIdFromPath) }}
                      >
                        <Plus className="h-4 w-4" />
                        <span>New Task</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>

      <SidebarFooter>
        <NavUser
          user={{
            name: 'Byron',
            email: 'byron@example.com',
          }}
        />
      </SidebarFooter>
    </Sidebar>
  )
}
