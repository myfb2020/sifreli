import sys, io, zipfile, json, struct, os
sys.path.insert(0, os.path.dirname(__file__)); import uzak_zip
zipno, hedef = sys.argv[1], sys.argv[2]
d = json.load(open(sys.argv[3]))
z = zipfile.ZipFile(io.BufferedReader(uzak_zip.Uzak(d[zipno]), buffer_size=4 << 20))
os.makedirs(hedef, exist_ok=True)
for i in z.infolist():
    ad = os.path.basename(i.filename).rsplit('.', 1)[0]
    yol = os.path.join(hedef, ad + '.jpg')
    if os.path.exists(yol): continue
    with z.open(i) as f:
        b = f.read(100)
        jo, jl = struct.unpack('>II', b[84:92])
        f.read(jo - 100)
        j = f.read(jl)
    open(yol, 'wb').write(j)
    print(zipno, ad, jl, flush=True)
