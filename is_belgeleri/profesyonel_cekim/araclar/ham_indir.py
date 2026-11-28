import sys, io, zipfile, json, os, shutil
sys.path.insert(0, os.path.dirname(__file__)); import uzak_zip
zipler = json.load(open(sys.argv[1])); icerik = json.load(open(sys.argv[2])); hedef = sys.argv[3]
istenen = set(sys.argv[4].split(','))
os.makedirs(hedef, exist_ok=True)
for zno, dosyalar in icerik.items():
    sec = [f for f, _ in dosyalar if os.path.basename(f)[4:8] in istenen]
    if not sec: continue
    z = zipfile.ZipFile(io.BufferedReader(uzak_zip.Uzak(zipler[zno]), buffer_size=8 << 20))
    for f in sec:
        yol = os.path.join(hedef, os.path.basename(f))
        if os.path.exists(yol): continue
        with z.open(f) as k, open(yol + '.yarim', 'wb') as c: shutil.copyfileobj(k, c, 8 << 20)
        os.rename(yol + '.yarim', yol); print(zno, f, flush=True)
