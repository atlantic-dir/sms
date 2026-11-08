import sys, io; sys.path.insert(0,'src')
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fontsleuth.font_library import FontScanner
from fontsleuth.ink_analysis import InkAnalyzer
from fontsleuth.text_mask import MaskBuilder
from fontsleuth.font_matcher import FontMatcher

rep = FontScanner.scan([Path('/usr/share/fonts')])
cands = [c for c in rep.candidates if 'Emoji' not in c.family and 'Unifont' not in c.family]
print(len(cands), "candidates")

def synth(c, text, size, ink, bg, jpeg=None, scale=None):
    f = ImageFont.truetype(str(c.path), size, index=c.index)
    if c.axes: f.set_variation_by_axes(list(c.axes))
    w = int(f.getlength(text))+30; asc, desc = f.getmetrics()
    im = Image.new('RGB',(w, asc+desc+24), bg)
    ImageDraw.Draw(im).text((15,12+asc), text, font=f, fill=ink, anchor='ls')
    if scale: im = im.resize((int(im.width*scale), int(im.height*scale)), Image.Resampling.BICUBIC)
    if jpeg:
        b=io.BytesIO(); im.save(b,'JPEG',quality=jpeg); im=Image.open(b).convert('RGB')
    return im

def run(c, text, size, ink, bg, **kw):
    im = synth(c, text, size, ink, bg, **kw)
    m = InkAnalyzer.analyze(np.asarray(im))
    mask = MaskBuilder.build(m.coverage)
    res = FontMatcher.rank(mask, text, cands, top_n=4)
    return m, res

if __name__ == "__main__":
    tests = [("Liberation Sans","Regular"),("Liberation Sans","Bold"),("Carlito","Bold"),("Carlito","Regular"),("DejaVu Serif","Book"),
             ("Liberation Serif","Italic"),("Inter","Medium"),("Inter","Light"),("FreeSans","Bold"),("JetBrains Mono","Regular"),("Caladea","Bold")]
    text = "Quarterly Report: Invoice 2048 due"
    ok=0
    for fam, sty in tests:
        c = next(x for x in cands if x.family==fam and x.style==sty)
        for size, kw in [(32,{}),(16,{}),(12,{'jpeg':70})]:
            m,res = run(c,text,size,(31,58,95),(250,250,240),**kw)
            top = res[0]
            hit = (top.candidate.family,top.candidate.style)==(fam,sty)
            ok+=hit
            print(f"{fam} {sty} @{size}{kw}: top={top.candidate.family} {top.candidate.style} s={top.score:.3f} size={top.size_px:.1f} | 2nd={res[1].candidate.family} {res[1].candidate.style} {res[1].score:.3f} | ink={m.ink.hex()} {'OK' if hit else 'MISS'}")
    print(ok, "/", len(tests)*3)
