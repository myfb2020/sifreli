import json, io, sys
from pathlib import Path
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.comments import Comment

K = Path("/home/user/sifreli/uretim_takip/uretim")
sys.path.insert(0, str(K.parent))
CIKTI = Path(sys.argv[1])
TMP = Path(__file__).parent / "kucuk"; TMP.mkdir(exist_ok=True)
kat = json.load(open(K / "katalog_tohum/katalog.json"))

# ---- renk kartelası: programdaki malzemeler + kürk/deri renkleri (adlar geçici)
import importlib.util
src = (K / "parcali.py").read_text()
ns = {}
exec(src[src.index("MALZEMELER = ["):src.index("MALZEME_AD")], ns)
exec(src[src.index("IPLIKLER = ["):src.index("IPLIK_HEX")], ns)
exec(src[src.index("NAKIS_MOTIFLERI = ["):src.index("MOTIF = ")], ns)

def grup(k):
    if k.startswith("pelus") or k == "dalgali_pelus": return "PL", "Peluş"
    if k.startswith("bienca"): return "BN", "Bienca"
    if k.startswith("rona"): return "RN", "Rona"
    if k.endswith("keten"): return "KT", "Keten görünümlü suni deri"
    if "varak" in k or "sim" in k or "ayna" in k: return "VR", "Varak / simli"
    if "kadife" in k: return "KD", "Kadife"
    if k.endswith("_deri"): return "SD", "Düz suni deri"
    return "MT", "Metalik"
KURK = [("Beyaz", "#efebe4"), ("Krem", "#e4d8c0"), ("Bej", "#cdb994"), ("Açık gri", "#b4b2ae"), ("Gri", "#8a8885"),
        ("Antrasit", "#4d4b49"), ("Vizon", "#8a7867"), ("Kahve", "#5e4636"), ("Taba", "#9a5e34"), ("Siyah", "#222120"),
        ("Doğal desenli (dana)", "#8b6e55"), ("Mavi", "#2d5fa8"), ("Lacivert", "#28304f"), ("Bordo", "#6b2430"), ("Çok renkli (patchwork)", "#7d6a5c")]
kartela, sayac = [], {}
for k, ad, hx in ns["MALZEMELER"]:
    g, gad = grup(k); sayac[g] = sayac.get(g, 0) + 1
    kartela.append((f"{g}{sayac[g]:02d}", ad, gad, hx))
for ad, hx in KURK:
    sayac["KR"] = sayac.get("KR", 0) + 1
    kartela.append((f"KR{sayac['KR']:02d}", f"{ad} kürk/deri", "Kürk / doğal deri", hx))
iplik = [(f"IP{i+1:02d}", f"{ad} iplik", "Nakış ipliği", hx) for i, (_, ad, hx) in enumerate(ns["IPLIKLER"])]

def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
SERI_GRUP = {"İpek Peluş": {"PL"}, "Peluche": {"PL"}, "Bienca": {"BN", "VR"}, "Rono": {"RN", "KT"}}
def tahmin(resim, seri):
    im = Image.open(resim).convert("RGB"); w, h = im.size
    orta = im.crop((int(w*.35), int(h*.35), int(w*.65), int(h*.65))).resize((20, 20))
    px = sorted(orta.getdata(), key=sum); r, g, b = px[len(px)//2]
    gruplar = SERI_GRUP.get(seri, {"KR"})
    aday = [x for x in kartela if x[0][:2] in gruplar]
    return min(aday, key=lambda x: sum((a-c)**2 for a, c in zip(rgb(x[3]), (r, g, b))))

wb = Workbook()
F = "Arial"; ince = Side(style="thin", color="D9CFC4"); kenar = Border(top=ince, bottom=ince, left=ince, right=ince)
BAS = PatternFill("solid", fgColor="5C3A21"); BASF = Font(name=F, bold=True, color="FFFFFF")
GIRDI = PatternFill("solid", fgColor="FFF2CC"); TAHMIN = PatternFill("solid", fgColor="FCE4D6")
def baslik(ws, satir, basliklar, genis):
    for i, (b, g) in enumerate(zip(basliklar, genis), 1):
        c = ws.cell(satir, i, b); c.fill = BAS; c.font = BASF; c.alignment = Alignment(wrap_text=True, vertical="center"); c.border = kenar
        ws.column_dimensions[c.column_letter].width = g
    ws.row_dimensions[satir].height = 32; ws.freeze_panes = ws.cell(satir+1, 1)
def kucuk(yol, b=110):
    im = Image.open(yol).convert("RGB"); im.thumbnail((b, b))
    p = TMP / (yol.stem + ".jpg"); im.save(p, quality=80); return XLImage(str(p))

# ---- 1 Açıklama
ws = wb.active; ws.title = "Nasıl kullanılır"
ws.column_dimensions["A"].width = 110
satirlar = [
 ("BIENNA FUR – ÜRÜN KOD LİSTESİ (taslak)", True),
 ("", False),
 ("Ürün kodu = MODEL KODU – RENK NO      örnek:  IPS-449-01", True),
 ("Satışta ölçü eklenir:  IPS-449-01-160x230   (ölçünün koda girip girmeyeceği henüz kararlaştırılmadı)", False),
 ("", False),
 ("MODEL KODU: halının şekli/deseni. Katalogdaki kod (TOS-034, IPS-449…). Müşteri fotoğrafından eklenen: MM-001…  Bayi/stüdyo tasarımı modele çevrilirse: BF-001…", False),
 ("RENK NO: aynı modelin renk seçeneği. 01 = katalog fotoğrafındaki renkler. Aynı model başka renklerde yapılınca alt satıra 02, 03… eklenir.", False),
 ("Her renk seçeneğinde parça parça renk yazılır: Zemin, Bant/desen, Kenar (biye/lanfel), varsa nakış motifi ve iplik rengi. Renkler 'Renk kartelası' sayfasındaki listeden seçilir.", False),
 ("Lazer deseni (DB…) ve nakış motifi (61.01…) ürün kodu değildir; halının parçalarıdır, satırda ayrıca yazılır.", False),
 ("", False),
 ("NASIL DOLDURULUR", True),
 ("• Sarı hücreler sizin dolduracağınız yerlerdir (açılır listeden seçin). 'Ürün kodu' sütunu kendiliğinden oluşur, ona dokunmayın.", False),
 ("• Turuncu 'Zemin' hücreleri program tarafından fotoğrafın ortasındaki renge bakılarak TAHMİN edildi. Kontrol edip düzeltin.", False),
 ("• Yeni renk seçeneği için: satırı kopyalayıp hemen altına yapıştırın, Renk no'yu 02 yapın, renkleri değiştirin.", False),
 ("• Kartelada olmayan renk varsa 'Renk kartelası' sayfasının sonuna yeni kod ekleyin (aynı grup harfleriyle, örn. PL10). Adlar geçicidir, atölyedeki adlarla değiştirin.", False),
 ("• Paraşüt'teki karşılığı biliniyorsa 'Paraşüt kodu' sütununa yazın; sonra programa aktarırken eşleştirilir.", False),
 ("", False),
 ("Bu liste programa sonra aynı düzenle aktarılacak; sütun adlarını değiştirmeyin.", True),
]
for i, (m, k) in enumerate(satirlar, 1):
    c = ws.cell(i, 1, m); c.font = Font(name=F, bold=k, size=14 if i == 1 else 11, color="5C3A21" if k else "000000")
    c.alignment = Alignment(wrap_text=True)

# ---- 2 Ürün kodları
ws = wb.create_sheet("Ürün kodları")
bas = ["Resim", "Seri", "Model kodu", "Renk no", "Zemin", "Bant / desen", "Kenar (biye / lanfel)", "Lazer deseni",
       "Nakış motifi", "Nakış ipliği", "Ürün kodu", "Paraşüt kodu", "Not"]
baslik(ws, 1, bas, [17, 15, 12, 8, 28, 24, 24, 12, 24, 14, 16, 16, 30])
r = 2
for m in kat["modeller"]:
    yol = K / "katalog_tohum/model" / m["dosya"]
    ws.row_dimensions[r].height = 82
    if yol.exists():
        img = kucuk(yol); ws.add_image(img, f"A{r}")
    ws.cell(r, 2, m["seri"]); ws.cell(r, 3, m["kod"]); ws.cell(r, 4, "01")
    t = tahmin(yol, m["seri"]) if yol.exists() else None
    if t:
        c = ws.cell(r, 5, f"{t[0]} {t[1]}"); c.fill = TAHMIN
    for col in range(6, 11): ws.cell(r, col).fill = GIRDI
    ws.cell(r, 12).fill = GIRDI; ws.cell(r, 13).fill = GIRDI
    ws.cell(r, 11, f'=IF(C{r}="","",C{r}&"-"&D{r})').font = Font(name=F, bold=True)
    for col in range(1, 14):
        c = ws.cell(r, col); c.border = kenar; c.alignment = Alignment(vertical="center", wrap_text=True)
        if col != 11: c.font = Font(name=F)
    r += 1
SON = r - 1 + 300   # yeni renk satırları için yer
for rr in range(r, SON + 1):
    ws.cell(rr, 11, f'=IF(C{rr}="","",C{rr}&"-"&D{rr})').font = Font(name=F, bold=True)
ws.cell(2, 4).comment = Comment("01 = katalog fotoğrafındaki renkler. Başka renk için satırı kopyalayıp 02, 03 yazın.", "Bienna")
ws.auto_filter.ref = f"A1:M{r-1}"

# ---- 3 Renk kartelası
wk = wb.create_sheet("Renk kartelası")
baslik(wk, 1, ["Kod", "Renk / malzeme adı", "Grup", "Örnek", "Liste adı (seçimde görünen)", "Atölyedeki adı / tedarikçi kodu"], [8, 34, 26, 10, 40, 34])
tum = kartela + iplik
for i, (kod, ad, g, hx) in enumerate(tum, 2):
    wk.cell(i, 1, kod); wk.cell(i, 2, ad); wk.cell(i, 3, g)
    wk.cell(i, 4).fill = PatternFill("solid", fgColor=hx.lstrip("#").upper())
    wk.cell(i, 5, f'=A{i}&" "&B{i}'); wk.cell(i, 6).fill = GIRDI
    for col in range(1, 7):
        wk.cell(i, col).border = kenar
        if col != 4: wk.cell(i, col).font = Font(name=F)
sonk = len(kartela) + 1
for i in range(len(tum) + 2, len(tum) + 42):  # yeni renkler için boş satırlar
    wk.cell(i, 5, f'=IF(A{i}="","",A{i}&" "&B{i})'); wk.cell(i, 1).fill = GIRDI; wk.cell(i, 2).fill = GIRDI
not_satir = len(tum) + 43
wk.cell(not_satir, 1, "Not: adlar ve renk örnekleri programdaki malzeme fotoğraflarından/tahminden; atölyedeki gerçek adlarla düzeltin. "
        "Grup harfleri: PL peluş, BN Bienca, RN Rona, KT keten görünümlü, VR varak/simli, KD kadife, SD düz suni deri, MT metalik, KR kürk/deri, IP iplik.").font = Font(name=F, italic=True)

# ---- 4 Lazer desenleri
wd = wb.create_sheet("Lazer desenleri")
baslik(wd, 1, ["Resim", "Desen kodu", "Suni deri ekranında", "Adı / not"], [17, 12, 20, 40])
gizli = {"DB002", "DB007", "DB010", "DB011"}
desenler = list(kat["desenler"]) + [{"kod": "DB015", "dosya": None}]
for i, d in enumerate(desenler, 2):
    wd.row_dimensions[i].height = 82
    if d.get("dosya") and (K / "katalog_tohum/desen" / d["dosya"]).exists():
        wd.add_image(kucuk(K / "katalog_tohum/desen" / d["dosya"]), f"A{i}")
    wd.cell(i, 2, d["kod"]); wd.cell(i, 3, "gizli" if d["kod"] in gizli else "görünür")
    if d["kod"] == "DB015": wd.cell(i, 4, "Grek bant (programda çizildi)")
    wd.cell(i, 4).fill = GIRDI
    for col in range(1, 5): wd.cell(i, col).border = kenar; wd.cell(i, col).font = Font(name=F)

# ---- 5 Nakış motifleri
wn = wb.create_sheet("Nakış motifleri")
baslik(wn, 1, ["Resim", "Motif kodu", "Adı", "En (cm)", "Boy (cm)", "Tür", "Liste adı"], [17, 11, 26, 9, 9, 18, 34])
for i, (kod, ad, en, boy, tur) in enumerate(ns["NAKIS_MOTIFLERI"], 2):
    wn.row_dimensions[i].height = 82
    p = K / "tasarim_varlik/nakis" / (kod.replace(".", "_") + ".png")
    if p.exists():
        im = Image.open(p).convert("RGBA"); arka = Image.new("RGB", im.size, (40, 36, 34)); arka.paste((201, 167, 94), mask=im.split()[-1])
        q = TMP / f"nk_{kod}.png"; arka.thumbnail((110, 110)); arka.save(q); wn.add_image(XLImage(str(q)), f"A{i}")
    for col, v in enumerate([None, kod, ad, en, boy, "şerit (uç uca)" if tur == "serit" else "tek motif"], 1):
        if v is not None: wn.cell(i, col, v)
    wn.cell(i, 7, f'=B{i}&" "&C{i}')
    for col in range(1, 8): wn.cell(i, col).border = kenar; wn.cell(i, col).font = Font(name=F)

# ---- açılır listeler
nk = len(ns["NAKIS_MOTIFLERI"]) + 1
wb.defined_names["Renkler"] = DefinedName("Renkler", attr_text=f"'Renk kartelası'!$E$2:$E${len(tum)+41}")
wb.defined_names["Iplikler"] = DefinedName("Iplikler", attr_text=f"'Renk kartelası'!$E${sonk+1}:$E${len(tum)+1}")
wb.defined_names["Desenler"] = DefinedName("Desenler", attr_text=f"'Lazer desenleri'!$B$2:$B${len(desenler)+1}")
wb.defined_names["Motifler"] = DefinedName("Motifler", attr_text=f"'Nakış motifleri'!$G$2:$G${nk}")
for ad, aralik in [("Renkler", f"E2:G{SON}"), ("Desenler", f"H2:H{SON}"), ("Motifler", f"I2:I{SON}"), ("Iplikler", f"J2:J{SON}")]:
    dv = DataValidation(type="list", formula1=f"={ad}", allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv); dv.add(aralik)
wb.active = 1
wb.save(CIKTI)
print("ok", len(kat["modeller"]), "model", len(tum), "renk")
