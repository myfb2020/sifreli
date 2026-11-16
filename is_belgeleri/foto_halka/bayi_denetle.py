"""islemler.jsonl: her işlemde sunucu hangi parçaları 'değişti' sayıyor? Beklenenle birebir aynı mı?"""
import os, sys, json, django
sys.path.insert(0, "."); os.environ["DJANGO_SETTINGS_MODULE"] = "fabrika.settings"; django.setup()
from django.http import QueryDict
from uretim import foto_temel as ft
from uretim.parcali_views import _temizle

hatalar, say = [], 0
for satir in open(sys.argv[1]):
    k = json.loads(satir); say += 1
    kod, islem = k["kod"], k["islem"]
    if islem == "SECENEK_YOK":
        hatalar.append((kod, islem, k["kap"], [], [], {})); continue
    v = _temizle(QueryDict(k["q"]))
    if not ft.uygun_mu(kod):
        continue
    b = ft.referans(kod, v["en"], v["boy"])
    d = ft.degisenler(v, b)
    farklar = {a: (v.get(a), b.get(a)) for a in set(v) | set(b) if v.get(a) != b.get(a)}
    ilk_no = ft._ogeler(v)[0][0] if ft._ogeler(v) else None
    if islem == "ilk":
        bek = set()
    elif islem.startswith("h"):
        i = int(islem[1]); bek = {("h", i)} | ({"kenar"} if ilk_no == i else set())
    elif islem.startswith("a"):
        i = int(islem[1]); bek = {("a", i)} if not ft.referans(kod).get(f"a{i}_gen") else set()
    elif islem == "zemin":
        bek = {"zemin"} | {("a", i) for i in range(1, 4)}
    elif islem == "madalyon_malzeme":
        bek = {"madalyon", "mcerceve"}
    elif islem == "kenar_renk":
        bek = {"kenar"}
    if d != bek:
        hatalar.append((kod, islem, k["secilen"], sorted(map(str, d - bek)), sorted(map(str, bek - d)),
                        {a: f for a, f in farklar.items() if a not in ("hazir",)}))
print(say, "işlem;", len(hatalar), "hatalı")
for h in hatalar:
    print(h[0], h[1], "→", h[2], "| fazladan:", h[3], "eksik:", h[4], "| farklar:", h[5])
