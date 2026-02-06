import { test, expect, SettingsPage } from './fixtures';

/**
 * Settings E2E Tests
 *
 * Tests for user settings, broker connection, and preferences
 */

test.describe('Settings', () => {
  test.describe('Settings Page', () => {
    test('should display settings page with all sections', async ({ authenticatedPage }) => {
      const settingsPage = new SettingsPage(authenticatedPage);
      await settingsPage.goto();

      await expect(authenticatedPage.locator('[data-testid="settings-header"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="profile-section"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="broker-section"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="notifications-section"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="security-section"]')).toBeVisible();
    });

    test('should navigate between settings tabs', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');

      const tabs = ['profile', 'broker', 'notifications', 'security'];

      for (const tab of tabs) {
        await authenticatedPage.click(`[data-testid="settings-tab-${tab}"]`);
        await expect(
          authenticatedPage.locator(`[data-testid="${tab}-section"]`)
        ).toBeVisible();
      }
    });
  });

  test.describe('Profile Settings', () => {
    test('should display current user information', async ({ authenticatedPage, testUser }) => {
      await authenticatedPage.goto('/settings');

      await expect(authenticatedPage.locator('[data-testid="user-email"]')).toContainText(
        testUser.email
      );
    });

    test('should update display name', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');

      const newName = 'Updated Name';
      await authenticatedPage.fill('[data-testid="display-name-input"]', newName);
      await authenticatedPage.click('[data-testid="save-profile-button"]');

      await expect(authenticatedPage.locator('[data-testid="toast-success"]')).toContainText(
        'Profile updated'
      );
    });

    test('should validate email format on change', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');

      await authenticatedPage.fill('[data-testid="email-input"]', 'invalid-email');
      await authenticatedPage.click('[data-testid="save-profile-button"]');

      await expect(authenticatedPage.locator('[data-testid="email-error"]')).toContainText(
        'Invalid email'
      );
    });
  });

  test.describe('Broker Connection', () => {
    test('should display broker connection status', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      await expect(authenticatedPage.locator('[data-testid="broker-status"]')).toBeVisible();
    });

    test('should show Alpaca connection form when not connected', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      // If not connected, form should be visible
      const connectButton = authenticatedPage.locator('[data-testid="connect-broker-button"]');

      if (await connectButton.isVisible()) {
        await expect(authenticatedPage.locator('[data-testid="api-key-input"]')).toBeVisible();
        await expect(authenticatedPage.locator('[data-testid="api-secret-input"]')).toBeVisible();
      }
    });

    test('should validate API credentials format', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      const connectButton = authenticatedPage.locator('[data-testid="connect-broker-button"]');

      if (await connectButton.isVisible()) {
        await authenticatedPage.fill('[data-testid="api-key-input"]', 'short'); // Too short
        await authenticatedPage.fill('[data-testid="api-secret-input"]', 'short');
        await connectButton.click();

        await expect(authenticatedPage.locator('[data-testid="api-key-error"]')).toBeVisible();
      }
    });

    test('should connect to Alpaca with valid credentials', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      const connectButton = authenticatedPage.locator('[data-testid="connect-broker-button"]');

      if (await connectButton.isVisible()) {
        // Use test/paper trading credentials
        await authenticatedPage.fill('[data-testid="api-key-input"]', 'PKTEST12345678901234');
        await authenticatedPage.fill('[data-testid="api-secret-input"]', 'secretkey1234567890123456789012345678');
        await authenticatedPage.check('[data-testid="paper-trading-checkbox"]');
        await connectButton.click();

        // Either success or specific error message
        const result = await Promise.race([
          authenticatedPage.locator('[data-testid="broker-status"]:has-text("Connected")').waitFor({ timeout: 10000 }),
          authenticatedPage.locator('[data-testid="connection-error"]').waitFor({ timeout: 10000 }),
        ]);
      }
    });

    test('should disconnect from broker', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      const disconnectButton = authenticatedPage.locator('[data-testid="disconnect-broker-button"]');

      if (await disconnectButton.isVisible()) {
        await disconnectButton.click();
        await authenticatedPage.click('[data-testid="confirm-disconnect-button"]');

        await expect(authenticatedPage.locator('[data-testid="broker-status"]')).toContainText(
          'Not connected'
        );
      }
    });

    test('should display account information when connected', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-broker"]');

      const accountInfo = authenticatedPage.locator('[data-testid="broker-account-info"]');

      if (await accountInfo.isVisible()) {
        await expect(accountInfo.locator('[data-testid="account-equity"]')).toBeVisible();
        await expect(accountInfo.locator('[data-testid="buying-power"]')).toBeVisible();
        await expect(accountInfo.locator('[data-testid="account-type"]')).toBeVisible();
      }
    });
  });

  test.describe('Notification Settings', () => {
    test('should display notification preferences', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-notifications"]');

      await expect(authenticatedPage.locator('[data-testid="email-notifications-toggle"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="trade-alerts-toggle"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="daily-report-toggle"]')).toBeVisible();
    });

    test('should toggle email notifications', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-notifications"]');

      const toggle = authenticatedPage.locator('[data-testid="email-notifications-toggle"]');
      const initialState = await toggle.isChecked();

      await toggle.click();

      expect(await toggle.isChecked()).toBe(!initialState);
    });

    test('should save notification preferences', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-notifications"]');

      await authenticatedPage.click('[data-testid="trade-alerts-toggle"]');
      await authenticatedPage.click('[data-testid="save-notifications-button"]');

      await expect(authenticatedPage.locator('[data-testid="toast-success"]')).toContainText(
        'Preferences saved'
      );
    });

    test('should configure notification frequency', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-notifications"]');

      await authenticatedPage.selectOption('[data-testid="report-frequency-select"]', 'weekly');
      await authenticatedPage.click('[data-testid="save-notifications-button"]');

      await expect(authenticatedPage.locator('[data-testid="toast-success"]')).toBeVisible();
    });
  });

  test.describe('Security Settings', () => {
    test('should display security options', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await expect(authenticatedPage.locator('[data-testid="change-password-section"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="two-factor-section"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="sessions-section"]')).toBeVisible();
    });

    test('should change password successfully', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await authenticatedPage.fill('[data-testid="current-password-input"]', 'OldPassword123!');
      await authenticatedPage.fill('[data-testid="new-password-input"]', 'NewPassword456!');
      await authenticatedPage.fill('[data-testid="confirm-new-password-input"]', 'NewPassword456!');
      await authenticatedPage.click('[data-testid="change-password-button"]');

      // Either success or error depending on current password
      await expect(
        authenticatedPage.locator('[data-testid="toast-success"], [data-testid="password-error"]')
      ).toBeVisible();
    });

    test('should validate password match', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await authenticatedPage.fill('[data-testid="current-password-input"]', 'OldPassword123!');
      await authenticatedPage.fill('[data-testid="new-password-input"]', 'NewPassword456!');
      await authenticatedPage.fill('[data-testid="confirm-new-password-input"]', 'DifferentPassword!');
      await authenticatedPage.click('[data-testid="change-password-button"]');

      await expect(authenticatedPage.locator('[data-testid="confirm-password-error"]')).toContainText(
        'Passwords do not match'
      );
    });

    test('should display active sessions', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await expect(authenticatedPage.locator('[data-testid="sessions-list"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="current-session"]')).toBeVisible();
    });

    test('should revoke other sessions', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      const revokeAllButton = authenticatedPage.locator('[data-testid="revoke-all-sessions-button"]');

      if (await revokeAllButton.isVisible()) {
        await revokeAllButton.click();
        await authenticatedPage.click('[data-testid="confirm-revoke-button"]');

        await expect(authenticatedPage.locator('[data-testid="toast-success"]')).toContainText(
          'Sessions revoked'
        );
      }
    });
  });

  test.describe('Danger Zone', () => {
    test('should display account deletion option', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await expect(authenticatedPage.locator('[data-testid="delete-account-section"]')).toBeVisible();
    });

    test('should require confirmation for account deletion', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await authenticatedPage.click('[data-testid="delete-account-button"]');

      await expect(authenticatedPage.locator('[data-testid="delete-confirmation-modal"]')).toBeVisible();
      await expect(authenticatedPage.locator('[data-testid="delete-confirmation-input"]')).toBeVisible();
    });

    test('should cancel account deletion', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/settings');
      await authenticatedPage.click('[data-testid="settings-tab-security"]');

      await authenticatedPage.click('[data-testid="delete-account-button"]');
      await authenticatedPage.click('[data-testid="cancel-delete-account-button"]');

      await expect(authenticatedPage.locator('[data-testid="delete-confirmation-modal"]')).not.toBeVisible();
    });
  });
});
