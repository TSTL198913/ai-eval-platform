import { test } from '@playwright/test';

test('调试网络请求', async ({ page }) => {
  const requests: { url: string; method: string; status: number }[] = [];
  
  page.on('response', async response => {
    const request = response.request();
    requests.push({
      url: response.url(),
      method: request.method(),
      status: response.status(),
    });
    console.log(`Response: ${response.status()} ${request.method()} ${response.url()}`);
  });

  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  
  await page.locator('input[type="text"]').first().fill('admin');
  await page.locator('input[type="password"]').fill('admin');
  await page.locator('button[type="submit"]').click();
  
  await page.waitForURL('/', { timeout: 10000 });
  
  console.log('\n所有网络请求:');
  requests.forEach(req => {
    console.log(`  ${req.method} ${req.url} -> ${req.status}`);
  });
});
