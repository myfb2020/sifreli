import json, sys
from PIL import Image, ImageDraw, ImageFont
D, kl, cikis = sys.argv[1], sys.argv[2], sys.argv[3]
F='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; f=ImageFont.truetype(F,24); fb=ImageFont.truetype(F.replace('Sans','Sans-Bold'),28)
olc=json.load(open(D+'/olcek.json')); b=json.load(open(kl+'/bilgi.json'))
ad={'BN01':'Gümüş & altın varak','BN02':'Eskitme kahve / krem','BN03':'Gümüş & gri eskitme','BN04':'Altın & gümüş eskitme','BN05':'Gri & siyah-gümüş varak'}
KART=Image.open('/home/user/sifreli/is_belgeleri/kartela_foto/bienca_kartela.jpg').convert('RGB')
KK={'BN01':(80,215,400,535),'BN02':(775,315,1040,580),'BN03':(330,640,650,955),'BN04':(80,1080,380,1380)}
CM=15; W=380
p=Image.new('RGB',(3*W+40,70+5*(W+60)),'white'); d=ImageDraw.Draw(p)
for x,t in ((0,'Kartelanız'),(W+20,'Şu an programda'),(2*W+40,'Yeni çekimden')): d.text((x,15),t,fill='black',font=fb)
for i,k in enumerate(ad):
  y=70+i*(W+60); e=Image.open(D+'/bienca_'+k.lower()+'.jpg').convert('RGB'); pc=e.width/olc['bienca_'+k.lower()]; s=min(int(CM*pc),min(e.size))
  e=e.crop((0,0,s,s)).resize((W,W),Image.LANCZOS)
  n=None
  if k in b: n=Image.open(f'{kl}/{k}.jpg'); s=int(CM*b[k]['px_cm']); n=n.crop((0,0,s,s)).resize((W,W),Image.LANCZOS)
  if k in KK: p.paste(KART.crop(KK[k]).resize((W,W),Image.LANCZOS),(0,y+40))
  else: d.text((10,y+180),'(kartelada yok)',fill='#777',font=f)
  d.text((0,y),f'{k}  {ad[k]}  (çekim {b[k]["cekim"] if k in b else "—"}) — {CM}×{CM} cm',fill='black',font=f); p.paste(e,(W+20,y+40))
  if n is not None: p.paste(n,(2*W+40,y+40))
  else: d.text((2*W+50,y+180),'çekim yok — eski kalır',fill='#777',font=f)
p.save(cikis,quality=88)
