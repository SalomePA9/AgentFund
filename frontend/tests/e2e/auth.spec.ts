import { test, expect, LoginPage, RegisterPage } from './fixtures';

/**
 * Authentication E2E Tests
 *
 * Tests for user registration, login, logout, and session management
 */

test.describe('Authentication', () => {
  test.describe('Login', () => {
    test('should display login form', async ({ page }) => {
      await page.goto('/login');

      await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
    });

    test('should show error for invalid credentials', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();
      await loginPage.login('invalid@example.com', 'wrongpassword');

      await loginPage.expectError('Invalid email or password');
    });

    test('should show validation errors for empty fields', async ({ page }) => {
      await page.goto('/login');
      await page.click('[data-testid="login-button"]');

      await expect(page.locator('[data-testid="email-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="password-error"]')).toBeVisible();
    });

    test('should show error for invalid email format', async ({ page }) => {
      await page.goto('/login');
      await page.fill('[data-testid="email-input"]', 'not-an-email');
      await page.fill('[data-testid="password-input"]', 'password123');
      await page.click('[data-testid="login-button"]');

      await expect(page.locator('[data-testid="email-error"]')).toContainText('Invalid email');
    });

    test('should have link to registration page', async ({ page }) => {
      await page.goto('/login');
      await page.click('[data-testid="register-link"]');

      await expect(page).toHaveURL('/register');
    });

    test('should have link to forgot password', async ({ page }) => {
      await page.goto('/login');

      await expect(page.locator('[data-testid="forgot-password-link"]')).toBeVisible();
    });
  });

  test.describe('Registration', () => {
    test('should display registration form', async ({ page }) => {
      await page.goto('/register');

      await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="confirm-password-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="register-button"]')).toBeVisible();
    });

    test('should show error for password mismatch', async ({ page }) => {
      const registerPage = new RegisterPage(page);
      await registerPage.goto();
      await registerPage.register('test@example.com', 'Password123!', 'DifferentPassword');

      await expect(page.locator('[data-testid="confirm-password-error"]')).toContainText(
        'Passwords do not match'
      );
    });

    test('should show error for weak password', async ({ page }) => {
      await page.goto('/register');
      await page.fill('[data-testid="email-input"]', 'test@example.com');
      await page.fill('[data-testid="password-input"]', '123'); // Too weak
      await page.fill('[data-testid="confirm-password-input"]', '123');
      await page.click('[data-testid="register-button"]');

      await expect(page.locator('[data-testid="password-error"]')).toContainText(
        'at least 8 characters'
      );
    });

    test('should show error for existing email', async ({ page }) => {
      const registerPage = new RegisterPage(page);
      await registerPage.goto();
      await registerPage.register('existing@example.com', 'Password123!');

      await registerPage.expectError('Email already registered');
    });

    test('should have link to login page', async ({ page }) => {
      await page.goto('/register');
      await page.click('[data-testid="login-link"]');

      await expect(page).toHaveURL('/login');
    });
  });

  test.describe('Session Management', () => {
    test('should persist session on page refresh', async ({ authenticatedPage }) => {
      await authenticatedPage.reload();

      await expect(authenticatedPage).toHaveURL('/dashboard');
      await expect(
        authenticatedPage.locator('[data-testid="user-menu"]')
      ).toBeVisible();
    });

    test('should logout successfully', async ({ authenticatedPage }) => {
      await authenticatedPage.click('[data-testid="user-menu"]');
      await authenticatedPage.click('[data-testid="logout-button"]');

      await expect(authenticatedPage).toHaveURL('/login');
    });

    test('should redirect to login when accessing protected route', async ({ page }) => {
      await page.goto('/dashboard');

      await expect(page).toHaveURL(/\/login/);
    });

    test('should redirect to login when accessing agents page', async ({ page }) => {
      await page.goto('/agents');

      await expect(page).toHaveURL(/\/login/);
    });

    test('should redirect to login when accessing settings page', async ({ page }) => {
      await page.goto('/settings');

      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Password Reset', () => {
    test('should display forgot password form', async ({ page }) => {
      await page.goto('/login');
      await page.click('[data-testid="forgot-password-link"]');

      await expect(page.locator('[data-testid="reset-email-input"]')).toBeVisible();
      await expect(page.locator('[data-testid="reset-password-button"]')).toBeVisible();
    });

    test('should send reset email for valid email', async ({ page }) => {
      await page.goto('/login');
      await page.click('[data-testid="forgot-password-link"]');
      await page.fill('[data-testid="reset-email-input"]', 'test@example.com');
      await page.click('[data-testid="reset-password-button"]');

      await expect(page.locator('[data-testid="reset-success-message"]')).toContainText(
        'Check your email'
      );
    });
  });
});
