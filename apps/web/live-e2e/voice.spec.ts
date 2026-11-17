import {test,expect} from '@playwright/test';
test('真实ASR模型数据库导航和TTS（自制语音模拟麦克风）',async({page,request})=>{
 const health=await request.get('/health/ready');expect((await health.json()).provider).toBe('deepseek');
 const auth=await request.post('/api/v1/auth/register',{data:{username:'live_browser_'+Date.now(),password:'synthetic-test-'+Date.now()+'-123'}});expect(auth.ok()).toBeTruthy();const {access_token}=await auth.json();
 await page.addInitScript(t=>sessionStorage.setItem('xiaoban-token',t),access_token);
 const audioResponses: number[]=[];page.on('response',r=>{if(r.url().endsWith('/audio/speech'))audioResponses.push(r.status())});
 await page.goto('/');await page.getByRole('button',{name:'找小伴帮忙'}).click();await page.getByRole('button',{name:'开始语音对话'}).click();
 await expect(page.locator('[data-course-ready="repotting-basics"]')).toBeVisible();
 await expect(page.locator('.reply')).toContainText('课程已经打开');
 await expect.poll(()=>audioResponses.includes(200),{timeout:45000}).toBeTruthy();
 await page.getByRole('button',{name:'结束语音对话'}).click();await page.getByRole('button',{name:'停止播报'}).click();
 await page.screenshot({path:'../../docs/evals/real-voice-navigation.png',fullPage:true});
 const library=await request.get('/api/v1/library',{headers:{Authorization:'Bearer '+access_token}});expect((await library.json()).items).toHaveLength(1);
 await request.delete('/api/v1/me/data',{headers:{Authorization:'Bearer '+access_token},data:{confirmation:'DELETE_MY_DATA'}});
});
