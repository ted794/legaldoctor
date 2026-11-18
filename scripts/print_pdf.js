// 가상 사업소개서 HTML을 PDF로 인쇄: node scripts/print_pdf.js <HTML 폴더> <PDF 폴더>
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
(async()=>{const [src,dst]=process.argv.slice(2);fs.mkdirSync(dst,{recursive:true});const b=await chromium.launch();const p=await b.newPage();
for(const f of fs.readdirSync(src).filter(x=>x.endsWith('.html'))){await p.goto('file://'+path.resolve(src,f));await p.waitForTimeout(600);
await p.pdf({path:path.join(dst,f.replace('.html','.pdf')),preferCSSPageSize:true,printBackground:true});console.log(f)}
await b.close()})();
