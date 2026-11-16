// Bayiye açık her modelde bayinin her değişikliği gerçek tıklamayla yapılır; ekranın sunucuya göndereceği değerler yazılır.
const { chromium } = require('playwright');
const kodlar = process.argv[2].split(',');
const sorgu = () => { const f = document.getElementById('studyo'); const v = new URLSearchParams();
  new FormData(f).forEach((d, a) => { if (!['adet','istenen_tarih','notlar','csrfmiddlewaretoken'].includes(a)) v.set(a, d); }); return v.toString(); };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1300, height: 1000 } });
  await p.route('**/*.jpg*', r => r.abort()); await p.route('**/malzeme/**', r => r.abort()); await p.route('**/desen-onizleme/**', r => r.abort());
  await p.goto('http://127.0.0.1:8765/giris/');
  await p.fill('input[name=username]', 'bayitest'); await p.fill('input[name=password]', 'Deneme.1234');
  await p.click('form.dikey button[type=submit]'); await p.waitForLoadState('networkidle');
  const ac = async (kod) => { await p.goto('http://127.0.0.1:8765/tasarim/parcali/?hazir=' + kod, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(700); };
  const yaz = async (kod, islem, secilen) => { await p.waitForTimeout(700); console.log(JSON.stringify({ kod, islem, secilen, q: await p.evaluate(sorgu) })); };
  const tikla = async (kap, secici) => {  // kap içinde görünür, seçili olmayan ilk seçeneğe gerçek tıklama
    // "Tümünü göster" düğmesi ızgaranın hemen ardında (içinde değil): kısaltılmış listede kartela renkleri gizli kalır
    const t = p.locator(`${kap} + button.tumu, ${kap} button.tumu`);
    for (let i = 0; i < await t.count(); i++) if (await t.nth(i).isVisible() && (await t.nth(i).textContent()).includes('Tümünü')) await t.nth(i).click();
    const e = p.locator(`${kap} ${secici}:visible:not(:has(input:checked)):not(:has(input:disabled))`).first();
    if (!(await e.count())) { console.log(JSON.stringify({ kod: simdiki, islem: 'SECENEK_YOK', kap })); return null; }
    const v = await e.locator('input').getAttribute('value'); await e.click(); return v; };
  let simdiki = '';
  for (const kod of kodlar) {
    simdiki = kod;
    await ac(kod); await yaz(kod, 'ilk', null);
    const n = parseInt(await p.inputValue('#halka_sayisi'), 10) || 0;
    const madalyon = await p.evaluate(() => (document.querySelector('[name=madalyon]:checked') || {}).value);
    for (let i = 1; i <= n; i++) {
      await ac(kod); await p.click('.adimlar button[data-git="2"]');
      let s = await tikla(`.halka[data-halka="${i}"] .mal-izgara`, 'label.mal'); if (s) await yaz(kod, `h${i}_malzeme`, s);
      const tur = await p.evaluate((i) => (document.querySelector(`[name=h${i}_tur]:checked`) || {}).value, i);
      if (tur === 'desenli') { await ac(kod); await p.click('.adimlar button[data-git="2"]');
        s = await tikla(`.halka[data-halka="${i}"] .desen-izgara`, 'label.desen:not(:has(input[value=""]))'); if (s) await yaz(kod, `h${i}_desen`, s); }
      if (i < n) { await ac(kod); await p.click('.adimlar button[data-git="2"]');
        s = await tikla(`.ara-bant[data-ara="${i}"]`, 'label.secim:not(:has(input[value="0"]))'); if (s) await yaz(kod, `a${i}_gen`, s); }
    }
    await ac(kod); await p.click('.adimlar button[data-git="3"]');
    let s = await tikla('.mal-izgara[data-alan="zemin"]', 'label.mal'); if (s) await yaz(kod, 'zemin', s);
    if (madalyon && madalyon !== 'yok') { await ac(kod); await p.click('.adimlar button[data-git="3"]');
      s = await tikla('.mal-izgara[data-alan="madalyon_malzeme"]', 'label.mal'); if (s) await yaz(kod, 'madalyon_malzeme', s); }
    await ac(kod); await p.click('.adimlar button[data-git="4"]');
    s = await tikla('.adim[data-adim="4"]', 'label.kenar-renk'); if (s) await yaz(kod, 'kenar_renk', s);
  }
  await b.close();
})();
