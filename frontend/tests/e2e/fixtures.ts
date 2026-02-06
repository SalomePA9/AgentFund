import { test as base, expect, Page } from '@playwright/test';

// =============================================================================
// Custom Test Fixtures
// =============================================================================

/**
 * Test user data
 */
export interface TestUser {
  email: string;
  password: string;
  name?: string;
}

/**
 * Test agent data
 */
export interface TestAgent {
  name: string;
  strategy: 'growth' | 'value' | 'momentum' | 'dividend';
  allocated_capital: number;
  risk_tolerance: 'low' | 'medium' | 'high';
}

/**
 * Extended test fixtures for AgentFund E2E tests
 */
interface AgentFundFixtures {
  testUser: TestUser;
  testAgent: TestAgent;
  authenticatedPage: Page;
}

/**
 * Test user credentials
 */
const defaultTestUser: TestUser = {
  email: `test-${Date.now()}@example.com`,
  password: 'TestPassword123!',
  name: 'Test User',
};

/**
 * Test agent configuration
 */
const defaultTestAgent: TestAgent = {
  name: 'E2E Test Agent',
  strategy: 'growth',
  allocated_capital: 10000,
  risk_tolerance: 'medium',
};

/**
 * Extended test with custom fixtures
 */
export const test = base.extend<AgentFundFixtures>({
  // Provide test user credentials
  testUser: async ({}, use) => {
    await use(defaultTestUser);
  },

  // Provide test agent configuration
  testAgent: async ({}, use) => {
    await use(defaultTestAgent);
  },

  // Provide an authenticated page
  authenticatedPage: async ({ page, testUser }, use) => {
    // Navigate to login page
    await page.goto('/login');

    // Fill in login credentials
    await page.fill('[data-testid="email-input"]', testUser.email);
    await page.fill('[data-testid="password-input"]', testUser.password);

    // Submit login form
    await page.click('[data-testid="login-button"]');

    // Wait for redirect to dashboard
    await page.waitForURL('/dashboard', { timeout: 10000 });

    // Provide the authenticated page
    await use(page);
  },
});

export { expect };

// =============================================================================
// Page Object Models
// =============================================================================

/**
 * Login Page Object
 */
export class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.page.fill('[data-testid="email-input"]', email);
    await this.page.fill('[data-testid="password-input"]', password);
    await this.page.click('[data-testid="login-button"]');
  }

  async expectError(message: string) {
    await expect(this.page.locator('[data-testid="error-message"]')).toContainText(message);
  }

  async expectLoginSuccess() {
    await this.page.waitForURL('/dashboard');
  }
}

/**
 * Register Page Object
 */
export class RegisterPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/register');
  }

  async register(email: string, password: string, confirmPassword?: string) {
    await this.page.fill('[data-testid="email-input"]', email);
    await this.page.fill('[data-testid="password-input"]', password);
    await this.page.fill('[data-testid="confirm-password-input"]', confirmPassword || password);
    await this.page.click('[data-testid="register-button"]');
  }

  async expectError(message: string) {
    await expect(this.page.locator('[data-testid="error-message"]')).toContainText(message);
  }

  async expectRegisterSuccess() {
    await this.page.waitForURL('/dashboard');
  }
}

/**
 * Dashboard Page Object
 */
export class DashboardPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/dashboard');
  }

  async expectLoaded() {
    await expect(this.page.locator('[data-testid="dashboard-header"]')).toBeVisible();
  }

  async getPortfolioValue() {
    return this.page.locator('[data-testid="portfolio-value"]').textContent();
  }

  async getDailyChange() {
    return this.page.locator('[data-testid="daily-change"]').textContent();
  }

  async getAgentCount() {
    return this.page.locator('[data-testid="agent-card"]').count();
  }

  async clickAgent(index: number) {
    await this.page.locator('[data-testid="agent-card"]').nth(index).click();
  }
}

/**
 * Agents Page Object
 */
export class AgentsPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/agents');
  }

  async expectLoaded() {
    await expect(this.page.locator('[data-testid="agents-header"]')).toBeVisible();
  }

  async createAgent(agent: TestAgent) {
    await this.page.click('[data-testid="create-agent-button"]');
    await this.page.fill('[data-testid="agent-name-input"]', agent.name);
    await this.page.selectOption('[data-testid="strategy-select"]', agent.strategy);
    await this.page.fill('[data-testid="capital-input"]', agent.allocated_capital.toString());
    await this.page.selectOption('[data-testid="risk-select"]', agent.risk_tolerance);
    await this.page.click('[data-testid="submit-agent-button"]');
  }

  async pauseAgent(name: string) {
    const agentCard = this.page.locator('[data-testid="agent-card"]', { hasText: name });
    await agentCard.locator('[data-testid="pause-button"]').click();
  }

  async resumeAgent(name: string) {
    const agentCard = this.page.locator('[data-testid="agent-card"]', { hasText: name });
    await agentCard.locator('[data-testid="resume-button"]').click();
  }

  async deleteAgent(name: string) {
    const agentCard = this.page.locator('[data-testid="agent-card"]', { hasText: name });
    await agentCard.locator('[data-testid="delete-button"]').click();
    await this.page.click('[data-testid="confirm-delete-button"]');
  }

  async expectAgentExists(name: string) {
    await expect(this.page.locator('[data-testid="agent-card"]', { hasText: name })).toBeVisible();
  }

  async expectAgentNotExists(name: string) {
    await expect(this.page.locator('[data-testid="agent-card"]', { hasText: name })).not.toBeVisible();
  }
}

/**
 * Settings Page Object
 */
export class SettingsPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/settings');
  }

  async expectLoaded() {
    await expect(this.page.locator('[data-testid="settings-header"]')).toBeVisible();
  }

  async updateApiKey(key: string) {
    await this.page.fill('[data-testid="api-key-input"]', key);
    await this.page.click('[data-testid="save-api-key-button"]');
  }

  async connectBroker() {
    await this.page.click('[data-testid="connect-broker-button"]');
  }

  async expectBrokerConnected() {
    await expect(this.page.locator('[data-testid="broker-status"]')).toHaveText(/connected/i);
  }
}
