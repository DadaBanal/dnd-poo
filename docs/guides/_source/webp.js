const { chromium } = require('playwright'); const fs = require('fs');
const [dir, out, width, q] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); let tot = 0;
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.jpg'))) {
    const src = 'data:image/jpeg;base64,' + fs.readFileSync(dir + '/' + f).toString('base64');
    const d = await p.evaluate(async ([src, W, Q]) => { const i = new Image(); i.src = src; await i.decode(); const w = Math.min(+W, i.naturalWidth), h = Math.round(i.naturalHeight * w / i.naturalWidth);
      const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.imageSmoothingQuality = 'high'; x.drawImage(i, 0, 0, w, h); return c.toDataURL('image/webp', +Q); }, [src, width, q]);
    const buf = Buffer.from(d.split(',')[1], 'base64'); fs.writeFileSync(out + '/' + f.replace('.jpg', '.webp'), buf); tot += buf.length;
  }
  console.log(width, q, 'total KB', Math.round(tot / 1024)); await b.close();
})();
