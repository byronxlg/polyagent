# Frontend Development Guide

This file provides frontend-specific guidance for the PolyAgent React UI.

For general project information, see [../CLAUDE.md](../CLAUDE.md)

## Development Commands

### Setup
```bash
cd ui
npm install
```

### Development Server
```bash
npm run dev
```
UI available at http://localhost:5173

### Build
```bash
# Production build
npm run build

# Preview production build
npm run preview
```

### Linting
```bash
# Check for issues
npm run lint

# Auto-fix issues
npm run lint -- --fix
```

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool and dev server
- **Tailwind CSS v4** - Utility-first CSS framework with @tailwindcss/vite plugin
- **Radix UI** - Accessible component primitives
- **TanStack Query** - Data fetching and caching
- **React Router** - Client-side routing
- **date-fns** - Date/time utilities with timezone support

## Project Structure

```
ui/
├── src/
│   ├── components/    # Reusable UI components
│   │   └── ui/        # shadcn/ui components (Radix-based)
│   ├── lib/           # Utilities and helpers
│   │   └── api.ts     # Backend API client
│   ├── pages/         # Route components
│   ├── App.tsx        # Root component
│   └── main.tsx       # Entry point
├── public/            # Static assets
└── vite.config.ts     # Vite configuration
```

## Component Patterns

### Use Functional Components with Hooks

```tsx
import { useState, useEffect } from 'react';

function MyComponent() {
  const [data, setData] = useState<DataType | null>(null);

  useEffect(() => {
    // Fetch data
  }, []);

  return <div>{data?.field}</div>;
}
```

### Prefer TypeScript Interfaces

```tsx
interface Agent {
  id: number;
  name: string | null;
  public_profile: string | null;
  is_running: boolean;
}

function AgentCard({ agent }: { agent: Agent }) {
  return <div>{agent.name}</div>;
}
```

## Styling with Tailwind CSS

### Dark Mode by Default

The UI is configured for dark mode. Use Tailwind's dark mode utilities:

```tsx
<div className="bg-white dark:bg-gray-900 text-black dark:text-white">
  Content
</div>
```

### Component Styling

Use Tailwind utility classes directly in components:

```tsx
<button className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg">
  Click me
</button>
```

### Custom Components

For reusable styled components, use the `ui/` directory pattern (shadcn/ui):

```tsx
// src/components/ui/button.tsx
import { cn } from "@/lib/utils";

export function Button({ className, ...props }) {
  return (
    <button
      className={cn(
        "px-4 py-2 rounded-lg font-medium",
        "bg-primary text-primary-foreground",
        "hover:bg-primary/90",
        className
      )}
      {...props}
    />
  );
}
```

## API Integration

### API Client (src/lib/api.ts)

All backend communication goes through the API client:

```typescript
// Define TypeScript interface matching backend schema
interface AgentResponse {
  id: number;
  name: string | null;
  model_id: number;
  // ... other fields
}

// Fetch data
export async function getAgents(): Promise<AgentResponse[]> {
  const response = await fetch(`${API_BASE_URL}/agents`);
  if (!response.ok) throw new Error('Failed to fetch agents');
  return response.json();
}
```

### Using TanStack Query

```tsx
import { useQuery } from '@tanstack/react-query';
import { getAgents } from '@/lib/api';

function AgentList() {
  const { data: agents, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {agents?.map(agent => (
        <div key={agent.id}>{agent.name}</div>
      ))}
    </div>
  );
}
```

## Date and Time Handling

### Use date-fns with Timezone Support

```tsx
import { format, formatDistanceToNow } from 'date-fns';
import { zonedTimeToUtc } from 'date-fns-tz';

// Parse ISO string from API (UTC)
const timestamp = new Date(agent.created_at);

// Format for display
const formatted = format(timestamp, 'PPpp'); // Dec 20, 2025, 3:45 PM

// Relative time
const relative = formatDistanceToNow(timestamp, { addSuffix: true }); // 2 hours ago
```

### Handling UTC Timestamps

All API timestamps are in UTC. Convert to local timezone for display:

```tsx
function formatTimestamp(isoString: string) {
  const date = new Date(isoString);
  return format(date, 'PPpp'); // Automatically uses local timezone
}
```

## State Management

### Local State

Use `useState` for component-local state:

```tsx
const [isOpen, setIsOpen] = useState(false);
```

### Server State

Use TanStack Query for server data:

```tsx
const { data, isLoading } = useQuery({
  queryKey: ['agents'],
  queryFn: getAgents,
});
```

### Global State (if needed)

Use React Context for app-wide state:

```tsx
const ThemeContext = createContext<Theme>('dark');

function ThemeProvider({ children }) {
  const [theme, setTheme] = useState<Theme>('dark');
  return (
    <ThemeContext.Provider value={theme}>
      {children}
    </ThemeContext.Provider>
  );
}
```

## Adding New Features

### Adding a New Page

1. Create component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation link in layout

### Adding a New Component

1. Create component file in `src/components/`
2. Use TypeScript interfaces for props
3. Follow existing styling patterns
4. Export component for reuse

### Adding a New API Endpoint

1. Update `src/lib/api.ts` with TypeScript interface
2. Add fetch function
3. Use with TanStack Query in component
4. Handle loading and error states

## Common Tasks

### Updating API Types

When backend schemas change:

1. Check `src/schemas.py` in backend
2. Update TypeScript interfaces in `src/lib/api.ts`
3. Update components using the changed types

### Adding a shadcn/ui Component

```bash
# From ui/ directory
npx shadcn@latest add button
npx shadcn@latest add dialog
npx shadcn@latest add table
```

Components will be added to `src/components/ui/`

### Debugging

- **React DevTools**: Install browser extension for component inspection
- **Network Tab**: Check API requests/responses
- **Console**: Check for errors and warnings
- **TypeScript**: Fix type errors before runtime issues occur

## Best Practices

- **Type Everything**: Use TypeScript interfaces, avoid `any`
- **Error Boundaries**: Wrap components to catch render errors
- **Accessibility**: Use Radix UI primitives for keyboard/screen reader support
- **Performance**: Use React.memo for expensive components, lazy load routes
- **Responsive Design**: Use Tailwind responsive utilities (sm:, md:, lg:)
- **Consistent Naming**: Component files PascalCase, utilities camelCase
