import { expect, test, type Page } from "@playwright/test";

const guide={name:"analysis.drilldown",version:"1.0.1",sha256:"a".repeat(64),markdown:"# 항목별 조사\n\n1. **공식 지표**를 확인합니다.\n2. `run_skill_query`로 조회합니다.\n\n<script>window.hacked=true</script>",suggested_methods:[]};
const manifest={name:guide.name,version:guide.version,kind:"query",implementation:"skill",agent_executable:true,description:"한국어 조사",roles:{},parameters:{},outputs:[]};
const source="---\nname: analysis.drilldown\nversion: 1.0.1\ndescription: 한국어 조사\nquery_execution: true\n---\n# 항목별 조사\n";
const pythonCode="def calculate(data):\n    return data * 2\n";
test.beforeEach(async({page}) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale","ko"));
  await page.route("**/api/me",route => route.fulfill({json:{subject:"alice"}}));
});
function fixture(page:Page, python=false, permission={edit:true,publish:true}) {
  const name=python ? "stats.series_diagnostics" : guide.name;
  const initial=python ? pythonCode : source;
  let current=guide.version, draft:any=null, saves:any[]=[], checked=0;
  const asset=()=>({version:current,implementation:python ? "python":"skill",content:initial,
    code:python ? {available:true,version:current,origin:"installed",authoring_content:pythonCode,
      files:[{name:"dl_method_assets.a_"+"c".repeat(64),content:"# unrelated platform source\n"+pythonCode,sha256:"b".repeat(64)}]}:null,
    permissions:permission,draft,history:[]});
  const ready=Promise.all([
    page.route(`**/api/methods/${name}`,r=>r.fulfill({json:{...manifest,name,version:current,implementation:python ? "python":"skill"}})),
    page.route(`**/api/methods/${name}/guide`,r=>r.fulfill({json:{...guide,version:current}})),
    page.route(`**/api/methods/${name}/source`,r=>r.fulfill({json:asset()})),
    page.route(`**/api/methods/${name}/draft`,r=>{
      const request=r.request().postDataJSON();saves.push(request);
      draft={revision:`saved-${saves.length}`,version:request.version,content:request.content,validation:null};
      return r.fulfill({json:draft});
    }),
    page.route(`**/api/methods/${name}/draft:check`,r=>{
      checked++;expect(r.request().postDataJSON().revision).toBe(draft.revision);
      draft={...draft,validation:{status:"pass"}};return r.fulfill({json:draft});
    }),
    page.route(`**/api/methods/${name}/draft:publish`,r=>{
      expect(r.request().postDataJSON()).toEqual({revision:draft.revision,reviewed:true});
      current=draft.version;draft=null;return r.fulfill({json:{version:current}});
    }),
  ]);
  return {ready,name,asset,saves,checked:()=>checked,setDraft:(value:any)=>{draft=value;}};
}
async function openEditor(page:Page, python=false) {
  await page.getByRole("tab",{name:python ? "Python 코드" : "분석 지침",exact:true}).click();
  await page.getByRole("button",{name:python ? "Python 편집":"Skill.md 편집",exact:true}).click();
  const editor=page.getByRole("textbox",{name:python ? "Python 작성 코드":"Skill Markdown 원본",exact:true});
  await expect(editor).toBeVisible();return editor;
}

test("Skill editing opens on demand, previews Markdown, saves on check and publishes",async({page},info)=>{
  const f=fixture(page);await f.ready;await page.goto(`/methods/${f.name}`);
  await expect(page.getByRole("button",{name:"Skill.md 편집",exact:true})).not.toBeVisible();
  await page.getByRole("tab",{name:"분석 지침",exact:true}).click();
  await expect(page.getByRole("heading",{name:"항목별 조사",exact:true})).toBeVisible();
  await expect(page.getByText("공식 지표",{exact:true})).toHaveCSS("font-weight","700");
  expect(await page.evaluate(()=>Boolean((window as any).hacked))).toBe(false);
  const editor=await openEditor(page);
  await editor.fill(source.replace("1.0.1","1.0.2")+"\n## 새 조사 지침\n기간을 확인합니다.\n");
  await page.getByRole("tab",{name:"미리보기",exact:true}).click();
  await expect(page.getByRole("heading",{name:"새 조사 지침",exact:true})).toBeVisible();
  await expect(page.getByText("name: analysis.drilldown",{exact:false})).not.toBeVisible();
  await page.getByRole("tab",{name:"변경 비교",exact:true}).click();
  await expect(page.getByRole("heading",{name:"게시 v1.0.1",exact:true})).toBeVisible();
  await page.getByRole("tab",{name:"편집",exact:true}).click();
  await page.getByRole("button",{name:"구문·등록 검사",exact:true}).click();
  expect(f.saves).toHaveLength(1);expect(f.saves[0].content).toContain("새 조사 지침");
  await expect(page.getByText("구문·등록 검사를 통과했습니다. 실제 데이터·분석 품질은 검사하지 않았습니다.")).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button",{name:"v1.0.2 게시",exact:true}).click();
  await expect(page.getByText("analysis.drilldown / v1.0.2")).toBeVisible();
  await page.screenshot({path:info.outputPath("skill-published.png"),fullPage:true});
});

test("Python uses a code editor, supports keyboard save, preserves drafts and invalidates checks after edits",async({page},info)=>{
  const f=fixture(page,true);await f.ready;await page.goto(`/methods/${f.name}`);
  await page.getByRole("tab",{name:"Python 코드",exact:true}).click();
  await expect(page.locator(".hljs-keyword").first()).toBeVisible();
  await expect(page.getByText("# unrelated platform source",{exact:false})).not.toBeVisible();
  const editor=await openEditor(page,true);
  await expect(page.getByRole("button",{name:"구문·등록 검사",exact:true})).toBeDisabled();
  await editor.fill(pythonCode+"# edited in browser\n");
  await editor.press("ControlOrMeta+s");
  await expect(page.getByText("서버에 저장된 초안",{exact:true})).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button",{name:"구문·등록 검사",exact:true}).click();
  await expect(page.getByRole("button",{name:"v1.0.2 게시",exact:true})).toBeEnabled();
  await editor.fill(pythonCode+"# second edit\n");
  await expect(page.getByRole("button",{name:"v1.0.2 게시",exact:true})).toBeDisabled();
  await expect(page.getByRole("checkbox")).not.toBeChecked();
  await page.getByRole("button",{name:"초안 저장",exact:true}).click();
  await expect(page.getByText("서버에 저장된 초안",{exact:true})).toBeVisible();
  await page.reload();
  await page.getByRole("tab",{name:"Python 코드",exact:true}).click();
  await page.getByRole("button",{name:"편집 이어서",exact:true}).click();
  await expect(page.getByRole("textbox",{name:"Python 작성 코드",exact:true})).toContainText("second edit");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("python-editor.png"),fullPage:true});
});

test("unsaved edits survive read mode and navigation can be cancelled or saved",async({page})=>{
  const f=fixture(page);await f.ready;await page.route("**/api/methods",r=>r.fulfill({json:[]}));await page.goto(`/methods/${f.name}`);
  const editor=await openEditor(page);await editor.fill(source.replace("1.0.1","1.0.2")+"\n내가 작성한 변경\n");
  await page.getByRole("button",{name:"읽기로 돌아가기",exact:true}).click();
  await expect(page.getByText("작성 중인 내용은 이 화면에 유지됩니다. 편집을 이어서 초안으로 저장하세요.")).toBeVisible();
  await page.getByRole("button",{name:"편집 이어서",exact:true}).click();
  await expect(page.getByRole("textbox",{name:"Skill Markdown 원본",exact:true})).toContainText("내가 작성한 변경");
  await page.getByRole("link",{name:"분석 방법",exact:true}).last().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button",{name:"계속 편집",exact:true}).click();
  await expect(page).toHaveURL(`/methods/${f.name}`);
  await page.getByRole("link",{name:"분석 방법",exact:true}).last().click();
  await page.getByRole("button",{name:"저장하고 이동",exact:true}).click();
  await expect(page).toHaveURL("/methods");expect(f.saves[0].content).toContain("내가 작성한 변경");
});

test("typing during a save remains unsaved rather than being lost when the response arrives",async({page})=>{
  const f=fixture(page,true);await f.ready;
  let release!:()=>void;const wait=new Promise<void>(resolve=>release=resolve);
  await page.route(`**/api/methods/${f.name}/draft`,async route=>{
    const request=route.request().postDataJSON();await wait;
    await route.fulfill({json:{revision:"late-save",version:request.version,content:request.content,validation:null}});
  });
  await page.goto(`/methods/${f.name}`);const editor=await openEditor(page,true);
  await editor.fill(pythonCode+"# first\n");
  const request=page.waitForRequest(`**/api/methods/${f.name}/draft`);
  await page.getByRole("button",{name:"초안 저장",exact:true}).click();await request;
  await editor.fill(pythonCode+"# second while saving\n");release();
  await expect(page.getByText("저장하지 않은 변경",{exact:true})).toBeVisible();
  await expect(editor).toContainText("second while saving");
  await expect(page.getByRole("button",{name:"초안 저장",exact:true})).toBeEnabled();
});

test("a conflicting draft preserves local text and requires an explicit comparison before retry",async({page})=>{
  const f=fixture(page);await f.ready;let conflict=true;
  await page.route(`**/api/methods/${f.name}/draft`,route=>{
    const request=route.request().postDataJSON();
    if(conflict)return route.fulfill({status:409,json:{detail:"This asset or draft changed. Reload before saving."}});
    expect(request.revision).toBe("other-editor");expect(request.content).toContain("내 변경");
    return route.fulfill({json:{revision:"resolved",version:request.version,content:request.content}});
  });
  await page.goto(`/methods/${f.name}`);const editor=await openEditor(page);
  await editor.fill(source.replace("1.0.1","1.0.2")+"\n내 변경\n");
  await page.getByRole("button",{name:"초안 저장",exact:true}).click();
  await expect(page.getByRole("alert").filter({hasText:"작성 내용은 유지됩니다"})).toBeVisible();
  await expect(editor).toContainText("내 변경");
  f.setDraft({revision:"other-editor",version:"1.0.2",content:source+"\n다른 작성자의 변경\n"});
  await page.getByRole("button",{name:"서버 상태 확인",exact:true}).click();
  await expect(page.getByLabel("서버 초안과 내 변경 비교")).toContainText("다른 작성자의 변경");
  await page.getByRole("button",{name:"내 변경을 유지하고 기준 갱신",exact:true}).click();conflict=false;
  await page.getByRole("button",{name:"초안 저장",exact:true}).click();
  await expect(page.getByText("서버에 저장된 초안",{exact:true})).toBeVisible();
});

test("read-only users can inspect content but do not receive an editor",async({page})=>{
  const f=fixture(page,true,{edit:false,publish:false});await f.ready;await page.goto(`/methods/${f.name}`);
  await page.getByRole("tab",{name:"Python 코드",exact:true}).click();
  await expect(page.getByText("읽기 전용입니다.",{exact:false})).toBeVisible();
  await expect(page.getByRole("button",{name:"Python 편집",exact:true})).toHaveCount(0);
  await expect(page.locator(".hljs-keyword").first()).toBeVisible();
});

test("language refresh keeps an in-progress edit and tab switching preserves its undo state",async({page})=>{
  const f=fixture(page,true);await f.ready;await page.goto(`/methods/${f.name}`);
  const editor=await openEditor(page,true);await editor.fill(pythonCode+"# keep across refresh\n");
  await page.getByRole("tab",{name:"개요와 입력",exact:true}).click();
  await page.getByRole("tab",{name:"Python 코드",exact:true}).click();
  await expect(editor).toContainText("keep across refresh");
  await page.getByLabel("language").selectOption("en");
  await expect(editor).toContainText("keep across refresh");
  await page.getByRole("tab",{name:"미리보기",exact:true}).click();
  await page.getByRole("tab",{name:"편집",exact:true}).click();
  await expect(editor).toContainText("keep across refresh");
  await expect(page.getByText("저장하지 않은 변경",{exact:true})).toBeVisible();
});

test("failed registration leaves source editable and cannot enable publication",async({page})=>{
  const f=fixture(page);await f.ready;
  await page.route(`**/api/methods/${f.name}/draft:check`,r=>r.fulfill({json:{
    revision:"saved-1",version:"1.0.2",content:source.replace("1.0.1","1.0.2"),
    validation:{status:"fail",message:"Skill name/version must match publication fields"}}}));
  await page.goto(`/methods/${f.name}`);const editor=await openEditor(page);
  await page.getByRole("button",{name:"구문·등록 검사",exact:true}).click();
  await expect(page.getByText("Skill name/version must match publication fields",{exact:true})).toBeVisible();
  await expect(editor).toBeVisible();
  await expect(page.getByRole("button",{name:"v1.0.2 게시",exact:true})).toBeDisabled();
});

test("Python formatting is explicit, reversible and requires a new review without saving",async({page},info)=>{
  const f=fixture(page,true);await f.ready;
  const messy="def calculate(data):\n return data*3\n";
  const formatted="def calculate(data):\n    return data * 3\n";
  await page.route(`**/api/methods/${f.name}/source:format`,route=>{
    expect(route.request().postDataJSON()).toEqual({content:messy});
    return route.fulfill({json:{content:formatted,changed:true}});
  });
  await page.goto(`/methods/${f.name}`);const editor=await openEditor(page,true);
  await editor.fill(messy);await page.getByRole("checkbox").check();
  await page.getByRole("button",{name:"코드 정리",exact:true}).click();
  await expect(editor).toHaveText(formatted);
  await expect(page.getByRole("checkbox")).not.toBeChecked();
  expect(f.saves).toHaveLength(0);expect(f.checked()).toBe(0);
  await page.getByRole("tab",{name:"변경 비교",exact:true}).click();
  const diff=page.getByRole("table",{name:"추가·삭제 코드",exact:true});
  await expect(diff).toContainText("-    return data * 2");
  await expect(diff).toContainText("+    return data * 3");
  await expect(page.getByText("+1줄 추가",{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath("python-review-diff.png"),fullPage:true});
  await page.getByRole("tab",{name:"편집",exact:true}).click();
  await page.getByRole("button",{name:"정리 되돌리기",exact:true}).click();
  await expect(editor).toHaveText(messy);
  await editor.press("Alt+Shift+f");
  await expect(editor).toHaveText(formatted);
});

test("invalid Python formatting preserves the editor text and leaves saved revisions untouched",async({page})=>{
  const f=fixture(page,true);await f.ready;
  await page.route(`**/api/methods/${f.name}/source:format`,route=>route.fulfill({status:400,json:{error:{code:"METHOD_ASSET_ERROR",message:"Python syntax error at line 1"}}}));
  await page.goto(`/methods/${f.name}`);const editor=await openEditor(page,true);
  await editor.fill("def broken(");
  await page.getByRole("button",{name:"코드 정리",exact:true}).click();
  await expect(page.getByRole("alert").filter({hasText:"Python syntax error"})).toBeVisible();
  await expect(editor).toHaveText("def broken(");
  expect(f.saves).toHaveLength(0);
});
