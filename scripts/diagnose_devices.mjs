// Local device access only; no audio or images are saved or sent to a provider.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../apps/web/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const browser = await chromium.launch({ channel: 'chromium', headless: true });
try {
  const context = await browser.newContext({ permissions: ['microphone', 'camera'], viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto('http://localhost:5173');
  const result = await page.evaluate(async () => {
    const output = { secure: isSecureContext, mediaAPI: !!navigator.mediaDevices };
    if (!navigator.mediaDevices) return output;
    const devices = await navigator.mediaDevices.enumerateDevices();
    output.inputs = { audio: devices.filter(d => d.kind === 'audioinput').length, video: devices.filter(d => d.kind === 'videoinput').length };
    for (const kind of ['audio', 'video']) {
      let expired = false, timer, stream;
      try {
        const pending = navigator.mediaDevices.getUserMedia({ [kind]: true });
        pending.then(s => { if (expired) s.getTracks().forEach(t => t.stop()); }, () => {});
        stream = await Promise.race([pending, new Promise((_, reject) => { timer = setTimeout(() => { expired = true; reject(new Error('DEVICE_TIMEOUT')); }, 10000); })]);
        output[kind] = { status: 'OK', track: stream.getTracks()[0].readyState };
      } catch (e) { output[kind] = { status: e.name, code: e.message === 'DEVICE_TIMEOUT' ? e.message : undefined }; }
      finally { clearTimeout(timer); stream?.getTracks().forEach(t => t.stop()); }
    }
    return output;
  });
  // Exercise the actual UI capture path, with uploads blocked for this device check.
  await page.route('**/api/v1/audio/transcriptions', route => route.abort());
  await page.route('**/api/v1/camera/feedback', route => route.abort());
  await page.getByRole('button', { name: '小伴语音助手' }).click();
  try {
    await page.locator('.voice-input button.recording').waitFor({ state: 'attached', timeout: 10000 });
    result.microphoneUI = 'RECORDING';
    await page.waitForFunction(() => Number(document.querySelector('.voice-input')?.getAttribute('data-samples')) > 5000, null, { timeout: 5000 });
    await page.waitForTimeout(1500);
    result.pcm = await page.locator('.voice-input').evaluate(el => ({ engine: el.getAttribute('data-engine'), samples: Number(el.getAttribute('data-samples')), peakRms: Number(el.getAttribute('data-peak')) }));
  } catch { result.microphoneUI = await page.locator('.voice-status').textContent(); }
  await page.goto('http://localhost:5173/practice');
  await page.getByRole('button', { name: '开始视频陪练', exact: true }).waitFor();
  result.idleCamera = await page.locator('video[aria-label="摄像头预览"]').evaluate(v => v.srcObject === null);
  await page.screenshot({ path: fileURLToPath(new URL('../artifacts/practice-idle-mobile-2026-11-19.png', import.meta.url)), fullPage: true });
  await page.getByRole('button', { name: '开始视频陪练', exact: true }).click();
  try {
    await page.waitForFunction(() => document.querySelector('video[aria-label="摄像头预览"]')?.videoWidth > 0, null, { timeout: 12000 });
    result.cameraUI = 'LIVE_PREVIEW';
  } catch { result.cameraUI = await page.locator('.camera-error').textContent().catch(() => 'NO_PREVIEW'); }
  await page.getByRole('button', { name: '结束陪练', exact: true }).click().catch(() => {});
  await page.goto('http://localhost:5173/share');
  await page.getByRole('button', { name: '我的', exact: true }).click();
  await page.locator('.my-work-card').first().waitFor();
  result.sampleUploads = await page.locator('.my-work-card').filter({ hasText: '（示例）' }).count();
  await page.waitForFunction(() => [...document.querySelectorAll('.my-work-card img')].length >= 3);
  await page.screenshot({ path: fileURLToPath(new URL('../artifacts/my-samples-2026-11-19.png', import.meta.url)), fullPage: true });
  fs.writeFileSync(new URL('../artifacts/device-diagnosis-mobile-2026-11-19.json', import.meta.url), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
} finally { await browser.close(); }
