"""Eksporter rapportfigurer fra verifiserte resultater med Pillow, uten nettleser."""
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,re,textwrap

from build_report_assets import OUT, ROOT as PROJECT_ROOT
ROOT=PROJECT_ROOT/'report'
manifest=json.loads((OUT/'manifest.json').read_text())
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
MONO='/System/Library/Fonts/Menlo.ttc'
def load_font(path,size):
    if Path(path).exists(): return ImageFont.truetype(path,size)
    fallback='DejaVuSansMono.ttf' if 'Menlo' in path else ('DejaVuSans-Bold.ttf' if 'Bold' in path else 'DejaVuSans.ttf')
    return ImageFont.truetype(fallback,size)
fonts={k:load_font(p,size) for k,p,size in [('title',BOLD,44),('sub',FONT,28),('note',FONT,28),('header',BOLD,30),('cell',FONT,36),('code',MONO,32),('h2',BOLD,36)]}
class Parse(HTMLParser):
    def __init__(self): super().__init__(); self.blocks=[]; self.typ=None; self.buf=''; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='table': self.table=[]
        elif tag=='tr': self.row=[]
        elif tag in ['td','th']: self.cell=''; self.header=tag=='th'
        elif tag=='br':
            if self.cell is not None: self.cell+='\n'
        elif tag in ['h1','h2','pre'] or tag=='p' and attrs.get('class') in ['sub','note']:
            self.typ={'h1':'title','h2':'h2','pre':'code','p':attrs.get('class')}.get(tag); self.buf=''; self.end=tag
    def handle_data(self,d):
        if self.cell is not None: self.cell+=d
        elif self.typ: self.buf+=d
    def handle_endtag(self,tag):
        if tag in ['td','th'] and self.cell is not None: self.row.append(self.cell); self.cell=None
        elif tag=='tr' and self.row is not None: self.table.append(self.row); self.row=None
        elif tag=='table' and self.table is not None: self.blocks.append(('table',self.table)); self.table=None
        elif self.typ and tag==self.end: self.blocks.append((self.typ,self.buf.strip('\n'))); self.typ=None

W=1800; PAD=40; INNER=W-2*PAD
measure=ImageDraw.Draw(Image.new('RGB',(1,1)))
def wrap(s,font,width):
    out=[]
    for paragraph in str(s).split('\n'):
        if not paragraph: out.append(''); continue
        words=paragraph.split(' '); line=''
        for word in words:
            candidate=(line+' '+word) if line else word
            if measure.textlength(candidate,font=font)<=width: line=candidate
            else:
                if line: out.append(line)
                line=word
                while measure.textlength(line,font=font)>width:
                    cut=max(1,int(len(line)*width/measure.textlength(line,font=font)))
                    while measure.textlength(line[:cut],font=font)>width: cut-=1
                    out.append(line[:cut]); line=line[cut:]
        if line: out.append(line)
    return out
weights={
'resultat_01':[.29,.09,.12,.28,.22],
'resultat_02':[.34,.34,.12,.20],
'resultat_03':[.50,.25,.25],
'resultat_04':[.22,.085,.105,.21,.14,.24],
'resultat_05':[.17,.29,.16,.20,.18],
'resultat_06':[.25,.48,.27],
'resultat_07':[.49,.12,.20,.19],
'resultat_08':[.27,.25,.10,.18,.20],
'resultat_08_del2':[.27,.25,.10,.18,.20],
'resultat_09':[.21,.20,.59],
'resultat_10':[.20,.24,.34,.22],
'resultat_10_varians':[.20,.24,.34,.22],
'innsetting_kontroll':[.53,.47]}
for item in manifest:
    name=item['name']; parser=Parse(); parser.feed(Path(item['html']).read_text())
    blocks=parser.blocks
    if name=='resultat_03':
        blocks=[(k, [row[:3] for row in v] if k=='table' else v) for k,v in blocks]
        blocks.append(('note','Fem eksempelsjangre for alle ti: Action, Adventure, Animation, Comedy, Crime.'))
    ops=[]; y=PAD
    for kind,value in blocks:
        if kind=='table':
            ws=weights.get(name,[1/len(value[0])]*len(value[0])); ws=[x/sum(ws)*INNER for x in ws]
            for i,row in enumerate(value):
                font=fonts['header' if i==0 else 'cell']; lh=38 if i==0 else 44
                lines=[wrap(cell,font,w-28) for cell,w in zip(row,ws)]
                height=max(map(len,lines))*lh+26
                ops.append(('row',y,height,ws,lines,font,lh,i))
                y+=height
            y+=20
        elif kind=='code':
            font=fonts['code']; lh=41; out=[]
            for line in value.splitlines():
                width=INNER-36
                if measure.textlength(line,font=font)<=width: out.append(line)
                else:
                    indent=len(line)-len(line.lstrip()); chunks=textwrap.wrap(line.strip(),width=84-indent,break_long_words=True,break_on_hyphens=False)
                    out.extend([' '*indent+chunk for chunk in chunks])
            height=len(out)*lh+32; ops.append(('code',y,height,out,font,lh)); y+=height+16
        else:
            font=fonts[kind]; lh={'title':54,'sub':37,'h2':46,'note':37}[kind]
            lines=wrap(value,font,INNER); ops.append(('text',y,lines,font,lh,kind)); y+=len(lines)*lh+{'title':6,'sub':15,'h2':12,'note':8}[kind]
    im=Image.new('RGB',(W,int(y+PAD)),'white'); d=ImageDraw.Draw(im)
    for op in ops:
        if op[0]=='text':
            _,yy,ls,f,lh,k=op; color='#00509e' if k in ['title','h2'] else '#4b5966'
            for line in ls: d.text((PAD,yy),line,font=f,fill=color); yy+=lh
        elif op[0]=='code':
            _,yy,h,ls,f,lh=op; d.rounded_rectangle((PAD,yy,W-PAD,yy+h),radius=10,fill='#f4f7fa',outline='#cbd6df',width=2)
            for line in ls: d.text((PAD+18,yy+16),line,font=f,fill='#172332'); yy+=lh
        else:
            _,yy,h,ws,ls,f,lh,i=op; fill='#edf3f7' if i==0 else ('#f7f9fb' if i%2==0 else '#ffffff')
            d.rectangle((PAD,yy,W-PAD,yy+h),fill=fill); x=PAD
            for ww,cell in zip(ws,ls):
                cy=yy+13
                for line in cell: d.text((x+14,cy),line,font=f,fill='#172332'); cy+=lh
                x+=ww
            d.line((PAD,yy+h,W-PAD,yy+h),fill='#00509e' if i==0 else '#dce3e8',width=3 if i==0 else 2)
    im.save(item['image'],quality=95,subsampling=0,dpi=(220,220))
    print(name,im.size)
