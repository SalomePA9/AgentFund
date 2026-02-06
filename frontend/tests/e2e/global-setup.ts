import { chromium, FullConfig } from '@playwright/test';

/**
 * Global setup for Playwright E2E tests
 *
 * This runs once before all tests to:
 * - Verify the application is accessible
 * - Set up any global test data
 * - Pre-authenticate test users if needed
 */
async function globalSetup(config: FullConfig) {
  const { baseURL } = config.projects[0].use;

  console.log('🚀 Starting global E2E test setup...');
  console.log(`📍 Base URL: ${baseURL}`);

  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    // Wait for the application to be ready
    console.log('⏳ Waiting for application to be ready...');

    // Try to access the homepage
    const response = await page.goto(baseURL as string, {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });

    if (!response?.ok()) {
      throw new Error(`Application not accessible at ${baseURL}. Status: ${response?.status()}`);
    }

    console.log('✅ Application is ready');

    // Create test user storage state (if needed for authenticated tests)
    // This would typically involve:
    // 1. Registering a test user via API
    // 2. Logging in and saving the auth state
    // 3. Storing it for use by authenticated tests

    // For now, we'll just verify the app loads
    const title = await page.title();
    console.log(`📄 Page title: ${title}`);

  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }

  console.log('✅ Global E2E test setup complete');
}

export default globalSetup;
