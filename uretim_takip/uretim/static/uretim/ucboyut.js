// 🧊 3B görünüm (2026-11-27): halı kalınlığıyla, parmakla çevrilir / eğilir / yakınlaşır.
// Kullanım: import("/static/uretim/ucboyut.js").then((m) => m.ac({ yuzey: "...", kabartma: "..." }))
// yuzey: halının resmi (sunucu, X-Bilgi başlığında ölçü + şekil), kabartma: gri kabartma haritası.
import * as THREE from "./vendor/three/three.module.min.js";
import { OrbitControls } from "./vendor/three/OrbitControls.js";

let acik = null;

function webglVar() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) { return false; }
}
export const destekli = webglVar();

function kabuk() {
  const kap = document.createElement("div");
  kap.className = "ucb-kap";
  kap.innerHTML = `
    <div class="ucb-ust"><b>🧊 3B görünüm</b><span class="ucb-ipucu">Parmakla çevirin · iki parmakla yakınlaştırın</span>
      <button type="button" class="ucb-kapat" aria-label="Kapat">✕</button></div>
    <div class="ucb-not" hidden></div>
    <div class="ucb-sahne"><div class="ucb-bekle">Hazırlanıyor…</div></div>
    <div class="ucb-alt">
      <button type="button" data-aci="egik">Eğik</button>
      <button type="button" data-aci="ust">Üstten</button>
      <button type="button" data-aci="yan">Yandan</button>
      <button type="button" data-aci="don">⟳ Döndür</button>
    </div>`;
  const stil = document.createElement("style");
  stil.textContent = `
    .ucb-kap { position:fixed; inset:0; z-index:300; background:#1b1714; color:#f3ead7; display:flex; flex-direction:column; }
    .ucb-ust { display:flex; align-items:center; gap:12px; padding:calc(10px + env(safe-area-inset-top)) 14px 10px; }
    .ucb-ust b { font-size:18px; } .ucb-ipucu { color:#b9ad9c; font-size:13px; }
    .ucb-kapat { margin-left:auto; flex:none; width:46px; height:46px; border-radius:50%; border:0; background:#fff; color:#1b1714; font-size:22px; cursor:pointer; }
    .ucb-not { padding:0 14px 8px; color:#d8c9ad; font-size:13px; }
    .ucb-not[hidden] { display:none; }
    .ucb-sahne { position:relative; flex:1; min-height:0; touch-action:none; }
    .ucb-sahne canvas { display:block; width:100%; height:100%; }
    .ucb-bekle { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:17px; color:#d8c9ad; }
    .ucb-alt { display:flex; gap:8px; justify-content:center; flex-wrap:wrap; padding:10px 12px calc(12px + env(safe-area-inset-bottom)); }
    .ucb-alt button { background:#2f2823; color:#f3ead7; border:1px solid #5a4b3c; border-radius:20px; padding:10px 16px; font-size:15px; cursor:pointer; }
    .ucb-alt button.etkin { background:#a8843c; border-color:#a8843c; color:#fff; }
    @media (max-width: 520px) { .ucb-ipucu { display:none; } }`;
  kap.appendChild(stil);
  document.body.appendChild(kap);
  return kap;
}

function halıSekli(b) {
  const s = new THREE.Shape();
  const w = b.en / 2, h = b.boy / 2;
  if (b.sekil === "oval") {
    s.absellipse(0, 0, w, h, 0, Math.PI * 2, false, 0);
    return s;
  }
  const r = Math.min(b.kose || 3, w, h);
  s.moveTo(-w + r, -h);
  s.lineTo(w - r, -h); s.quadraticCurveTo(w, -h, w, -h + r);
  s.lineTo(w, h - r); s.quadraticCurveTo(w, h, w - r, h);
  s.lineTo(-w + r, h); s.quadraticCurveTo(-w, h, -w, h - r);
  s.lineTo(-w, -h + r); s.quadraticCurveTo(-w, -h, -w + r, -h);
  return s;
}

function kenarRengi(resim) {
  // halının kenar rengi (biye): resmin dış şeridinden ortalama
  const c = document.createElement("canvas"); c.width = 64; c.height = 64;
  const x = c.getContext("2d"); x.drawImage(resim, 0, 0, 64, 64);
  const d = x.getImageData(0, 0, 64, 64).data;
  let r = 0, g = 0, b = 0, n = 0;
  for (let y = 0; y < 64; y++) for (let k = 0; k < 64; k++) {
    if (k > 2 && k < 61 && y > 2 && y < 61) continue;
    if (k < 1 || k > 62 || y < 1 || y > 62) continue;
    const i = (y * 64 + k) * 4; r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
  }
  return new THREE.Color(r / n / 255, g / n / 255, b / n / 255).convertSRGBToLinear().multiplyScalar(0.8);
}

async function resimYukle(adres) {
  const y = await fetch(adres, { credentials: "same-origin" });
  if (!y.ok) throw new Error("resim alınamadı");
  let bilgi = null;
  try { bilgi = JSON.parse(y.headers.get("X-Bilgi") || "null"); } catch (e) { bilgi = null; }
  const url = URL.createObjectURL(await y.blob());
  const resim = await new Promise((tamam, hata) => { const i = new Image(); i.onload = () => tamam(i); i.onerror = hata; i.src = url; });
  return { resim, bilgi, url };
}

export async function ac({ yuzey, kabartma, not = "" }) {
  if (acik) acik.kapat();
  const kap = kabuk();
  const sahneKap = kap.querySelector(".ucb-sahne");
  const bekle = kap.querySelector(".ucb-bekle");
  let durdu = false, kare = 0;
  const temizlikler = [];
  const kapat = () => {
    if (durdu) return;
    durdu = true; cancelAnimationFrame(kare);
    temizlikler.forEach((f) => { try { f(); } catch (e) { /* */ } });
    kap.remove(); document.body.style.overflow = ""; acik = null;
    if (history.state && history.state.ucb) history.back();
  };
  acik = { kapat };
  document.body.style.overflow = "hidden";
  history.pushState({ ucb: 1 }, "");
  const geri = () => { if (!durdu) { history.replaceState(null, ""); kapat(); } };
  window.addEventListener("popstate", geri);
  temizlikler.push(() => window.removeEventListener("popstate", geri));
  kap.querySelector(".ucb-kapat").addEventListener("click", kapat);
  const tus = (e) => { if (e.key === "Escape") kapat(); };
  document.addEventListener("keydown", tus);
  temizlikler.push(() => document.removeEventListener("keydown", tus));

  if (!destekli) { bekle.textContent = "Bu cihaz 3B görünümü desteklemiyor."; return; }
  let y, k;
  try {
    [y, k] = await Promise.all([resimYukle(yuzey), resimYukle(kabartma)]);
  } catch (e) {
    bekle.textContent = "Resim alınamadı. Bağlantıyı kontrol edip yeniden deneyin.";
    return;
  }
  if (durdu) return;
  temizlikler.push(() => { URL.revokeObjectURL(y.url); URL.revokeObjectURL(k.url); });
  const b = y.bilgi || { en: 160, boy: 230, sekil: "dikdortgen", kose: 3, kalinlik: 1.4 };
  const notlar = [`${Math.round(b.en)} × ${Math.round(b.boy)} cm`, b.not, not].filter(Boolean);
  const notKutu = kap.querySelector(".ucb-not");
  notKutu.textContent = notlar.join(" · "); notKutu.hidden = false;
  bekle.remove();

  const cizici = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: false });
  cizici.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  cizici.outputColorSpace = THREE.SRGBColorSpace;
  cizici.toneMapping = THREE.ACESFilmicToneMapping;
  cizici.toneMappingExposure = 1.05;
  cizici.shadowMap.enabled = true;
  cizici.shadowMap.type = THREE.PCFSoftShadowMap;
  sahneKap.appendChild(cizici.domElement);
  temizlikler.push(() => cizici.dispose());

  const sahne = new THREE.Scene();
  sahne.background = new THREE.Color(0xd6cec2);  // açık, sıcak: koyu ve açık halı ikisi de seçilir
  const buyuk = Math.max(b.en, b.boy);
  sahne.fog = new THREE.Fog(0xd6cec2, buyuk * 2.2, buyuk * 6);
  const kamera = new THREE.PerspectiveCamera(38, 1, buyuk / 50, buyuk * 30);

  // ışık: gökyüzü + yumuşak gölgeli ana ışık (sol üstten, katalog fotoğrafındaki gibi) + arkadan hafif dolgu
  sahne.add(new THREE.HemisphereLight(0xfff6e8, 0x8a7d6c, 1.2));
  const gunes = new THREE.DirectionalLight(0xffffff, 2.3);
  gunes.position.set(-buyuk * 0.6, buyuk * 1.4, buyuk * 0.9);
  gunes.castShadow = true;
  gunes.shadow.mapSize.set(1024, 1024);
  const sg = gunes.shadow.camera; sg.left = -buyuk; sg.right = buyuk; sg.top = buyuk; sg.bottom = -buyuk; sg.near = 1; sg.far = buyuk * 4;
  gunes.shadow.radius = 6; gunes.shadow.bias = -0.0005;
  sahne.add(gunes);
  const dolgu = new THREE.DirectionalLight(0xffe9cc, 0.45);
  dolgu.position.set(buyuk, buyuk * 0.5, -buyuk);
  sahne.add(dolgu);

  // zemin (yalnız gölgeyi gösterir) + hafif ışıklı yer
  const yer = new THREE.Mesh(new THREE.CircleGeometry(buyuk * 8, 64), new THREE.MeshStandardMaterial({ color: 0xc9bfb0, roughness: 1 }));
  yer.rotation.x = -Math.PI / 2; yer.receiveShadow = true;
  sahne.add(yer);

  const yuzeyDoku = new THREE.Texture(y.resim);
  yuzeyDoku.colorSpace = THREE.SRGBColorSpace;
  yuzeyDoku.anisotropy = cizici.capabilities.getMaxAnisotropy();
  yuzeyDoku.repeat.set(1 / b.en, 1 / b.boy); yuzeyDoku.offset.set(0.5, 0.5);
  yuzeyDoku.needsUpdate = true;
  const kabartmaDoku = new THREE.Texture(k.resim);
  kabartmaDoku.repeat.copy(yuzeyDoku.repeat); kabartmaDoku.offset.copy(yuzeyDoku.offset);
  kabartmaDoku.needsUpdate = true;
  temizlikler.push(() => { yuzeyDoku.dispose(); kabartmaDoku.dispose(); });

  const kalin = b.kalinlik || 1.4;
  const pah = Math.min(0.6, kalin * 0.4);
  const geo = new THREE.ExtrudeGeometry(halıSekli(b), {
    depth: kalin - 2 * pah, bevelEnabled: true, bevelThickness: pah, bevelSize: pah * 0.8, bevelSegments: 4,
    curveSegments: b.sekil === "oval" ? 96 : 8,
  });
  const ust = new THREE.MeshStandardMaterial({ map: yuzeyDoku, bumpMap: kabartmaDoku, bumpScale: 2.2, roughness: 0.82, metalness: 0 });
  const yan = new THREE.MeshStandardMaterial({ color: kenarRengi(y.resim), roughness: 0.75 });
  const hali = new THREE.Mesh(geo, [ust, yan]);
  hali.rotation.x = -Math.PI / 2;
  hali.position.y = pah;
  hali.castShadow = true; hali.receiveShadow = true;
  sahne.add(hali);
  temizlikler.push(() => { geo.dispose(); ust.dispose(); yan.dispose(); });

  const kontrol = new OrbitControls(kamera, cizici.domElement);
  kontrol.enableDamping = true; kontrol.dampingFactor = 0.08;
  kontrol.enablePan = false;
  kontrol.minDistance = buyuk * 0.3; kontrol.maxDistance = buyuk * 5;
  kontrol.maxPolarAngle = Math.PI * 0.47;
  kontrol.target.set(0, 0, 0);
  kontrol.autoRotateSpeed = 1.2;
  temizlikler.push(() => kontrol.dispose());

  // seçilen yönden halının tamamı ekrana sığacak uzaklık (dik telefon ekranında yatay açı dardır)
  const yaricap = Math.hypot(b.en, b.boy) / 2;
  const konum = (x, y, z) => {
    const yon = new THREE.Vector3(x, y, z).normalize();
    const dikey = THREE.MathUtils.degToRad(kamera.fov) / 2;
    const yatay = Math.atan(Math.tan(dikey) * kamera.aspect);
    const d = (yaricap * 0.98) / Math.sin(Math.min(dikey, yatay));
    kamera.position.copy(yon.multiplyScalar(d));
  };
  const acilar = {
    egik: () => konum(0.35, 1.0, 1.05),
    ust: () => konum(0, 1, 0.001),
    yan: () => konum(1.0, 0.34, 0.62),
  };
  const dugmeler = kap.querySelectorAll(".ucb-alt button");
  const sec = (ad) => {
    dugmeler.forEach((d) => d.classList.toggle("etkin", d.dataset.aci === ad || (d.dataset.aci === "don" && kontrol.autoRotate)));
  };
  dugmeler.forEach((d) => d.addEventListener("click", () => {
    if (d.dataset.aci === "don") { kontrol.autoRotate = !kontrol.autoRotate; d.classList.toggle("etkin", kontrol.autoRotate); return; }
    acilar[d.dataset.aci](); kontrol.update(); sec(d.dataset.aci);
  }));
  kontrol.addEventListener("start", () => { dugmeler.forEach((d) => d.dataset.aci !== "don" && d.classList.remove("etkin")); });
  const boyutla = () => {
    const w = sahneKap.clientWidth, h = sahneKap.clientHeight;
    if (!w || !h) return;
    cizici.setSize(w, h, false);
    kamera.aspect = w / h;
    // dar (dik) ekranda halı ekrana sığsın
    kamera.fov = w < h ? 50 : 38;
    kamera.updateProjectionMatrix();
  };
  boyutla();
  acilar.egik(); sec("egik");
  const go = new ResizeObserver(boyutla); go.observe(sahneKap);
  temizlikler.push(() => go.disconnect());

  const dongu = () => {
    if (durdu) return;
    kontrol.update();
    cizici.render(sahne, kamera);
    kare = requestAnimationFrame(dongu);
  };
  dongu();
}
