// Record the real local UI after scripts/demo.sh; no mocked responses or fabricated screens.
// node scripts/record-demo.mjs /tmp/quickstart-evidence.json /tmp/dl-recording
import { chromium } from '../web/node_modules/playwright/index.mjs';
import { readFile, mkdir } from 'node:fs/promises';
const evidence = JSON.parse(await readFile(process.argv[2], 'utf8'));
const output = process.argv[3] || '/tmp/dl-recording';
const base = process.env.DL_DEMO_WEB_URL || 'http://localhost:3100';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({headless: true});
try {
  const context = await browser.newContext({viewport:{width:1280,height:900},
    recordVideo:{dir:output,size:{width:1280,height:900}}});
  const page = await context.newPage();
  await page.addInitScript(()=>localStorage.setItem('decision-layer.locale','en'));
  const scenes = [
    ['january', `/runs/${evidence.january.id}`, 'Home has the highest revenue', 12000],
    ['recipe', `/recipes/${evidence.recipe.name}`, 'query.drilldown', 8000],
    ['february', `/runs/${evidence.february.id}`, 'Grocery has the highest revenue', 12000],
    ['march', `/runs/${evidence.march.id}`, 'March', 12000],
  ];
  for (const [name,path,expected,duration] of scenes) {
    await page.goto(base + path);
    if(name==='recipe') await page.locator('input').first().waitFor({state:'visible'});
    else await page.getByText(expected,{exact:false}).first().waitFor({state:'visible'});
    await page.screenshot({path:`${output}/${name}.png`,fullPage:true});
    if (await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('Horizontal overflow');
    await page.waitForTimeout(duration/2);
    await page.evaluate(()=>window.scrollBy({top:650,behavior:'smooth'}));
    await page.waitForTimeout(duration/2);
  }
  const video=page.video();
  await context.close();
  await video.saveAs(`${output}/recipe-replay.webm`);
  console.log(`${output}/recipe-replay.webm`);
} finally { await browser.close(); }
