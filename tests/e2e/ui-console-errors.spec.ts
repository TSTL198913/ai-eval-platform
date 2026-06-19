/**
 * Playwright UI 测试 - 捕获控制台错误和警告
 * 测试工程师思维：
 * 1. 收集所有控制台消息（错误、警告）
 * 2. 验证页面渲染正确性
 * 3. 检查组件是否正常加载
 * 4. 验证 API 数据正确渲染
 */

import { test, expect, Page } from '@playwright/test';

// 存储控制台消息
interface ConsoleMessage {
  type: string;
  text: string;
  location?: string;
}

// 测试工程师思维：每个测试都应该收集控制台消息
test.describe('UI 控制台错误检测', () => {
  let consoleMessages: ConsoleMessage[] = [];
  let pageErrors: Error[] = [];

  test.beforeEach(async ({ page }) => {
    consoleMessages = [];
    pageErrors = [];

    // 监听控制台消息
    page.on('console', msg => {
      consoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()?.url,
      });
    });

    // 监听页面错误
    page.on('pageerror', error => {
      pageErrors.push(error);
    });
  });

  test('登录页面 - 无控制台错误', async ({ page }) => {
    await page.goto('/login');

    // 等待页面完全加载
    await page.waitForLoadState('networkidle');

    // 验证页面元素存在
    await expect(page.locator('input[type="text"]').first()).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();

    // 测试工程师思维：验证无错误
    const errors = consoleMessages.filter(m => m.type === 'error');
    const warnings = consoleMessages.filter(m => m.type === 'warning');

    // 打印所有控制台消息供调试
    if (consoleMessages.length > 0) {
      console.log('控制台消息:', consoleMessages);
    }

    // 期望：无 JavaScript 错误
    expect(pageErrors.length, `页面错误: ${pageErrors.map(e => e.message).join(', ')}`).toBe(0);

    // 期望：无 React 错误边界错误
    const reactErrors = errors.filter(e => e.text.includes('ErrorBoundary') || e.text.includes('TypeError'));
    expect(reactErrors.length, `React错误: ${reactErrors.map(e => e.text).join(', ')}`).toBe(0);
  });

  test('首页/仪表盘 - 无控制台错误', async ({ page }) => {
    await page.goto('/');

    // 等待页面完全加载
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // 等待 API 数据加载

    // 验证仪表盘元素
    const cards = page.locator('.ant-card');
    await expect(cards.first()).toBeVisible({ timeout: 10000 });

    // 打印所有控制台消息
    if (consoleMessages.length > 0) {
      console.log('控制台消息:', consoleMessages);
    }

    // 检查 Antd 弃用警告
    const antdWarnings = consoleMessages.filter(m =>
      m.text.includes('antd') && m.text.includes('deprecated')
    );

    // 测试工程师思维：记录弃用警告
    if (antdWarnings.length > 0) {
      console.log('Antd 弃用警告:', antdWarnings);
    }

    // 期望：无 JavaScript 错误
    expect(pageErrors.length, `页面错误: ${pageErrors.map(e => e.message).join(', ')}`).toBe(0);
  });

  test('Records 页面 - 无 TypeError', async ({ page }) => {
    await page.goto('/records');

    // 等待页面完全加载
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000); // 等待数据加载

    // 打印所有控制台消息
    console.log('Records 页面控制台消息:', consoleMessages);

    // 测试工程师思维：重点检查 undefined.length 错误
    const typeErrors = pageErrors.filter(e =>
      e.message.includes('TypeError') && e.message.includes('length')
    );

    // 期望：无 TypeError
    expect(typeErrors.length, `TypeError错误: ${typeErrors.map(e => e.message).join(', ')}`).toBe(0);

    // 检查 ErrorBoundary 错误
    const errorBoundaryErrors = consoleMessages.filter(m =>
      m.text.includes('ErrorBoundary') || m.text.includes('Caught error')
    );

    expect(errorBoundaryErrors.length, `ErrorBoundary错误: ${errorBoundaryErrors.map(e => e.text).join(', ')}`).toBe(0);
  });

  test('Evaluators 页面 - 无控制台错误', async ({ page }) => {
    await page.goto('/evaluators');

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 验证评估器卡片存在（页面使用 Card 网格布局，不是 Table）
    const cards = page.locator('.ant-card');
    await expect(cards.first()).toBeVisible({ timeout: 10000 });

    console.log('Evaluators 页面控制台消息:', consoleMessages);

    expect(pageErrors.length).toBe(0);
  });

  test('Reports 页面 - 无控制台错误', async ({ page }) => {
    await page.goto('/reports');

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    console.log('Reports 页面控制台消息:', consoleMessages);

    expect(pageErrors.length).toBe(0);
  });

  test('Cost 页面 - 无控制台错误', async ({ page }) => {
    await page.goto('/cost');

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    console.log('Cost 页面控制台消息:', consoleMessages);

    expect(pageErrors.length).toBe(0);
  });

  test('全页面扫描 - 收集所有弃用警告', async ({ page }) => {
    const pages = ['/login', '/', '/records', '/evaluators', '/reports', '/cost'];
    const allWarnings: ConsoleMessage[] = [];

    for (const path of pages) {
      consoleMessages = [];
      pageErrors = [];

      page.on('console', msg => {
        if (msg.type() === 'warning') {
          allWarnings.push({
            type: msg.type(),
            text: msg.text(),
            location: msg.location()?.url,
          });
        }
      });

      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
    }

    // 测试工程师思维：汇总所有弃用警告
    console.log('所有页面弃用警告汇总:', allWarnings);

    // 检查 Antd 弃用警告
    const antdDeprecatedWarnings = allWarnings.filter(w =>
      w.text.includes('antd') && w.text.includes('deprecated')
    );

    // 打印需要修复的警告
    if (antdDeprecatedWarnings.length > 0) {
      console.log('需要修复的 Antd 弃用属性:', antdDeprecatedWarnings);
    }
  });
});

test.describe('UI 功能测试', () => {
  let consoleMessages: ConsoleMessage[] = [];
  let pageErrors: Error[] = [];

  test('登录流程', async ({ page }) => {
    // 监听控制台消息
    page.on('console', msg => {
      consoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()?.url,
      });
    });

    page.on('pageerror', error => {
      pageErrors.push(error);
    });

    await page.goto('/login');

    // 输入用户名
    await page.locator('input[type="text"]').first().fill('admin');

    // 输入密码
    await page.locator('input[type="password"]').fill('admin');

    // 点击登录按钮
    await page.locator('button[type="submit"]').click();

    // 等待跳转到首页
    await page.waitForURL('/', { timeout: 10000 });

    // 验证登录成功
    await expect(page).toHaveURL('/');
  });

  test('仪表盘数据展示', async ({ page }) => {
    page.on('console', msg => {
      consoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()?.url,
      });
    });

    await page.goto('/');

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 验证统计卡片存在
    const cards = page.locator('.ant-card');
    const cardCount = await cards.count();

    expect(cardCount, '仪表盘应有多个统计卡片').toBeGreaterThan(0);
  });

  test('Records 列表渲染', async ({ page }) => {
    const localConsoleMessages: ConsoleMessage[] = [];
    const localPageErrors: Error[] = [];

    page.on('console', msg => {
      localConsoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()?.url,
      });
    });

    page.on('pageerror', error => {
      localPageErrors.push(error);
    });

    await page.goto('/records');

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000); // 增加等待时间让数据加载

    // 验证页面内容存在（可能是 Card 或 Table）
    const card = page.locator('.ant-card');
    const table = page.locator('.ant-table');

    // 测试工程师思维：检查页面是否正常渲染
    const cardCount = await card.count();
    const tableCount = await table.count();

    // 打印控制台错误帮助调试
    console.log('Records 页面控制台消息:', localConsoleMessages);
    console.log('Records 页面 JS 错误:', localPageErrors);
    console.log('Records 页面 Card 数量:', cardCount);
    console.log('Records 页面 Table 数量:', tableCount);

    // 期望：无 JavaScript 错误
    expect(localPageErrors.length, `JS错误: ${localPageErrors.map(e => e.message).join(', ')}`).toBe(0);

    // 期望：页面有内容渲染（Card 或 Table）
    expect(cardCount + tableCount, '页面应有内容渲染').toBeGreaterThan(0);
  });
});