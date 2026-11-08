import sys; sys.path.insert(0,'src')
from tools_proto import *
from fontsleuth.analysis import AnalysisService
from fontsleuth.sources import PageImage
c = next(x for x in cands if x.family=="Carlito" and x.style=="Regular")
for size,kw in [(14,{}),(11,{'jpeg':60})]:
    im = synth(c,"Quarterly Report: Invoice 2048 due",size,(31,58,95),(250,250,240),**kw)
    r = AnalysisService.analyze_pixels(PageImage(im,None),"Quarterly Report: Invoice 2048 due",96,cands)
    f=r.findings[0]; print(size,kw,f.family,f.style_name,f.size_px,f.size_pt,r.ink_color.hex(),r.confidence,r.ambiguous,r.warnings)
