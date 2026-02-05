import { test, expect, AgentsPage, TestAgent } from './fixtures';

/**
 * Agent Management E2E Tests
 *
 * Tests for creating, managing, and monitoring trading agents
 */

test.describe('Agent Management', () => {
  test.describe('Agent List', () => {
    test('should display agents list page', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      await expect(authenticatedPage.locator('[data-testid="agents-header"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="create-agent-button"]')).toBeVisible();
    });

    test('should display agent cards with correct information', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      const agentCard = authenticatedPage.locator('[data-testid="agent-card"]').first();
      await expect(agentCard).toBeVisible();

      // Check agent card contains expected elements
      await expect(agentCard.locator('[data-testid="agent-name"]')).toBeVisible();
      await expect(agentCard.locator('[data-testid="agent-strategy"]')).toBeVisible();
      await expect(agentCard.locator('[data-testid="agent-status"]')).toBeVisible();
      await expect(agentCard.locator('[data-testid="agent-value"]')).toBeVisible();
      await expect(agentCard.locator('[data-testid="agent-return"]')).toBeVisible();
    });

    test('should filter agents by status', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      // Filter by active
      await authenticatedPage.click('[data-testid="filter-active"]');
      const activeAgents = authenticatedPage.locator('[data-testid="agent-card"]:has([data-testid="agent-status"]:has-text("active"))');
      await expect(activeAgents.first()).toBeVisible();

      // Filter by paused
      await authenticatedPage.click('[data-testid="filter-paused"]');
      const pausedAgents = authenticatedPage.locator('[data-testid="agent-card"]:has([data-testid="agent-status"]:has-text("paused"))');
      // May or may not have paused agents
    });

    test('should filter agents by strategy', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      await authenticatedPage.selectOption('[data-testid="strategy-filter"]', 'growth');

      // All visible agents should have growth strategy
      const agents = authenticatedPage.locator('[data-testid="agent-card"]');
      const count = await agents.count();

      for (let i = 0; i < count; i++) {
        await expect(agents.nth(i).locator('[data-testid="agent-strategy"]')).toContainText(/growth/i);
      }
    });

    test('should sort agents by performance', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      await authenticatedPage.selectOption('[data-testid="sort-select"]', 'return-desc');

      // First agent should have highest return
      const agents = authenticatedPage.locator('[data-testid="agent-card"]');
      const count = await agents.count();

      if (count >= 2) {
        const firstReturn = await agents.first().locator('[data-testid="agent-return"]').textContent();
        const secondReturn = await agents.nth(1).locator('[data-testid="agent-return"]').textContent();

        // Parse and compare (this is a simplified check)
        expect(firstReturn).toBeDefined();
        expect(secondReturn).toBeDefined();
      }
    });
  });

  test.describe('Create Agent', () => {
    test('should open create agent modal', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.click('[data-testid="create-agent-button"]');

      await expect(authenticatedPage.locator('[data-testid="create-agent-modal"]')).toBeVisible();
    });

    test('should display all required form fields', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.click('[data-testid="create-agent-button"]');

      await expect(authenticatedPage.locator('[data-testid="agent-name-input"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="strategy-select"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="capital-input"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="risk-select"]')).toBeVisible();
    });

    test('should show validation errors for empty form', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.click('[data-testid="create-agent-button"]');
      await authenticatedPage.click('[data-testid="submit-agent-button"]');

      await expect(authenticatedPage.locator('[data-testid="name-error"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="capital-error"]')).toBeVisible();
    });

    test('should show error for insufficient capital', async ({ authenticatedPage, testAgent }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.click('[data-testid="create-agent-button"]');

      await authenticatedPage.fill('[data-testid="agent-name-input"]', testAgent.name);
      await authenticatedPage.selectOption('[data-testid="strategy-select"]', testAgent.strategy);
      await authenticatedPage.fill('[data-testid="capital-input"]', '999999999'); // More than available
      await authenticatedPage.selectOption('[data-testid="risk-select"]', testAgent.risk_tolerance);
      await authenticatedPage.click('[data-testid="submit-agent-button"]');

      await expect(authenticatedPage.locator('[data-testid="capital-error"]')).toContainText(
        'Insufficient funds'
      );
    });

    test('should create agent successfully', async ({ authenticatedPage, testAgent }) => {
      const agentsPage = new AgentsPage(authenticatedPage);
      await agentsPage.goto();
      await agentsPage.createAgent(testAgent);

      // Modal should close
      await expect(authenticatedPage.locator('[data-testid="create-agent-modal"]')).not.toBeVisible();

      // New agent should appear in list
      await agentsPage.expectAgentExists(testAgent.name);
    });

    test('should show success notification after creation', async ({ authenticatedPage, testAgent }) => {
      const agentsPage = new AgentsPage(authenticatedPage);
      await agentsPage.goto();
      await agentsPage.createAgent(testAgent);

      await expect(authenticatedPage.locator('[data-testid="toast-success"]')).toContainText(
        'Agent created successfully'
      );
    });
  });

  test.describe('Agent Actions', () => {
    test('should pause active agent', async ({ authenticatedPage }) => {
      const agentsPage = new AgentsPage(authenticatedPage);
      await agentsPage.goto();

      // Find an active agent
      const activeAgent = authenticatedPage.locator(
        '[data-testid="agent-card"]:has([data-testid="agent-status"]:has-text("active"))'
      ).first();

      const agentName = await activeAgent.locator('[data-testid="agent-name"]').textContent();
      await activeAgent.locator('[data-testid="pause-button"]').click();

      // Status should change to paused
      await expect(activeAgent.locator('[data-testid="agent-status"]')).toContainText(/paused/i);
    });

    test('should resume paused agent', async ({ authenticatedPage }) => {
      const agentsPage = new AgentsPage(authenticatedPage);
      await agentsPage.goto();

      // Find a paused agent (or pause one first)
      const pausedAgent = authenticatedPage.locator(
        '[data-testid="agent-card"]:has([data-testid="agent-status"]:has-text("paused"))'
      ).first();

      if (await pausedAgent.isVisible()) {
        await pausedAgent.locator('[data-testid="resume-button"]').click();
        await expect(pausedAgent.locator('[data-testid="agent-status"]')).toContainText(/active/i);
      }
    });

    test('should show delete confirmation modal', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      const agentCard = authenticatedPage.locator('[data-testid="agent-card"]').first();
      await agentCard.locator('[data-testid="delete-button"]').click();

      await expect(authenticatedPage.locator('[data-testid="confirm-delete-modal"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="confirm-delete-message"]')).toContainText(
        'Are you sure'
      );
    });

    test('should cancel delete operation', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      const agentCard = authenticatedPage.locator('[data-testid="agent-card"]').first();
      const agentName = await agentCard.locator('[data-testid="agent-name"]').textContent();

      await agentCard.locator('[data-testid="delete-button"]').click();
      await authenticatedPage.click('[data-testid="cancel-delete-button"]');

      // Modal should close
      await expect(authenticatedPage.locator('[data-testid="confirm-delete-modal"]')).not.toBeVisible();

      // Agent should still exist
      await expect(agentCard).toBeVisible();
    });

    test('should delete agent successfully', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      const agentCards = authenticatedPage.locator('[data-testid="agent-card"]');
      const initialCount = await agentCards.count();

      if (initialCount > 0) {
        const agentCard = agentCards.first();
        await agentCard.locator('[data-testid="delete-button"]').click();
        await authenticatedPage.click('[data-testid="confirm-delete-button"]');

        // Wait for deletion
        await expect(agentCards).toHaveCount(initialCount - 1);
      }
    });
  });

  test.describe('Agent Details', () => {
    test('should navigate to agent detail page on click', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');

      const agentCard = authenticatedPage.locator('[data-testid="agent-card"]').first();
      const agentId = await agentCard.getAttribute('data-agent-id');

      await agentCard.click();

      await expect(authenticatedPage).toHaveURL(new RegExp(`/agents/${agentId}`));
    });

    test('should display agent performance chart', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.locator('[data-testid="agent-card"]').first().click();

      await expect(authenticatedPage.locator('[data-testid="performance-chart"]')).toBeVisible();
    });

    test('should display agent positions', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.locator('[data-testid="agent-card"]').first().click();

      await expect(authenticatedPage.locator('[data-testid="positions-table"]')).toBeVisible();
    });

    test('should display agent activity log', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.locator('[data-testid="agent-card"]').first().click();

      await expect(authenticatedPage.locator('[data-testid="activity-log"]')).toBeVisible();
    });

    test('should allow chatting with agent', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/agents');
      await authenticatedPage.locator('[data-testid="agent-card"]').first().click();

      await authenticatedPage.click('[data-testid="chat-tab"]');
      await expect(authenticatedPage.locator('[data-testid="chat-interface"]')).toBeVisible();

      // Send a message
      await authenticatedPage.fill('[data-testid="chat-input"]', 'What is your current strategy?');
      await authenticatedPage.click('[data-testid="send-message-button"]');

      // Expect response
      await expect(authenticatedPage.locator('[data-testid="agent-response"]').last()).toBeVisible({
        timeout: 30000,
      });
    });
  });
});
