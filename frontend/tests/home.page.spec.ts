import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('should display the home page with platform title', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/AI 评测平台/);

    const title = page.locator('h1, h2, .title');
    await expect(title).toBeVisible();
  });

  test('should navigate to login page when not authenticated', async ({ page }) => {
    await page.goto('/');

    const loginButton = page.locator('button', { hasText: '登录' });
    if (await loginButton.isVisible()) {
      await loginButton.click();
    }

    await expect(page).toHaveURL(/login/);
  });

  test('should render navigation links', async ({ page }) => {
    await page.goto('/');

    const navLinks = page.locator('nav a, .sidebar a');
    await expect(navLinks).toHaveCount((await navLinks.count()) > 0);
  });
});

test.describe('Login Page', () => {
  test('should render login form with username and password fields', async ({ page }) => {
    await page.goto('/login');

    await expect(page.locator('input[name="username"], input#username')).toBeVisible();
    await expect(page.locator('input[name="password"], input#password')).toBeVisible();

    const loginButton = page.locator('button[type="submit"], button:has-text("登录")');
    await expect(loginButton).toBeVisible();
  });

  test('should show validation error for empty form submission', async ({ page }) => {
    await page.goto('/login');

    const loginButton = page.locator('button[type="submit"], button:has-text("登录")');
    await loginButton.click();

    const errorMessage = page.locator('.ant-form-item-explain, .ant-alert-error, text:has-text("请输入")');
    await expect(errorMessage.first()).toBeVisible();
  });

  test('should show password visibility toggle', async ({ page }) => {
    await page.goto('/login');

    const passwordInput = page.locator('input[name="password"], input#password');
    const eyeIcon = page.locator('[data-testid="eye-icon"], svg[class*="Eye"]');

    await expect(passwordInput).toHaveAttribute('type', 'password');

    if (await eyeIcon.isVisible()) {
      await eyeIcon.click();
      await expect(passwordInput).toHaveAttribute('type', 'text');
    }
  });
});

test.describe('Dashboard', () => {
  test('should show loading state initially', async ({ page }) => {
    await page.goto('/dashboard');

    const spinner = page.locator('.ant-spin, .loading, [class*="spinner"]');
    await expect(spinner.first()).toBeVisible({ timeout: 5000 });
  });

  test('should render dashboard statistics cards', async ({ page }) => {
    await page.goto('/dashboard');

    const statCards = page.locator('.stat-card, .ant-card, [class*="card"]');
    await expect(statCards.first()).toBeVisible({ timeout: 15000 });
  });
});
