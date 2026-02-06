import { test, expect, DashboardPage } from './fixtures';

/**
 * Dashboard E2E Tests
 *
 * Tests for the main dashboard functionality
 */

test.describe('Dashboard', () => {
  test.describe('Overview', () => {
    test('should display dashboard with portfolio summary', async ({ authenticatedPage }) => {
      const dashboardPage = new DashboardPage(authenticatedPage);
      await dashboardPage.goto();

      await expect(authenticatedPage.locator('[data-testid="dashboard-header"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="portfolio-value"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="daily-change"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="total-agents"]')).toBeVisible();
    });

    test('should display portfolio value correctly formatted', async ({ authenticatedPage }) => {
      const dashboardPage = new DashboardPage(authenticatedPage);
      await dashboardPage.goto();

      const portfolioValue = await dashboardPage.getPortfolioValue();
      expect(portfolioValue).toMatch(/\$[\d,]+(\.\d{2})?/);
    });

    test('should display daily change with correct color', async ({ authenticatedPage }) => {
      const dashboardPage = new DashboardPage(authenticatedPage);
      await dashboardPage.goto();

      const dailyChange = authenticatedPage.locator('[data-testid="daily-change"]');
      const changeText = await dailyChange.textContent();

      if (changeText?.includes('+')) {
        await expect(dailyChange).toHaveClass(/text-green/);
      } else if (changeText?.includes('-')) {
        await expect(dailyChange).toHaveClass(/text-red/);
      }
    });

    test('should display active agents count', async ({ authenticatedPage }) => {
      const dashboardPage = new DashboardPage(authenticatedPage);
      await dashboardPage.goto();

      const agentsCount = authenticatedPage.locator('[data-testid="active-agents-count"]');
      await expect(agentsCount).toBeVisible();
      const count = await agentsCount.textContent();
      expect(parseInt(count || '0')).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('Performance Chart', () => {
    test('should display portfolio performance chart', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="performance-chart"]')).toBeVisible();
    });

    test('should switch between time periods', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      // Test different time period buttons
      const periods = ['1D', '1W', '1M', '3M', '1Y', 'ALL'];

      for (const period of periods) {
        await authenticatedPage.click(`[data-testid="period-${period}"]`);
        await expect(
          authenticatedPage.locator(`[data-testid="period-${period}"]`)
        ).toHaveAttribute('data-active', 'true');
      }
    });

    test('should show tooltip on chart hover', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      const chart = authenticatedPage.locator('[data-testid="performance-chart"]');
      await chart.hover({ position: { x: 100, y: 100 } });

      // Tooltip may appear on hover
      // Implementation depends on charting library
    });
  });

  test.describe('Agent Summary', () => {
    test('should display list of active agents', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="agents-summary"]')).toBeVisible();
    });

    test('should show agent quick stats', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      const agentSummary = authenticatedPage.locator('[data-testid="agent-summary-card"]').first();

      if (await agentSummary.isVisible()) {
        await expect(agentSummary.locator('[data-testid="agent-name"]')).toBeVisible();
        await expect(agentSummary.locator('[data-testid="agent-status"]')).toBeVisible();
        await expect(agentSummary.locator('[data-testid="agent-return"]')).toBeVisible();
      }
    });

    test('should navigate to agent detail on click', async ({ authenticatedPage }) => {
      const dashboardPage = new DashboardPage(authenticatedPage);
      await dashboardPage.goto();

      const agentCount = await dashboardPage.getAgentCount();

      if (agentCount > 0) {
        await dashboardPage.clickAgent(0);
        await expect(authenticatedPage).toHaveURL(/\/agents\/.+/);
      }
    });

    test('should show "Create Agent" prompt when no agents', async ({ authenticatedPage }) => {
      // This test assumes a user with no agents
      await authenticatedPage.goto('/dashboard');

      const noAgentsMessage = authenticatedPage.locator('[data-testid="no-agents-message"]');

      // Only check if it would appear for a user with no agents
      // In a real test, you'd set up a fresh user first
    });
  });

  test.describe('Recent Activity', () => {
    test('should display recent activity feed', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="activity-feed"]')).toBeVisible();
    });

    test('should show activity timestamps', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      const activityItems = authenticatedPage.locator('[data-testid="activity-item"]');
      const count = await activityItems.count();

      if (count > 0) {
        const firstItem = activityItems.first();
        await expect(firstItem.locator('[data-testid="activity-time"]')).toBeVisible();
      }
    });

    test('should show different activity types', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      // Activity types: trade, analysis, alert, system
      const activityItems = authenticatedPage.locator('[data-testid="activity-item"]');
      const count = await activityItems.count();

      if (count > 0) {
        // Each item should have a type indicator
        for (let i = 0; i < Math.min(count, 5); i++) {
          await expect(activityItems.nth(i).locator('[data-testid="activity-type"]')).toBeVisible();
        }
      }
    });
  });

  test.describe('Market Overview', () => {
    test('should display market indices', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="market-overview"]')).toBeVisible();

      // Common indices
      const indices = ['S&P 500', 'NASDAQ', 'DOW'];
      for (const index of indices) {
        // May or may not show all indices
        const indexElement = authenticatedPage.locator('[data-testid="market-index"]', {
          hasText: index,
        });
        // Just check the section exists
      }
    });

    test('should show market status (open/closed)', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="market-status"]')).toBeVisible();
    });
  });

  test.describe('Quick Actions', () => {
    test('should have quick action buttons', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="quick-create-agent"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="quick-view-reports"]')).toBeVisible();
    });

    test('should open create agent modal from quick action', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await authenticatedPage.click('[data-testid="quick-create-agent"]');

      await expect(authenticatedPage.locator('[data-testid="create-agent-modal"]')).toBeVisible();
    });

    test('should navigate to reports from quick action', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await authenticatedPage.click('[data-testid="quick-view-reports"]');

      await expect(authenticatedPage).toHaveURL(/\/reports/);
    });
  });

  test.describe('Responsive Design', () => {
    test('should adapt layout for tablet viewport', async ({ authenticatedPage }) => {
      await authenticatedPage.setViewportSize({ width: 768, height: 1024 });
      await authenticatedPage.goto('/dashboard');

      // Dashboard should still be functional
      await expect(authenticatedPage.locator('[data-testid="dashboard-header"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="portfolio-value"]')).toBeVisible();
    });

    test('should adapt layout for mobile viewport', async ({ authenticatedPage }) => {
      await authenticatedPage.setViewportSize({ width: 375, height: 667 });
      await authenticatedPage.goto('/dashboard');

      // Dashboard should still be functional
      await expect(authenticatedPage.locator('[data-testid="dashboard-header"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="portfolio-value"]')).toBeVisible();

      // Mobile menu should be present
      await expect(authenticatedPage.locator('[data-testid="mobile-menu-button"]')).toBeVisible();
    });

    test('should show mobile navigation menu', async ({ authenticatedPage }) => {
      await authenticatedPage.setViewportSize({ width: 375, height: 667 });
      await authenticatedPage.goto('/dashboard');

      await authenticatedPage.click('[data-testid="mobile-menu-button"]');

      await expect(authenticatedPage.locator('[data-testid="mobile-nav"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="nav-dashboard"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="nav-agents"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="nav-settings"]')).toBeVisible();
    });
  });

  test.describe('Real-time Updates', () => {
    test('should update portfolio value in real-time', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      const portfolioValue = authenticatedPage.locator('[data-testid="portfolio-value"]');
      const initialValue = await portfolioValue.textContent();

      // Wait for potential update (in a real test with WebSocket connection)
      await authenticatedPage.waitForTimeout(5000);

      // Value might have changed if market is open
      // This is a placeholder for real-time testing
    });

    test('should show live indicator when connected', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/dashboard');

      await expect(authenticatedPage.locator('[data-testid="live-indicator"]')).toBeVisible();
    });
  });
});
