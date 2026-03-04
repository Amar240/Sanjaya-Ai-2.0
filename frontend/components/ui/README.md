# Sanjaya AI — UI Component Kit

Reusable components built on the design tokens defined in `frontend/app/globals.css`.

## Components

| Component | Purpose | Variants |
|-----------|---------|----------|
| **Button** | Primary actions and secondary triggers | `primary`, `secondary`, `ghost` |
| **Card** | Elevated content panels | `elevated` (optional prop) |
| **Chip** | Tags for skills, interests, status | `default`, `success`, `warning`, `error`, `muted` |
| **SectionHeader** | Section title + optional description | `as` prop: `h2`, `h3`, `h4` |
| **ProgressStepper** | Multi-step progress (e.g. intake) | `steps` array + `currentStep` index |
| **Tabs** | Horizontal tab selection | `tabs` array + `activeId` + `onSelect` |
| **EmptyState** | Placeholder when no data | `title`, `body`, optional `action` |
| **Alert** | Error/warning banners | `error`, `warning`, `info` |

## Usage

```tsx
import { Button, Card, Chip, Tabs } from "@/components/ui";
```

## Tokens Used

All components reference CSS custom properties from `:root`:
- Colors: `--color-primary`, `--color-ink`, `--color-border`, etc.
- Spacing: `--space-1` through `--space-10`
- Radius: `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full`
- Type: `--text-xs` through `--text-3xl`
- Transitions: `--transition-fast`, `--transition-base`, `--transition-slow`
