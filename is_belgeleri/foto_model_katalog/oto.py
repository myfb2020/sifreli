"""Katalog fotoğrafı (koyu deri zemin üstünde halı) → halı maskesi, orta, çerçeve."""
import cv2, numpy as np, sys, json
K='/home/user/sifreli/uretim_takip/uretim/katalog_tohum/model/'
def lab(im): return cv2.cvtColor(im.astype(np.float32)/255, cv2.COLOR_BGR2LAB)
def hali(im, hull=True):
    L=lab(im); h,w=L.shape[:2]
    kenar=np.concatenate([L[:6].reshape(-1,3),L[-6:].reshape(-1,3),L[:,:6].reshape(-1,3),L[:,-6:].reshape(-1,3)])
    zem=np.median(kenar,0); fark=np.linalg.norm(cv2.GaussianBlur(L,(0,0),2)-zem,axis=2)
    b=(fark>14).astype(np.uint8)
    b=cv2.morphologyEx(b,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    n,lb,st,_=cv2.connectedComponentsWithStats(b); i=1+np.argmax(st[1:,4]); b=(lb==i).astype(np.uint8)
    cs,_=cv2.findContours(b,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); c=max(cs,key=cv2.contourArea)
    m=np.zeros_like(b); cv2.drawContours(m,[cv2.convexHull(c) if hull else c],-1,1,-1)
    return m
def gecis(p, esik):
    p=cv2.GaussianBlur(p.reshape(1,-1,3),(0,0),2).reshape(-1,3)
    d=np.linalg.norm(p[3:]-p[:-3],axis=1)
    return d
def orta(im, m):
    """Merkezden dışa ilk güçlü geçiş: sol/sağ/üst/alt."""
    L=lab(im); ys,xs=np.where(m>0); x0,x1,y0,y1=xs.min(),xs.max(),ys.min(),ys.max()
    cx,cy=(x0+x1)//2,(y0+y1)//2
    yat=L[cy-40:cy+40].mean(0); dik=L[:,cx-30:cx+30].mean(1)
    def ilk(profil, bas, son, adim):
        p=cv2.GaussianBlur(profil.reshape(1,-1,3),(0,0),1.5).reshape(-1,3)
        ref=p[bas-15:bas+15].mean(0) if adim>0 else p[bas-15:bas+15].mean(0)
        i=bas
        while (i<son if adim>0 else i>son):
            if np.linalg.norm(p[i]-ref)>12 and np.linalg.norm(p[i+adim*2]-ref)>12: return i
            i+=adim
        return son
    sol=ilk(yat,cx,x0,-1); sag=ilk(yat,cx,x1,1); ust=ilk(dik,cy,y0,-1); alt=ilk(dik,cy,y1,1)
    return dict(hali=[int(x0),int(y0),int(x1),int(y1)], orta=[int(sol),int(ust),int(sag),int(alt)])
if __name__=='__main__':
    sonuc={}
    for k in sys.argv[1:]:
        im=cv2.imread(K+k+'.jpg'); m=hali(im); g=orta(im,m); sonuc[k]=g
        o=im.copy(); cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(o,cs,-1,(0,0,255),2); a=g['orta']; cv2.rectangle(o,(a[0],a[1]),(a[2],a[3]),(0,255,0),2)
        cv2.imwrite(f'/tmp/claude-0/-home-user-sifreli/0314cf55-6a39-5afb-b0a7-fcfad6be5475/scratchpad/kat/k_{k}.jpg',cv2.resize(o,(208,254)))
        print(k,g)
    ims=[cv2.imread(f'/tmp/claude-0/-home-user-sifreli/0314cf55-6a39-5afb-b0a7-fcfad6be5475/scratchpad/kat/k_{k}.jpg') for k in sys.argv[1:]]
    sat=[np.hstack(ims[i:i+8]+[np.zeros_like(ims[0])]*(8-len(ims[i:i+8]))) for i in range(0,len(ims),8)]
    cv2.imwrite('/tmp/claude-0/-home-user-sifreli/0314cf55-6a39-5afb-b0a7-fcfad6be5475/scratchpad/kat/oto.jpg',np.vstack(sat))
