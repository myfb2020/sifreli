// Bayi gibi: her modelden bir sipariş. Sipariş ver → model → 🎨 Tasarla → birkaç değişiklik (bordür eni, bordür rengi,
// desen, ara bant, zemin, madalyon, kenar) → Siparişi gönder. Her adımdan sonra önizleme resmi kaydedilir.
// Kullanım: NODE_PATH=$(npm root -g) node bayi_siparis_denemesi.js KOD,KOD… CIKTI_KLASORU  (sunucu 127.0.0.1:8765, bayitest)
const { chromium } = require('playwright');
const fs = require('fs');
const kodlar = process.argv[2].split(','); const cikti = process.argv[3];
const ADRES = 'http://127.0.0.1:8765';
(async () => {
  fs.mkdirSync(cikti, { recursive: true });
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1300, height: 1000 } });
  const sorunlar = [];
  p.on('pageerror', (e) => sorunlar.push('JS hatası: ' + e.message));
  p.on('response', (r) => { if (r.status() >= 400) sorunlar.push(`HTTP ${r.status()} ${r.url().slice(0, 120)}`); });
  await p.goto(ADRES + '/giris/');
  await p.fill('input[name=username]', 'bayitest'); await p.fill('input[name=password]', 'Deneme.1234');
  await p.click('form.dikey button[type=submit]'); await p.waitForLoadState('networkidle');
  const kaydet = async (kod, sira, ad) => {  // önizleme resmini (sunucunun verdiği gibi) kaydet
    await p.waitForTimeout(600);
    await p.waitForFunction(() => { const r = document.getElementById('onizleme'); return r.complete && !r.classList.contains('bekle'); }, null, { timeout: 30000 }).catch(() => {});
    const src = await p.evaluate(() => document.getElementById('onizleme').src);
    const y = await p.request.get(src);
    fs.writeFileSync(`${cikti}/${kod}_${sira}.jpg`, await y.body());
    const q = await p.evaluate(() => { const f = document.getElementById('studyo'); const v = new URLSearchParams();
      new FormData(f).forEach((d, a) => { if (!['adet','istenen_tarih','notlar','csrfmiddlewaretoken'].includes(a)) v.set(a, d); }); return v.toString(); });
    return { sira, ad, q, foto: src.includes('/medya/') || src.includes('katalog') };
  };
  const tumunuAc = async (kap) => { const t = p.locator(`${kap} + button.tumu`);
    for (let i = 0; i < await t.count(); i++) if ((await t.nth(i).textContent()).includes('Tümünü')) await t.nth(i).click(); };
  const sec = async (kap, secici, n = 0) => {  // görünür, seçili olmayan n. seçeneğe tıkla
    await tumunuAc(kap);
    const e = p.locator(`${kap} ${secici}:visible:not(:has(input:checked)):not(:has(input:disabled))`);
    const say = await e.count(); if (!say) return null;
    const h = e.nth(n % say); const v = await h.locator('input').getAttribute('value'); await h.click(); return v; };
  const adim = async (n) => { await p.click(`.adimlar button[data-git="${n}"]`); await p.waitForTimeout(200); };
  for (const [no, kod] of kodlar.entries()) {
    const kayit = { kod, adimlar: [], sorunlar: [] }; sorunlar.length = 0;
    try {
      await p.goto(ADRES + '/bayi/siparis/?tur=suni', { waitUntil: 'domcontentloaded' });
      const seri = await p.evaluate((kod) => document.querySelector(`.model-kart[data-kod="${kod}"]`).closest('[data-seri-izgara]').dataset.seriIzgara, kod);
      await p.click(`.seri-sekme button[data-seri="${seri}"]`);  // model başka seri sekmesindeyse önce o sekme
      await p.click(`.model-kart[data-kod="${kod}"]`);
      const link = p.locator('#secilen-model a.btn');
      if (!(await link.count())) { kayit.sorunlar.push('🎨 Tasarla bağlantısı yok'); fs.appendFileSync(`${cikti}/sonuc.jsonl`, JSON.stringify(kayit) + '\n'); continue; }
      await link.click(); await p.waitForLoadState('domcontentloaded'); await p.waitForTimeout(800);
      kayit.adimlar.push(await kaydet(kod, 0, 'açılış'));
      const n = parseInt(await p.inputValue('#halka_sayisi'), 10) || 0;
      let s = 1;
      await adim(2);
      if (n) {  // 1) bir bordürün enini değiştir (+4 cm)
        const i = (no % n) + 1; const a = p.locator(`#h${i}_gen`); const eski = parseFloat(await a.inputValue());
        await a.fill(String(eski + 4)); await a.dispatchEvent('change');
        kayit.adimlar.push(await kaydet(kod, s++, `${i}. bordür eni ${eski}→${eski + 4}`));
        // 2) başka bir bordürün rengi
        const j = ((no + 1) % n) + 1; const r = await sec(`.halka[data-halka="${j}"] .mal-izgara`, 'label.mal', no);
        if (r) kayit.adimlar.push(await kaydet(kod, s++, `${j}. bordür rengi → ${r}`));
        // 3) desenli bordür varsa her üç modelde bir desen değişsin
        for (let k = 1; k <= n; k++) {
          if (no % 3 === 0 && (await p.evaluate((k) => (document.querySelector(`[name=h${k}_tur]:checked`) || {}).value, k)) === 'desenli') {
            const d = await sec(`.halka[data-halka="${k}"] .desen-izgara`, 'label.desen:not(:has(input[value=""]))', no);
            if (d) kayit.adimlar.push(await kaydet(kod, s++, `${k}. bordür deseni → ${d}`)); break; }
        }
        // 4) ara bant (iki bordür varsa)
        if (n > 1) { const aa = await sec(`.ara-bant[data-ara="1"]`, 'label.secim:not(:has(input[value="0"]))', no);
          if (aa) kayit.adimlar.push(await kaydet(kod, s++, `1-2 ara bant → ${aa} cm`)); }
      }
      await adim(3);
      if (no % 2 === 0) { const z = await sec('.mal-izgara[data-alan="zemin"]', 'label.mal', no);
        if (z) kayit.adimlar.push(await kaydet(kod, s++, `zemin → ${z}`)); }
      if ((await p.evaluate(() => (document.querySelector('[name=madalyon]:checked') || {}).value)) !== 'yok' && await p.locator('.mal-izgara[data-alan="madalyon_malzeme"]').isVisible()) {
        const m = await sec('.mal-izgara[data-alan="madalyon_malzeme"]', 'label.mal', no);
        if (m) kayit.adimlar.push(await kaydet(kod, s++, `madalyon → ${m}`)); }
      await adim(4);
      const k = await sec('.adim[data-adim="4"]', 'label.kenar-renk', no);
      if (k) kayit.adimlar.push(await kaydet(kod, s++, `kenar → ${k}`));
      await adim(5);
      await p.fill('[name=adet]', '1'); await p.fill('[name=notlar]', `deneme ${kod}`);
      await Promise.all([p.waitForNavigation({ timeout: 60000 }), p.click('#studyo button[type=submit]')]);
      kayit.gonderim = p.url().endsWith('/bayi/') ? 'gönderildi' : 'GÖNDERİLEMEDİ ' + p.url();
      kayit.mesaj = (await p.locator('.mesaj').allTextContents()).join(' | ').slice(0, 160);
    } catch (e) { kayit.sorunlar.push('Deneme hatası: ' + String(e).slice(0, 200)); }
    kayit.sorunlar.push(...sorunlar);
    fs.appendFileSync(`${cikti}/sonuc.jsonl`, JSON.stringify(kayit) + '\n');
  }
  await b.close();
})();
