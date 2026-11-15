"""Standalone local-only Persian viewer for UNVERIFIED corpus snapshots.

No network calls, no API, no deployment and no automatic publication.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .corpus import initialize_corpus
from .taxonomy import CATEGORIES

MAX_PREVIEW_DOCS = 5000
MAX_PREVIEW_JSON_BYTES = 20 * 1024 * 1024

HTML = r'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; form-action 'none'">
<title>آرشیو پژوهشی قوانین — تأییدنشده</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:14px/1.9 Tahoma,"Segoe UI",sans-serif;background:#f5f7fb;color:#293c50}
header{background:#132c3d;color:#f5fbff;padding:22px 28px}
header h1{font-size:23px;margin:0}header p{margin:3px 0;color:#c3d5df}
main{max-width:1500px;margin:0 auto;padding:24px}
.warn{padding:16px;border:1px solid #e6bf75;border-radius:14px;background:#fff3d8;color:#785420;font-weight:bold}
.toolbar{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;margin:20px 0}
input,select{padding:12px;border:1px solid #d1dee6;background:#fff;border-radius:10px;font:inherit;width:100%}
.layout{display:grid;grid-template-columns:minmax(245px,1fr) minmax(0,2fr);gap:18px}
.panel{background:#fff;padding:20px;border:1px solid #e0e8ee;border-radius:15px;min-height:350px}
h2{margin:0 0 15px;font-size:18px}
.b{background:#f8fbfd;border:1px solid #dfe8ec;border-radius:9px;padding:13px;display:block;width:100%;text-align:right;cursor:pointer;margin:8px 0;color:#28445b;font:inherit}
.b.selected,.b:hover{border-color:#0d9187;background:#f0faf9}
.title{font-weight:bold}
.meta{font-size:12px;color:#718395;line-height:1.9}
.article{border-bottom:1px solid #e5ebee;padding:14px 0}
.article p{white-space:pre-wrap;margin:7px 0;color:#354c5d;overflow-wrap:anywhere}
.article strong{color:#0b6963}
.empty{color:#7f8b98;padding:17px 0}
small{color:#798994}
footer{text-align:center;color:#81909b;padding:30px}
@media(max-width:780px){.toolbar,.layout{grid-template-columns:1fr}main{padding:14px}}
</style>
</head>
<body>
<header><h1>آرشیو مستقل پژوهش قوانین و مقررات</h1>
<p>نمایش آفلاین اسناد، دسته‌بندی موضوعی و متن مواد — بدون اتصال به سرویس خارجی</p></header>
<main>
<div class="warn">⚠ تمامی این اسناد تأییدنشده هستند. طبقه‌بندی، نام منبع و پیوندهای سند، ادعاهای ورودی پژوهش‌اند و اثبات اصالت یا اعتبار حقوقی نیستند. از این خروجی برای استناد قضایی استفاده نکنید.</div>
<div class="toolbar">
<input id="search" aria-label="جست‌وجو" placeholder="جست‌وجوی عنوان، متن یا شماره ماده...">
<select id="category" aria-label="موضوع"><option value="">همه موضوعات</option></select>
<select id="kind" aria-label="نوع سند"><option value="">همه انواع سند</option></select>
</div>
<div class="layout">
<section class="panel"><h2>اسناد <small id="count"></small></h2><div id="docs"></div></section>
<section class="panel"><h2 id="heading">متن سند</h2><div id="details" class="empty">یک سند را برای مشاهده مواد انتخاب کنید.</div></section>
</div>
<footer>فقط برای پژوهش داخلی، نگهداری روی رایانه شخصی و بازبینی منبع. هیچ داده‌ای ارسال نمی‌شود.</footer>
</main>
<script>
const DATA=__DATA_JSON__;
const LABELS=__LABELS_JSON__;
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=String(text);if(cls)n.className=cls;return n;};
const norm=v=>String(v||"").replace(/ي/g,"ی").replace(/ك/g,"ک").replace(/[۰-۹]/g,ch=>String(ch.charCodeAt(0)-1776)).toLowerCase();
const categorySelect=$("category"),kindSelect=$("kind");
for(const slug of Object.keys(LABELS)){const o=el("option",LABELS[slug]);o.value=slug;categorySelect.append(o);}
for(const k of [...new Set(DATA.map(x=>x.kind))].sort()){const o=el("option",k);o.value=k;kindSelect.append(o);}
let selected=null;
function filterDocs(){
 const term=norm($("search").value.trim()),cat=categorySelect.value,kind=kindSelect.value;
 const found=DATA.filter(d=>(!cat||d.categories.includes(cat))&&(!kind||d.kind===kind)&&
 (!term||norm(d.title).includes(term)||d.units.some(u=>norm(u.text).includes(term)||norm(u.key)===term)));
 const holder=$("docs");holder.replaceChildren();$("count").textContent="("+found.length+" از "+DATA.length+")";
 if(!found.length)holder.append(el("div","سندی مطابق جست‌وجو پیدا نشد.","empty"));
 for(const d of found.slice(0,150)){
   const b=el("button","", "b"+(selected===d.id?" selected":""));b.type="button";
   b.append(el("div",d.title,"title"));
   b.append(el("div",d.kind+" | "+d.categories.map(x=>LABELS[x]||x).join("، "),"meta"));
   b.onclick=()=>showDoc(d);holder.append(b);
 }
 if(found.length>150)holder.append(el("p","برای مشاهده سایر اسناد جست‌وجو را دقیق‌تر کنید (۱۵۰ مورد نخست نمایش داده شده است).","meta"));
}
function showDoc(d){
 selected=d.id;
 $("heading").textContent=d.title;
 const box=$("details");box.replaceChildren();
 box.append(el("p","نوع سند: "+d.kind+" | مرجع ادعاشده: "+d.issuing_authority,"meta"));
 box.append(el("p","نشانی منبع اعلام‌شده: "+d.source_url,"meta"));
 box.append(el("p","وضعیت: تأییدنشده | نسخه پژوهشی "+d.snapshot_id,"meta"));
 const term=norm($("search").value.trim());
 const matched=d.units.filter(u=>!term||norm(d.title).includes(term)||norm(u.key)===term||norm(u.text).includes(term));
 for(const u of matched.slice(0,100)){
    const article=el("div","","article");
    article.append(el("strong",(u.type==="article"?"ماده ":"بخش ")+u.key));
    article.append(el("p",u.text));
    box.append(article);
 }
 if(matched.length>100)box.append(el("p","نمایش ۱۰۰ واحد نخست از "+matched.length+"؛ برای محدودکردن نتایج جست‌وجو کنید.","meta"));
 filterDocs();
}
$("search").addEventListener("input",filterDocs);
categorySelect.addEventListener("change",filterDocs);
kindSelect.addEventListener("change",filterDocs);
filterDocs();
</script>
</body></html>
'''


def export_corpus_preview(db: sqlite3.Connection, output: str) -> dict:
    """Export latest research copies to a standalone local HTML file.

    Fails safely when the HTML would become too large for a browser prototype.
    The original archived text is not altered or uploaded anywhere.
    """
    initialize_corpus(db)
    rows = db.execute(
        "SELECT s.id AS snapshot_id,s.instrument_id,s.title,s.kind,s.issuing_authority,"
        "s.source_url,(SELECT GROUP_CONCAT(c.category_slug,',') FROM corpus_snapshot_categories c "
        "WHERE c.snapshot_id=s.id) AS category_csv,"
        "u.unit_key,u.unit_type,u.raw_text FROM corpus_snapshots s "
        "JOIN corpus_units u ON u.snapshot_id=s.id "
        "WHERE s.id=(SELECT MAX(id) FROM corpus_snapshots WHERE instrument_id=s.instrument_id) "
        "ORDER BY s.instrument_id,u.unit_key"
    ).fetchall()
    documents: dict[str, dict] = {}
    for row in rows:
        key = row["instrument_id"]
        if key not in documents:
            if len(documents) >= MAX_PREVIEW_DOCS:
                raise ValueError("Too many documents for standalone HTML preview")
            documents[key] = {
                "id": key, "snapshot_id": row["snapshot_id"], "title": row["title"],
                "kind": row["kind"], "issuing_authority": row["issuing_authority"],
                "source_url": row["source_url"],
                "categories": row["category_csv"].split(",") if row["category_csv"] else [],
                "units": [],
            }
        documents[key]["units"].append({
            "key": row["unit_key"], "type": row["unit_type"], "text": row["raw_text"],
        })
    data = json.dumps(list(documents.values()), ensure_ascii=False, separators=(",", ":"))
    labels = json.dumps(CATEGORIES, ensure_ascii=False, separators=(",", ":"))
    for unsafe, safe in (("&", r"\u0026"), ("<", r"\u003c"), (">", r"\u003e"),
                         ("\u2028", r"\u2028"), ("\u2029", r"\u2029")):
        data = data.replace(unsafe, safe)
        labels = labels.replace(unsafe, safe)
    if len(data.encode("utf-8")) > MAX_PREVIEW_JSON_BYTES:
        raise ValueError("Too much legal text for a standalone HTML file; use paginated database tools")
    page = HTML.replace("__DATA_JSON__", data).replace("__LABELS_JSON__", labels)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return {
        "confidence": "UNVERIFIED", "publicly_published": False,
        "offline_only": True, "documents": len(documents),
        "units": sum(len(x["units"]) for x in documents.values()),
        "output": str(path),
    }
