from playwright.sync_api import sync_playwright
import os; out="/tmp/s4"; os.makedirs(out,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    for w,h,n,mob in [(1440,900,"d",False),(390,844,"m",True)]:
        ctx=b.new_context(viewport={"width":w,"height":h},is_mobile=mob,has_touch=mob); pg=ctx.new_page(); errs=[]
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.goto("http://localhost:8766/"); pg.wait_for_timeout(1200)
        H=pg.evaluate("document.documentElement.scrollHeight"); sw=pg.evaluate("document.documentElement.scrollWidth")
        print(n,"height",H,"width",sw)
        for sid in ["cover","problem","approach","build","demo","results","competition","impact","p-priv","sources"]:
            pg.evaluate(f"document.getElementById('{sid}').scrollIntoView({{behavior:'instant'}})"); pg.wait_for_timeout(300)
            print(n,sid,pg.evaluate("[document.querySelector('#tabs .on')?.textContent, document.body.className]"))
            pg.screenshot(path=f"{out}/{n}_{sid}.png")
        print("errors",errs); ctx.close()
    b.close()
