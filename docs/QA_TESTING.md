# QA Testing Infrastructure

Comprehensive testing infrastructure for AgentFund, enabling automated quality assurance across all layers of the application.

## Overview

The testing stack includes:
- **Backend**: pytest with async support, fixtures, and mocking
- **Frontend Unit Tests**: Vitest with React Testing Library
- **E2E Tests**: Playwright with multi-browser support
- **CI/CD**: GitHub Actions with parallel test execution

## Quick Start

### Backend Tests

```bash
cd backend

# Run all unit tests
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test markers
pytest -m "not slow"  # Skip slow tests
pytest -m "api"       # Only API tests
pytest -m "broker"    # Only broker tests
```

### Frontend Unit Tests

```bash
cd frontend

# Run all tests
npm run test

# Run with UI
npm run test:ui

# Run once (CI mode)
npm run test:run

# Run with coverage
npm run test:coverage
```

### E2E Tests

```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run with headed browser
npm run test:e2e:headed

# Run specific browser
npm run test:e2e -- --project=chromium

# Debug mode
npm run test:e2e:debug

# UI mode
npm run test:e2e:ui
```

## Test Structure

### Backend (`/backend/tests/`)

```
tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── test_auth.py      # Authentication tests
│   ├── test_agents.py    # Agent management tests
│   └── ...
└── integration/
    └── test_api_flow.py  # Full API flow tests
```

### Frontend (`/frontend/tests/`)

```
tests/
├── setup.ts              # Test setup with MSW
├── unit/
│   ├── lib/
│   │   ├── utils.test.ts
│   │   └── api.test.ts
│   └── components/
│       ├── Button.test.tsx
│       └── AgentCard.test.tsx
└── e2e/
    ├── fixtures.ts       # Playwright fixtures & POMs
    ├── global-setup.ts
    ├── global-teardown.ts
    ├── auth.spec.ts
    ├── agents.spec.ts
    ├── dashboard.spec.ts
    └── settings.spec.ts
```

## Backend Testing

### Pytest Configuration

Key markers defined in `pytest.ini`:

| Marker | Description |
|--------|-------------|
| `unit` | Unit tests (fast, isolated) |
| `integration` | Integration tests |
| `slow` | Long-running tests |
| `api` | API endpoint tests |
| `broker` | Broker integration tests |
| `llm` | LLM/Claude tests |

### Available Fixtures

```python
# Client fixtures
client          # Sync test client
async_client    # Async test client
app             # FastAPI application

# Mock fixtures
mock_supabase   # Mocked Supabase client
mock_alpaca     # Mocked Alpaca broker
mock_claude     # Mocked Claude API

# Data fixtures
sample_user           # Basic user data
sample_user_with_broker  # User with broker connected
sample_agent          # Single agent
sample_agents         # List of agents
sample_position       # Trading position
auth_token           # Valid JWT token
auth_headers         # Authorization headers
```

### Example Test

```python
@pytest.mark.api
class TestAgentEndpoints:
    def test_create_agent(self, client, auth_headers, mock_supabase):
        # Configure mock
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MockSupabaseResponse(data=[{"id": "new-agent", "name": "Test"}])
        )

        response = client.post(
            "/api/agents",
            json={"name": "Test Agent", "strategy": "growth"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Test Agent"
```

## Frontend Testing

### Vitest Configuration

- Uses jsdom for browser environment
- React Testing Library for component testing
- MSW for API mocking
- Coverage thresholds: 70% across all metrics

### MSW Handlers

Pre-configured API mocks in `tests/setup.ts`:

```typescript
// Auth endpoints
POST /api/auth/login
POST /api/auth/register
GET  /api/auth/me

// Agent endpoints
GET  /api/agents
POST /api/agents
GET  /api/agents/:id

// Market data
GET  /api/market/stocks/:symbol

// Reports
GET  /api/reports/daily
```

### Example Component Test

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

describe('Button', () => {
  it('calls onClick when clicked', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<Button onClick={handleClick}>Click me</Button>);
    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

## E2E Testing

### Playwright Configuration

- Multi-browser: Chromium, Firefox, WebKit
- Mobile testing: Pixel 5, iPhone 12
- Tablet testing: iPad
- Screenshots on failure
- Video on retry
- HTML reports

### Page Object Models

Pre-built POMs in `tests/e2e/fixtures.ts`:

```typescript
class LoginPage {
  async goto()
  async login(email, password)
  async expectError(message)
  async expectLoginSuccess()
}

class DashboardPage {
  async goto()
  async expectLoaded()
  async getPortfolioValue()
  async getAgentCount()
}

class AgentsPage {
  async createAgent(agent)
  async pauseAgent(name)
  async resumeAgent(name)
  async deleteAgent(name)
}

class SettingsPage {
  async updateApiKey(key)
  async connectBroker()
}
```

### Example E2E Test

```typescript
import { test, expect, AgentsPage } from './fixtures';

test.describe('Agent Management', () => {
  test('should create agent successfully', async ({ authenticatedPage, testAgent }) => {
    const agentsPage = new AgentsPage(authenticatedPage);
    await agentsPage.goto();
    await agentsPage.createAgent(testAgent);

    await agentsPage.expectAgentExists(testAgent.name);
  });
});
```

## CI/CD Pipeline

### Test Jobs

| Job | Dependencies | Description |
|-----|-------------|-------------|
| `backend-lint` | - | Ruff, Black, isort checks |
| `backend-typecheck` | - | MyPy type checking |
| `backend-unit-tests` | lint | Unit tests with coverage |
| `backend-integration-tests` | unit | Integration tests |
| `frontend-lint` | - | ESLint, TypeScript |
| `frontend-unit-tests` | lint | Vitest unit tests |
| `frontend-coverage` | unit | Coverage report |
| `frontend-build` | lint | Next.js build |
| `e2e-tests` | backend, frontend-build | Playwright tests |
| `docker` | backend, frontend-build | Docker image builds |
| `security-scan` | lint | Trivy vulnerability scan |

### Artifacts

The CI pipeline produces:
- Unit test results (JUnit XML)
- Coverage reports (HTML, lcov)
- Playwright reports (HTML)
- Test videos and screenshots
- Docker images

## Writing New Tests

### Backend Unit Test

1. Create file in `tests/unit/test_<module>.py`
2. Use appropriate fixtures from conftest
3. Add markers for categorization
4. Mock external dependencies

### Frontend Unit Test

1. Create file in `tests/unit/**/*.test.ts(x)`
2. Import from `@testing-library/react`
3. Use MSW for API calls
4. Follow AAA pattern (Arrange, Act, Assert)

### E2E Test

1. Create file in `tests/e2e/<feature>.spec.ts`
2. Use or extend fixtures from `fixtures.ts`
3. Create Page Objects for reusable interactions
4. Add appropriate test tags

## Best Practices

1. **Isolation**: Each test should be independent
2. **Determinism**: Tests should produce consistent results
3. **Speed**: Keep unit tests fast (<100ms each)
4. **Clarity**: Clear test names describing behavior
5. **Coverage**: Aim for meaningful coverage, not metrics
6. **Mocking**: Mock external dependencies, not internal logic

## Debugging

### Backend

```bash
# Run with verbose output
pytest -v --tb=long

# Drop into debugger on failure
pytest --pdb

# Run specific test
pytest tests/unit/test_auth.py::TestPasswordHashing::test_password_hashing -v
```

### Frontend

```bash
# Open Vitest UI
npm run test:ui

# Run specific test file
npm run test -- tests/unit/lib/utils.test.ts
```

### E2E

```bash
# Debug mode (step through)
npm run test:e2e:debug

# Open trace viewer
npx playwright show-trace trace.zip

# Generate report
npx playwright show-report
```

## Coverage Requirements

| Metric | Threshold |
|--------|-----------|
| Statements | 70% |
| Branches | 70% |
| Functions | 70% |
| Lines | 70% |

Coverage reports are generated in:
- Backend: `backend/htmlcov/`
- Frontend: `frontend/coverage/`
