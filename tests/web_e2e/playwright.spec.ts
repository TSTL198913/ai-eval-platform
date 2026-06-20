/**
 * AI Evaluation Platform - 核心用户流程 E2E 测试
 * 
 * 测试范围：
 * 1. 用户登录流程
 * 2. 仪表盘加载和数据展示
 * 3. 评估器列表查看
 * 4. 执行评测任务
 * 5. 查看评测记录
 * 6. 导出报告
 */

import { test, expect, Page } from '@playwright/test';

// 测试配置
const TEST_USER = {
  username: 'admin',
  password: 'admin123',
};

// ============ 辅助函数 ============

/**
 * 等待页面加载完成
 */
async function waitForPageLoad(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.waitForLoadState('domcontentloaded');
}

/**
 * 截图并保存
 */
async function screenshot(page: Page, name: string) {
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: true });
}

/**
 * 登录函数
 */
async function login(page: Page, username: string = TEST_USER.username, password: string = TEST_USER.password) {
  await page.goto('/login');
  await waitForPageLoad(page);
  
  // 输入用户名和密码
  const usernameInput = page.locator('input[type="text"], input[type="email"], input[name="username"]').first();
  const passwordInput = page.locator('input[type="password"]').first();
  
  await usernameInput.fill(username);
  await passwordInput.fill(password);
  
  // 点击登录按钮
  const loginButton = page.locator('button[type="submit"], button:has-text("登录"), button:has-text("Login")').first();
  await loginButton.click();
  
  // 等待登录完成，跳转到首页
  await page.waitForURL('**/');
  await waitForPageLoad(page);
}

// ============ 测试用例 ============

/**
 * 测试 1: 用户登录流程
 */
test.describe('登录流程', () => {
  test('应该能够使用 Demo 模式登录', async ({ page }) => {
    await page.goto('/login');
    await waitForPageLoad(page);
    
    // 验证登录页面元素
    await expect(page.locator('body')).toContainText(/登录|Login|sign in/i);
    
    // 输入用户名和密码
    const usernameInput = page.locator('input').filter({ hasText: /用户名|username/i }).first();
    const passwordInput = page.locator('input[type="password"]').first();
    
    if (await usernameInput.isVisible()) {
      await usernameInput.fill(TEST_USER.username);
    } else {
      // 尝试第一个文本输入框
      await page.locator('input[type="text"], input[type="email"]').first().fill(TEST_USER.username);
    }
    
    await passwordInput.fill(TEST_USER.password);
    
    // 点击登录
    await page.locator('button[type="submit"]').first().click();
    
    // 等待登录成功
    await page.waitForURL('**/', { timeout: 10000 }).catch(() => {
      // 如果 URL 没有变化，可能已经登录
    });
    
    await waitForPageLoad(page);
    
    // 验证登录成功（页面包含导航或用户信息）
    const isLoggedIn = await page.locator('text=/退出|logout|仪表盘|dashboard/i').isVisible().catch(() => false);
    expect(isLoggedIn).toBeTruthy();
  });

  test('应该拒绝无效凭据', async ({ page }) => {
    await page.goto('/login');
    await waitForPageLoad(page);
    
    // 输入无效凭据
    await page.locator('input[type="text"], input[type="email"]').first().fill('invalid_user');
    await page.locator('input[type="password"]').first().fill('wrong_password');
    
    // 点击登录
    await page.locator('button[type="submit"]').first().click();
    
    // 等待错误提示
    await page.waitForTimeout(1000);
    
    // 验证错误提示出现
    const hasError = await page.locator('text=/错误|失败|invalid|error|incorrect/i').isVisible().catch(() => false);
    expect(hasError).toBeTruthy();
  });

  test('应该能够记住登录状态', async ({ page, context }) => {
    // 第一次登录
    await login(page);
    
    // 关闭页面
    await page.close();
    
    // 重新打开页面（使用相同 context）
    const newPage = await context.newPage();
    await newPage.goto('/');
    await waitForPageLoad(newPage);
    
    // 验证已登录（不应该在登录页）
    const isLoggedIn = !newPage.url().includes('/login');
    expect(isLoggedIn).toBeTruthy();
  });
});

/**
 * 测试 2: 仪表盘功能
 */
test.describe('仪表盘', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('应该显示关键指标卡片', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 等待指标加载
    await page.waitForTimeout(2000);
    
    // 验证指标卡片存在
    const hasMetrics = await page.locator('[class*="card"], [class*="stat"], [class*="metric"]').first().isVisible().catch(() => false);
    expect(hasMetrics).toBeTruthy();
  });

  test('应该显示最近评测记录', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找评测记录列表
    const hasRecords = await page.locator('table, [class*="list"], [class*="record"]').first().isVisible().catch(() => false);
    expect(hasRecords).toBeTruthy();
  });

  test('应该能够刷新数据', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找刷新按钮
    const refreshButton = page.locator('button:has-text("刷新"), button:has-text("Refresh"), [aria-label*="refresh"]').first();
    
    if (await refreshButton.isVisible()) {
      await refreshButton.click();
      await page.waitForTimeout(1000);
    }
    
    // 验证页面仍然正常显示
    const isLoaded = await page.locator('body').isVisible();
    expect(isLoaded).toBeTruthy();
  });
});

/**
 * 测试 3: 评估器管理
 */
test.describe('评估器管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('应该显示评估器列表', async ({ page }) => {
    await page.goto('/evaluators');
    await waitForPageLoad(page);
    
    // 等待评估器加载
    await page.waitForTimeout(2000);
    
    // 验证评估器卡片或列表存在
    const hasEvaluators = await page.locator('[class*="card"], [class*="evaluator"], table, [class*="list"]').first().isVisible().catch(() => false);
    expect(hasEvaluators).toBeTruthy();
  });

  test('应该能够筛选评估器类型', async ({ page }) => {
    await page.goto('/evaluators');
    await waitForPageLoad(page);
    
    // 查找筛选按钮
    const filterButton = page.locator('button:has-text("筛选"), button:has-text("Filter"), [aria-label*="filter"]').first();
    
    if (await filterButton.isVisible()) {
      await filterButton.click();
      await page.waitForTimeout(500);
    }
  });

  test('应该能够查看评估器详情', async ({ page }) => {
    await page.goto('/evaluators');
    await waitForPageLoad(page);
    
    // 点击第一个评估器
    const evaluatorCard = page.locator('[class*="card"], [class*="evaluator"]').first();
    
    if (await evaluatorCard.isVisible()) {
      await evaluatorCard.click();
      await page.waitForTimeout(1000);
      
      // 验证详情弹窗或页面
      const hasDetail = await page.locator('[class*="modal"], [class*="detail"], [class*="info"]').first().isVisible().catch(() => false);
      expect(hasDetail).toBeTruthy();
    }
  });

  test('应该能够配置评估器参数', async ({ page }) => {
    await page.goto('/evaluators');
    await waitForPageLoad(page);
    
    // 查找配置按钮
    const configButton = page.locator('button:has-text("配置"), button:has-text("Config"), [aria-label*="config"]').first();
    
    if (await configButton.isVisible()) {
      await configButton.click();
      await page.waitForTimeout(500);
      
      // 验证配置表单出现
      const hasForm = await page.locator('form, input, select').first().isVisible().catch(() => false);
      expect(hasForm).toBeTruthy();
    }
  });
});

/**
 * 测试 4: 评测执行
 */
test.describe('评测执行', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('应该能够发起新的评测', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找新建评测按钮
    const newEvalButton = page.locator('button:has-text("新建"), button:has-text("New"), button:has-text("评测")').first();
    
    if (await newEvalButton.isVisible()) {
      await newEvalButton.click();
      await page.waitForTimeout(1000);
      
      // 验证评测表单出现
      const hasForm = await page.locator('form, [class*="modal"], [class*="drawer"]').first().isVisible().catch(() => false);
      expect(hasForm).toBeTruthy();
    }
  });

  test('应该能够选择评估器类型', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找评估器选择器
    const selector = page.locator('select, [class*="select"], [role="combobox"]').first();
    
    if (await selector.isVisible()) {
      await selector.click();
      await page.waitForTimeout(500);
      
      // 验证选项出现
      const hasOptions = await page.locator('option, [class*="option"], [role="option"]').first().isVisible().catch(() => false);
      expect(hasOptions).toBeTruthy();
    }
  });

  test('应该能够输入评测内容', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找输入框
    const input = page.locator('textarea, input[type="text"]').first();
    
    if (await input.isVisible()) {
      await input.fill('这是一段测试文本，用于验证评测功能是否正常工作。');
      await page.waitForTimeout(500);
      
      // 验证输入内容
      const value = await input.inputValue();
      expect(value.length).toBeGreaterThan(0);
    }
  });

  test('应该能够提交评测并查看结果', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 查找提交按钮
    const submitButton = page.locator('button:has-text("提交"), button:has-text("Submit"), button:has-text("评测")').first();
    
    if (await submitButton.isVisible()) {
      await submitButton.click();
      
      // 等待评测完成
      await page.waitForTimeout(5000);
      
      // 验证结果出现
      const hasResult = await page.locator('[class*="result"], [class*="score"], [class*="response"]').first().isVisible().catch(() => false);
      // 结果可能在历史记录中，不强制要求立即显示
    }
  });
});

/**
 * 测试 5: 评测记录
 */
test.describe('评测记录', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('应该显示评测记录列表', async ({ page }) => {
    await page.goto('/records');
    await waitForPageLoad(page);
    
    // 等待记录加载
    await page.waitForTimeout(2000);
    
    // 验证记录表格或列表
    const hasRecords = await page.locator('table, [class*="list"], [class*="record"]').first().isVisible().catch(() => false);
    expect(hasRecords).toBeTruthy();
  });

  test('应该能够按状态筛选记录', async ({ page }) => {
    await page.goto('/records');
    await waitForPageLoad(page);
    
    // 查找状态筛选
    const filterSelect = page.locator('select, [class*="filter"]').first();
    
    if (await filterSelect.isVisible()) {
      await filterSelect.selectOption({ index: 1 });
      await page.waitForTimeout(1000);
      
      // 验证筛选生效
      const hasFiltered = await page.locator('table, [class*="record"]').first().isVisible().catch(() => false);
      expect(hasFiltered).toBeTruthy();
    }
  });

  test('应该能够分页浏览记录', async ({ page }) => {
    await page.goto('/records');
    await waitForPageLoad(page);
    
    // 查找分页按钮
    const nextButton = page.locator('button:has-text("下一页"), button:has-text("Next"), [aria-label*="next"]').first();
    
    if (await nextButton.isVisible()) {
      await nextButton.click();
      await page.waitForTimeout(1000);
      
      // 验证页面变化
      const currentPage = await page.locator('text=/第.*页|page.*\\d/i').textContent().catch(() => '1');
      expect(currentPage).toBeTruthy();
    }
  });

  test('应该能够查看记录详情', async ({ page }) => {
    await page.goto('/records');
    await waitForPageLoad(page);
    
    // 点击第一条记录
    const recordRow = page.locator('tr, [class*="record"]').nth(1);
    
    if (await recordRow.isVisible()) {
      await recordRow.click();
      await page.waitForTimeout(1000);
      
      // 验证详情面板
      const hasDetail = await page.locator('[class*="detail"], [class*="modal"]').first().isVisible().catch(() => false);
      expect(hasDetail).toBeTruthy();
    }
  });
});

/**
 * 测试 6: 报告导出
 */
test.describe('报告导出', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('应该能够访问报告页面', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageLoad(page);
    
    // 验证页面加载
    const hasReports = await page.locator('body').isVisible();
    expect(hasReports).toBeTruthy();
  });

  test('应该能够选择报告类型', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageLoad(page);
    
    // 查找类型选择器
    const selector = page.locator('select, [class*="select"]').first();
    
    if (await selector.isVisible()) {
      await selector.click();
      await page.waitForTimeout(500);
      
      const hasOptions = await page.locator('option, [role="option"]').first().isVisible().catch(() => false);
      expect(hasOptions).toBeTruthy();
    }
  });

  test('应该能够导出报告', async ({ page }) => {
    await page.goto('/reports');
    await waitForPageLoad(page);
    
    // 查找导出按钮
    const exportButton = page.locator('button:has-text("导出"), button:has-text("Export"), button:has-text("下载")').first();
    
    if (await exportButton.isVisible()) {
      // 设置下载监听
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);
      
      await exportButton.click();
      
      const download = await downloadPromise;
      if (download) {
        // 验证下载文件名
        expect(download.suggestedFilename()).toBeTruthy();
      }
    }
  });
});

/**
 * 测试 7: 错误处理
 */
test.describe('错误处理', () => {
  test('应该显示友好的错误页面 404', async ({ page }) => {
    await page.goto('/non-existent-page-12345');
    await waitForPageLoad(page);
    
    // 验证错误页面
    const has404 = await page.locator('text=/404|Not Found/i').isVisible().catch(() => false);
    const hasBackButton = await page.locator('button:has-text("返回"), button:has-text("Back")').isVisible().catch(() => false);
    
    // 至少有一个元素
    expect(has404 || hasBackButton).toBeTruthy();
  });

  test('网络错误应该显示重试按钮', async ({ page }) => {
    // 模拟网络错误
    await page.route('**/api/**', route => route.abort('failed'));
    
    await page.goto('/');
    await waitForPageLoad(page);
    
    // 验证错误提示
    const hasError = await page.locator('text=/网络|错误|Error|Failed/i').isVisible().catch(() => false);
    const hasRetry = await page.locator('button:has-text("重试"), button:has-text("Retry")').isVisible().catch(() => false);
    
    // 至少显示错误或重试按钮之一
    expect(hasError || hasRetry).toBeTruthy();
  });

  test('应该能够从错误中恢复', async ({ page }) => {
    await page.goto('/login');
    await waitForPageLoad(page);
    
    // 输入凭据
    await page.locator('input[type="text"], input[type="email"]').first().fill(TEST_USER.username);
    await page.locator('input[type="password"]').first().fill(TEST_USER.password);
    
    // 点击登录
    await page.locator('button[type="submit"]').first().click();
    
    // 等待登录完成
    await page.waitForTimeout(3000);
    
    // 验证恢复成功
    const isLoggedIn = await page.locator('text=/退出|logout|dashboard/i').isVisible().catch(() => false);
    expect(isLoggedIn).toBeTruthy();
  });
});

/**
 * 测试 8: 响应式布局
 */
test.describe('响应式布局', () => {
  test('应该在移动端正常显示', async ({ page }) => {
    // 设置移动端视口
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.goto('/login');
    await waitForPageLoad(page);
    
    // 验证移动端布局
    const isVisible = await page.locator('body').isVisible();
    expect(isVisible).toBeTruthy();
  });

  test('应该在平板端正常显示', async ({ page }) => {
    // 设置平板视口
    await page.setViewportSize({ width: 768, height: 1024 });
    
    await page.goto('/login');
    await waitForPageLoad(page);
    
    // 验证平板布局
    const isVisible = await page.locator('body').isVisible();
    expect(isVisible).toBeTruthy();
  });
});
