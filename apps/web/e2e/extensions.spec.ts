import {test,expect} from '@playwright/test';
test('四技能、语音意图导航和独立账号投稿',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'进入本地测试'}).click();await page.getByRole('link',{name:'技能广场',exact:true}).click();
 await expect(page.getByRole('heading',{name:'书法入门',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'手机摄影',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'找小伴帮忙'}).click();await page.getByLabel('告诉小伴您想做什么').fill('返回首页');await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page.locator('.reply')).toContainText('已打开首页');
 await page.getByLabel('告诉小伴您想做什么').fill('把书法加入，再打开第一课');await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page.locator('[data-course-ready="calligraphy-lines"]')).toBeVisible();await expect(page.locator('.reply')).toContainText('课程已经打开');
 await page.getByRole('button',{name:'关闭小伴'}).click();await expect(page.locator('video')).toBeVisible();await page.screenshot({path:'../../docs/evals/extended-course.png',fullPage:true});
 await page.getByRole('button',{name:'退出登录'}).click();await page.getByRole('button',{name:'没有账号，去注册'}).click();await page.getByLabel('账号（字母、数字或下划线）').fill('browser_'+Date.now());await page.getByLabel('密码（至少10位）').fill('browser-only-test-123');await page.getByRole('button',{name:'注册并进入'}).click();
 await page.getByRole('link',{name:'我的与隐私',exact:true}).click();await page.getByRole('link',{name:'作品社区与我的投稿'}).click();
 await page.getByLabel('标题',{exact:true}).fill('原创测试学习记录');await page.getByLabel('作品说明',{exact:true}).fill('学习后整理了自己的步骤笔记。');await page.getByLabel('确认内容由我创作',{exact:false}).check();await page.getByRole('button',{name:'确认提交审核'}).click();await expect(page.getByText('已提交审核，尚未公开。')).toBeVisible();
});
