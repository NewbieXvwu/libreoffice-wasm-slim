// 冒烟测试驱动：puppeteer 打开 smoke_page.html，等待 window.__SMOKE_RESULT。
// LOWA 初始化约 70-80 秒（首次），超时给足 7 分钟。
// 用法: node smoke_test.mjs [url=http://127.0.0.1:8080/]
import puppeteer from 'puppeteer';

const url = process.argv[2] || 'http://127.0.0.1:8080/';

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
page.on('console', (msg) => console.log('[page]', msg.text()));
page.on('pageerror', (err) => console.log('[pageerror]', String(err)));

console.log('打开', url);
await page.goto(url, {waitUntil: 'domcontentloaded', timeout: 60000});

await page.waitForFunction('window.__SMOKE_RESULT !== undefined',
                           {timeout: 420000, polling: 1000});
const result = await page.evaluate('window.__SMOKE_RESULT');
await browser.close();

console.log('结果:', JSON.stringify(result));
if (!result.ok) {
  console.error('冒烟测试 FAIL');
  process.exit(1);
}
if (result.size < 10000) {
  console.error('PDF 体积异常小，转换可能不完整');
  process.exit(1);
}
console.log('冒烟测试 PASS');
