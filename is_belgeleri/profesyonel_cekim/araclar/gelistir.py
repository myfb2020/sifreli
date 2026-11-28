"""Ham RAF -> doğrusal RGB (sabit beyaz ayarı, pozlama süresine göre eşitlenmiş parlaklık)."""
import rawpy, numpy as np
from PIL import Image

def pozlama(r_yol):
    im = Image.open(r_yol.replace('/ham/', '/onizleme/').replace('.RAF', '.jpg'))
    e = im.getexif().get_ifd(0x8769)
    return float(e.get(33434)) * float(e.get(34855)) / 100.0  # süre × ISO/100

def dogrusal(yol, wb=None, yarim=True):
    with rawpy.imread(yol) as r:
        kw = dict(no_auto_bright=True, output_bps=16, gamma=(1, 1), half_size=yarim,
                  output_color=rawpy.ColorSpace.sRGB, highlight_mode=rawpy.HighlightMode.Clip)
        if wb is None: kw['use_camera_wb'] = True
        else: kw['user_wb'] = list(wb)
        a = r.postprocess(**kw).astype(np.float32) / 65535.0
    return a

def srgb(a):
    a = np.clip(a, 0, 1)
    b = np.where(a <= 0.0031308, 12.92 * a, 1.055 * np.power(a, 1 / 2.4) - 0.055)
    return Image.fromarray((b * 255 + 0.5).astype(np.uint8))
