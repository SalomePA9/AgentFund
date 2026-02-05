# AgentFund UI/UX Design Guidelines

## Design Benchmark

**Reference Template:** [Superior by Dream Studio](https://superior-template.framer.website/)

The Superior Framer template serves as the UI/UX benchmark for AgentFund. It's a premium SaaS template featuring:
- 20+ pages with consistent design language
- Dark mode-first aesthetic
- Modern, clean typography
- Smooth micro-interactions
- Fully responsive layouts

All UI development should reference this template for visual direction, spacing, and interaction patterns.

---

## Design Principles

### 1. Dark Mode First
- Primary interface uses dark theme
- Reduces eye strain for users monitoring portfolios
- Creates premium, professional aesthetic
- Light mode as secondary option

### 2. Data Clarity
- Financial data must be instantly readable
- Use color strategically for gains (green) and losses (red)
- Clear visual hierarchy for numbers and metrics
- Ample whitespace around data points

### 3. Trust & Professionalism
- Clean, minimal interface inspires confidence
- Avoid cluttered layouts
- Consistent component styling
- Smooth, purposeful animations

### 4. Accessibility
- WCAG 2.1 AA compliance minimum
- Sufficient color contrast ratios
- Keyboard navigation support
- Screen reader compatibility

---

## Color System

### Dark Theme (Primary)

```css
:root {
  /* Backgrounds */
  --bg-primary: #0A0A0B;        /* Main background */
  --bg-secondary: #111113;      /* Card backgrounds */
  --bg-tertiary: #18181B;       /* Elevated surfaces */
  --bg-hover: #1F1F23;          /* Hover states */

  /* Borders */
  --border-primary: #27272A;    /* Default borders */
  --border-secondary: #3F3F46;  /* Emphasized borders */

  /* Text */
  --text-primary: #FAFAFA;      /* Primary text */
  --text-secondary: #A1A1AA;    /* Secondary text */
  --text-tertiary: #71717A;     /* Muted text */

  /* Accent - Electric Blue */
  --accent-primary: #3B82F6;    /* Primary actions */
  --accent-hover: #2563EB;      /* Hover state */
  --accent-muted: #1D4ED8;      /* Pressed state */
  --accent-subtle: rgba(59, 130, 246, 0.1); /* Backgrounds */

  /* Semantic Colors */
  --success: #22C55E;           /* Positive/gains */
  --success-subtle: rgba(34, 197, 94, 0.1);
  --error: #EF4444;             /* Negative/losses */
  --error-subtle: rgba(239, 68, 68, 0.1);
  --warning: #F59E0B;           /* Warnings */
  --warning-subtle: rgba(245, 158, 11, 0.1);

  /* Gradients */
  --gradient-primary: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%);
  --gradient-card: linear-gradient(180deg, #18181B 0%, #111113 100%);
  --gradient-glow: radial-gradient(ellipse at center, rgba(59, 130, 246, 0.15) 0%, transparent 70%);
}
```

### Light Theme (Secondary)

```css
:root.light {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F4F4F5;
  --bg-tertiary: #E4E4E7;
  --bg-hover: #D4D4D8;

  --border-primary: #E4E4E7;
  --border-secondary: #D4D4D8;

  --text-primary: #09090B;
  --text-secondary: #52525B;
  --text-tertiary: #A1A1AA;

  /* Accent colors remain the same */
}
```

### Color Usage Guidelines

| Element | Color Variable | Notes |
|---------|---------------|-------|
| Page background | `--bg-primary` | Base layer |
| Cards | `--bg-secondary` | Slightly elevated |
| Modals | `--bg-tertiary` | Most elevated |
| Primary buttons | `--accent-primary` | Call-to-action |
| Positive numbers | `--success` | Gains, profits |
| Negative numbers | `--error` | Losses, alerts |
| Inactive text | `--text-tertiary` | Labels, hints |

---

## Typography

### Font Stack

```css
:root {
  /* Primary: Inter for UI */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Monospace: For numbers and code */
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
}
```

### Type Scale

```css
/* Headings */
.text-display {
  font-size: 3.5rem;      /* 56px - Hero sections */
  line-height: 1.1;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.text-h1 {
  font-size: 2.5rem;      /* 40px - Page titles */
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.text-h2 {
  font-size: 1.875rem;    /* 30px - Section headers */
  line-height: 1.3;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.text-h3 {
  font-size: 1.5rem;      /* 24px - Card titles */
  line-height: 1.4;
  font-weight: 600;
}

.text-h4 {
  font-size: 1.25rem;     /* 20px - Subsections */
  line-height: 1.5;
  font-weight: 600;
}

/* Body */
.text-body-lg {
  font-size: 1.125rem;    /* 18px - Lead paragraphs */
  line-height: 1.7;
  font-weight: 400;
}

.text-body {
  font-size: 1rem;        /* 16px - Default body */
  line-height: 1.6;
  font-weight: 400;
}

.text-body-sm {
  font-size: 0.875rem;    /* 14px - Secondary text */
  line-height: 1.5;
  font-weight: 400;
}

/* Small/Labels */
.text-caption {
  font-size: 0.75rem;     /* 12px - Labels, captions */
  line-height: 1.4;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

/* Numbers (monospace) */
.text-number-lg {
  font-family: var(--font-mono);
  font-size: 2rem;        /* 32px - Large metrics */
  font-weight: 600;
  font-feature-settings: 'tnum';
}

.text-number {
  font-family: var(--font-mono);
  font-size: 1rem;        /* 16px - Table numbers */
  font-weight: 500;
  font-feature-settings: 'tnum';
}
```

---

## Spacing System

Use an 8px base grid system:

```css
:root {
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-20: 5rem;     /* 80px */
  --space-24: 6rem;     /* 96px */
}
```

### Spacing Guidelines

| Context | Spacing | Variable |
|---------|---------|----------|
| Component internal padding | 16-24px | `--space-4` to `--space-6` |
| Between related elements | 8-16px | `--space-2` to `--space-4` |
| Between sections | 48-80px | `--space-12` to `--space-20` |
| Card padding | 24px | `--space-6` |
| Button padding | 12px 24px | `--space-3` `--space-6` |
| Input padding | 12px 16px | `--space-3` `--space-4` |
| Page margins (desktop) | 64-96px | `--space-16` to `--space-24` |
| Page margins (mobile) | 16-24px | `--space-4` to `--space-6` |

---

## Component Specifications

### Buttons

```css
/* Base button styles */
.btn {
  font-size: 0.875rem;
  font-weight: 500;
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  transition: all 150ms ease;
  cursor: pointer;
}

/* Primary - filled */
.btn-primary {
  background: var(--accent-primary);
  color: white;
  border: none;
}
.btn-primary:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

/* Secondary - outlined */
.btn-secondary {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-secondary);
}
.btn-secondary:hover {
  background: var(--bg-hover);
  border-color: var(--text-tertiary);
}

/* Ghost - text only */
.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: none;
}
.btn-ghost:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* Destructive */
.btn-destructive {
  background: var(--error);
  color: white;
  border: none;
}

/* Sizes */
.btn-sm { padding: 0.5rem 1rem; font-size: 0.75rem; }
.btn-lg { padding: 1rem 2rem; font-size: 1rem; }
```

### Cards

```css
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: 1rem;
  padding: 1.5rem;
  transition: all 200ms ease;
}

.card:hover {
  border-color: var(--border-secondary);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

/* Card with glow effect */
.card-glow {
  position: relative;
}
.card-glow::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: var(--gradient-primary);
  opacity: 0;
  z-index: -1;
  transition: opacity 200ms ease;
}
.card-glow:hover::before {
  opacity: 0.5;
}

/* Stat card */
.card-stat {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.card-stat .label {
  color: var(--text-tertiary);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.card-stat .value {
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 600;
}
```

### Inputs

```css
.input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: 0.5rem;
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: all 150ms ease;
}

.input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px var(--accent-subtle);
}

.input::placeholder {
  color: var(--text-tertiary);
}

/* Input with label */
.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.input-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}
```

### Tables

```css
.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-primary);
}

.table td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-primary);
  font-size: 0.875rem;
}

.table tr:hover td {
  background: var(--bg-hover);
}

/* Numeric columns */
.table .col-number {
  font-family: var(--font-mono);
  text-align: right;
}

/* Positive/negative values */
.table .positive { color: var(--success); }
.table .negative { color: var(--error); }
```

### Navigation

```css
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 2rem;
  background: rgba(10, 10, 11, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-primary);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-links {
  display: flex;
  gap: 2rem;
}

.nav-link {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  transition: color 150ms ease;
}

.nav-link:hover,
.nav-link.active {
  color: var(--text-primary);
}
```

### Badges/Tags

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 9999px;
}

.badge-success {
  background: var(--success-subtle);
  color: var(--success);
}

.badge-error {
  background: var(--error-subtle);
  color: var(--error);
}

.badge-warning {
  background: var(--warning-subtle);
  color: var(--warning);
}

.badge-neutral {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
```

---

## Animation Guidelines

### Timing Functions

```css
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

### Duration Standards

| Animation Type | Duration |
|---------------|----------|
| Micro-interactions (hover, focus) | 150ms |
| Component transitions | 200ms |
| Page transitions | 300ms |
| Modal open/close | 250ms |
| Loading spinners | 1000ms loop |

### Motion Principles

1. **Purposeful**: Every animation should have meaning
2. **Subtle**: Avoid flashy or distracting animations
3. **Responsive**: Interactions should feel immediate
4. **Consistent**: Same interactions = same animations

### Common Animations

```css
/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Slide up */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Scale in */
@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Skeleton loading */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 0%,
    var(--bg-tertiary) 50%,
    var(--bg-secondary) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

---

## Responsive Breakpoints

```css
/* Mobile first approach */
:root {
  --breakpoint-sm: 640px;   /* Small tablets */
  --breakpoint-md: 768px;   /* Tablets */
  --breakpoint-lg: 1024px;  /* Laptops */
  --breakpoint-xl: 1280px;  /* Desktops */
  --breakpoint-2xl: 1536px; /* Large screens */
}

/* Tailwind-style media queries */
@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
@media (min-width: 1536px) { /* 2xl */ }
```

### Responsive Patterns

| Element | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Navigation | Hamburger menu | Condensed | Full |
| Grid columns | 1 | 2 | 3-4 |
| Card layout | Stacked | Grid | Grid |
| Font sizes | -10% | Base | Base |
| Spacing | -20% | Base | Base |

---

## Chart Styling

For financial charts using Recharts or Lightweight Charts:

```javascript
const chartTheme = {
  // Colors
  backgroundColor: '#111113',
  gridColor: '#27272A',
  textColor: '#A1A1AA',

  // Line colors
  primaryLine: '#3B82F6',
  secondaryLine: '#8B5CF6',
  positiveArea: 'rgba(34, 197, 94, 0.1)',
  negativeArea: 'rgba(239, 68, 68, 0.1)',

  // Tooltip
  tooltipBackground: '#18181B',
  tooltipBorder: '#27272A',
  tooltipText: '#FAFAFA',

  // Axes
  axisColor: '#27272A',
  axisLabelColor: '#71717A',

  // Crosshair
  crosshairColor: '#3B82F6',
};

// Recharts example config
const chartConfig = {
  style: {
    fontFamily: 'Inter, sans-serif',
  },
  grid: {
    stroke: chartTheme.gridColor,
    strokeDasharray: '3 3',
  },
  xAxis: {
    stroke: chartTheme.axisColor,
    tick: { fill: chartTheme.axisLabelColor, fontSize: 12 },
  },
  yAxis: {
    stroke: chartTheme.axisColor,
    tick: { fill: chartTheme.axisLabelColor, fontSize: 12 },
  },
  tooltip: {
    contentStyle: {
      backgroundColor: chartTheme.tooltipBackground,
      border: `1px solid ${chartTheme.tooltipBorder}`,
      borderRadius: '8px',
      color: chartTheme.tooltipText,
    },
  },
};
```

---

## Page Layouts

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Nav: Logo | Dashboard | Agents | Settings | Profile           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ Total Value │ │ Day Change  │ │ Agents      │ │ Positions │ │
│  │ $125,432.00 │ │ +$1,234.00  │ │ 4 Active    │ │ 12 Open   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                                                             ││
│  │                    Performance Chart                        ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Agent Cards                                                    │
│  ┌─────────────────────┐ ┌─────────────────────┐               │
│  │ Agent Name          │ │ Agent Name          │               │
│  │ Strategy • Status   │ │ Strategy • Status   │               │
│  │ $50,000 • +5.2%     │ │ $75,000 • +3.8%     │               │
│  │ "Today's summary..."│ │ "Today's summary..."│               │
│  └─────────────────────┘ └─────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Detail Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard              Agent Name            Actions │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────┐ ┌───────────────────────────┐│
│  │         Performance           │ │      Quick Stats          ││
│  │                               │ │  Total: $52,430           ││
│  │    [Line Chart]               │ │  Return: +4.86%           ││
│  │                               │ │  Sharpe: 1.42             ││
│  │                               │ │  Win Rate: 68%            ││
│  └───────────────────────────────┘ └───────────────────────────┘│
│                                                                 │
│  ┌──────────────────────────────────────────────────────────────│
│  │  Tabs: Positions | Activity | Reports | Chat | Settings     │
│  ├──────────────────────────────────────────────────────────────│
│  │                                                              │
│  │  [Tab Content Area]                                          │
│  │                                                              │
│  └──────────────────────────────────────────────────────────────│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tailwind CSS Configuration

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: '#0A0A0B',
          secondary: '#111113',
          tertiary: '#18181B',
        },
        border: {
          DEFAULT: '#27272A',
          secondary: '#3F3F46',
        },
        accent: {
          DEFAULT: '#3B82F6',
          hover: '#2563EB',
          muted: '#1D4ED8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 300ms ease-out',
        'scale-in': 'scaleIn 200ms ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
};
```

---

## Component Library Recommendations

For faster development matching the Superior template aesthetic:

1. **Base Components**: [shadcn/ui](https://ui.shadcn.com/) - Unstyled, customizable
2. **Charts**: [Recharts](https://recharts.org/) or [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
3. **Icons**: [Lucide Icons](https://lucide.dev/) - Clean, consistent
4. **Animations**: [Framer Motion](https://www.framer.com/motion/) - Smooth, declarative

---

## Quality Checklist

Before shipping any UI:

- [ ] Matches Superior template visual language
- [ ] Dark mode renders correctly
- [ ] All interactive elements have hover/focus states
- [ ] Animations are smooth (60fps)
- [ ] Numbers use monospace font
- [ ] Positive/negative values color-coded
- [ ] Responsive on mobile, tablet, desktop
- [ ] Loading states for async content
- [ ] Error states styled consistently
- [ ] Accessibility: keyboard nav, contrast ratios

---

*Reference: [Superior Template](https://superior-template.framer.website/)*
*Last Updated: February 2026*
