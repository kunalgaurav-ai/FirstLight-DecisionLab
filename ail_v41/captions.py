"""No-drawtext caption rasterization.

A transparent PNG is generated in Python, then overlaid using FFmpeg's core
'overlay' filter. Pillow is optional; a deliberately legible 5x7 pure-stdlib
rasterizer is a *visible fallback*, not a reason to omit mandatory captions.
"""
from __future__ import annotations
import struct,zlib,textwrap,unicodedata
from pathlib import Path

WIDTH,HEIGHT=640,360
# A tiny embedded *bitmap alphabet*, not distributed font files.
GLYPHS={
'A':('01110','10001','10001','11111','10001','10001','10001'),
'B':('11110','10001','10001','11110','10001','10001','11110'),
'C':('01111','10000','10000','10000','10000','10000','01111'),
'D':('11110','10001','10001','10001','10001','10001','11110'),
'E':('11111','10000','10000','11110','10000','10000','11111'),
'F':('11111','10000','10000','11110','10000','10000','10000'),
'G':('01111','10000','10000','10111','10001','10001','01111'),
'H':('10001','10001','10001','11111','10001','10001','10001'),
'I':('11111','00100','00100','00100','00100','00100','11111'),
'J':('00111','00010','00010','00010','10010','10010','01100'),
'K':('10001','10010','10100','11000','10100','10010','10001'),
'L':('10000','10000','10000','10000','10000','10000','11111'),
'M':('10001','11011','10101','10101','10001','10001','10001'),
'N':('10001','11001','10101','10011','10001','10001','10001'),
'O':('01110','10001','10001','10001','10001','10001','01110'),
'P':('11110','10001','10001','11110','10000','10000','10000'),
'Q':('01110','10001','10001','10001','10101','10010','01101'),
'R':('11110','10001','10001','11110','10100','10010','10001'),
'S':('01111','10000','10000','01110','00001','00001','11110'),
'T':('11111','00100','00100','00100','00100','00100','00100'),
'U':('10001','10001','10001','10001','10001','10001','01110'),
'V':('10001','10001','10001','10001','10001','01010','00100'),
'W':('10001','10001','10001','10101','10101','10101','01010'),
'X':('10001','10001','01010','00100','01010','10001','10001'),
'Y':('10001','10001','01010','00100','00100','00100','00100'),
'Z':('11111','00001','00010','00100','01000','10000','11111'),
'0':('01110','10001','10011','10101','11001','10001','01110'),
'1':('00100','01100','00100','00100','00100','00100','01110'),
'2':('01110','10001','00001','00010','00100','01000','11111'),
'3':('11110','00001','00001','01110','00001','00001','11110'),
'4':('00010','00110','01010','10010','11111','00010','00010'),
'5':('11111','10000','10000','11110','00001','00001','11110'),
'6':('01110','10000','10000','11110','10001','10001','01110'),
'7':('11111','00001','00010','00100','01000','01000','01000'),
'8':('01110','10001','10001','01110','10001','10001','01110'),
'9':('01110','10001','10001','01111','00001','00001','01110'),
' ':('00000',)*7,'.':('00000','00000','00000','00000','00000','01100','01100'),
',':('00000','00000','00000','00000','01100','01100','00100'),
':':('00000','01100','01100','00000','01100','01100','00000'),
'-':('00000','00000','00000','11111','00000','00000','00000'),
'!':('00100','00100','00100','00100','00100','00000','00100'),
'/':('00001','00001','00010','00100','01000','10000','10000'),
"'":('00100','00100','00100','00000','00000','00000','00000'),
'(':('00010','00100','01000','01000','01000','00100','00010'),
')':('01000','00100','00010','00010','00010','00100','01000'),
'?':('01110','10001','00001','00010','00100','00000','00100'),
}

def make_lines(source):
 text=unicodedata.normalize('NFKD',source.replace('—','-').replace('–','-')).encode('ascii','replace').decode('ascii').upper()
 items=[]
 for row in text.splitlines():
  items.extend(textwrap.wrap(row, width=45,break_long_words=True,break_on_hyphens=True) or [''])
 if not items or len(items)>4:raise ValueError('CAPTION_OVERFLOW_OR_EMPTY')
 return items

def _png(p,data):
 def chunk(tag,payload):return struct.pack('>I',len(payload))+tag+payload+struct.pack('>I',zlib.crc32(tag+payload)&0xffffffff)
 # unfiltered RGBA scanlines
 body=b''.join(b'\x00'+bytes(data[y*WIDTH*4:(y+1)*WIDTH*4]) for y in range(HEIGHT))
 p.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(body,level=6))+chunk(b'IEND',b''))

def _stdlib_png(lines,p):
 px=bytearray(WIDTH*HEIGHT*4)
 scale=2;line_height=19;y0=HEIGHT-18-len(lines)*line_height
 # black translucent lower third; retains underlying photograph
 for y in range(max(0,y0-12),HEIGHT):
  for x in range(WIDTH):
   idx=(y*WIDTH+x)*4
   px[idx:idx+4]=bytes((5,12,22,212))
 for linei,line in enumerate(lines):
  ybase=y0+linei*line_height
  for ci,c in enumerate(line):
   g=GLYPHS.get(c,GLYPHS['?'])
   for yy,bits in enumerate(g):
    for xx,on in enumerate(bits):
     if on=='1':
      for dy in range(scale):
       for dx in range(scale):
        x=18+ci*12+xx*scale+dx;y=ybase+yy*scale+dy
        if 0<=x<WIDTH and 0<=y<HEIGHT:
         idx=(y*WIDTH+x)*4;px[idx:idx+4]=b'\xff\xff\xff\xff'
 _png(p,px)

def caption_png(text_path:Path,png_path:Path, force_stdlib=False):
 text=Path(text_path).read_text(encoding='utf-8')
 lines=make_lines(text)
 png_path=Path(png_path)
 if not force_stdlib:
  try:
   from PIL import Image,ImageDraw,ImageFont
   im=Image.new('RGBA',(WIDTH,HEIGHT),(0,0,0,0))
   d=ImageDraw.Draw(im)
   y0=HEIGHT-18-len(lines)*21
   d.rectangle((0,max(0,y0-13),WIDTH,HEIGHT),fill=(4,10,22,215))
   font=None
   paths=('/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Helvetica.ttc',
          '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
   for f in paths:
    try:font=ImageFont.truetype(f,16);break
    except OSError:pass
   if font is None:font=ImageFont.load_default()
   for i,line in enumerate(lines):d.text((18,y0+i*21),line,font=font,fill=(255,255,255,255))
   im.save(png_path,format='PNG')
   return {'renderer':'PIL_LOCAL_AVAILABLE','path':str(png_path),'lines':len(lines)}
  except ImportError:pass
 _stdlib_png(lines,png_path)
 return {'renderer':'PYTHON_STDLIB_BITMAP_NO_EXTRA_PACKAGES','path':str(png_path),'lines':len(lines)}
