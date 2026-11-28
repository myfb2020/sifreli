import sys, io, zipfile, urllib.request, json
URL="https://drive.usercontent.google.com/download?id={}&export=download&confirm=t"
class Uzak(io.RawIOBase):
    def __init__(s, fid):
        s.u=URL.format(fid); s.p=0
        r=urllib.request.urlopen(urllib.request.Request(s.u,headers={"Range":"bytes=0-0"}))
        s.n=int(r.headers["Content-Range"].split("/")[1])
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.p
    def seek(s,o,w=0):
        s.p = o if w==0 else (s.p+o if w==1 else s.n+o); return s.p
    def read(s,k=-1):
        if k<0: k=s.n-s.p
        if k==0 or s.p>=s.n: return b""
        e=min(s.n,s.p+k)-1
        r=urllib.request.urlopen(urllib.request.Request(s.u,headers={"Range":f"bytes={s.p}-{e}"}))
        d=r.read(); s.p+=len(d); return d
    def readinto(s,b):
        d=s.read(len(b)); b[:len(d)]=d; return len(d)
if __name__=="__main__":
    out={}
    for ad,fid in json.load(open(sys.argv[1])).items():
        z=zipfile.ZipFile(io.BufferedReader(Uzak(fid),buffer_size=1<<20))
        out[ad]=[(i.filename,i.file_size) for i in z.infolist()]
        print(ad,len(out[ad]),flush=True)
    json.dump(out,open(sys.argv[2],"w"),ensure_ascii=False,indent=0)
