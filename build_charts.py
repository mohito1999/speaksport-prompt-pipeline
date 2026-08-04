from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path('tmp/report_assets')
OUT.mkdir(parents=True, exist_ok=True)

GREEN = '#008F45'; DARK = '#006B3F'; MINT = '#DFF2E8'; GRAY = '#D9DEDC'
MID = '#63706A'; INK = '#17221D'; GOLD = '#D39A2C'; GRID = '#E7EBE9'
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'
FONT_B = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)

def canvas(w, h):
    im = Image.new('RGB', (w, h), 'white')
    return im, ImageDraw.Draw(im)

def title(d, text, y=30):
    d.text((50, y), text, font=font(31, True), fill=DARK)

def pct(v, total): return f'{100*v/total:.1f}%'

def save(im, name): im.save(OUT / name, quality=95)

# Call outcomes
im, d = canvas(1800, 470); title(d, 'Where the 523 calls went')
x0, y, full, h = 60, 130, 1680, 120
vals = [162, 267, 94]; labels = ['Not marked forwarded', 'Forwarded to golf shop', 'Forwarded elsewhere']
cols = [MINT, GREEN, GRAY]; x = x0
for v, label, col in zip(vals, labels, cols):
    w = round(full*v/523); d.rectangle((x, y, x+w, y+h), fill=col, outline='white', width=3)
    tc = 'white' if col == GREEN else INK
    txt = f'{v}\n{pct(v,523)}'; box = d.multiline_textbbox((0,0), txt, font=font(27,True), spacing=4, align='center')
    tw, th = box[2], box[3]; d.multiline_text((x+w/2-tw/2, y+h/2-th/2), txt, font=font(27,True), fill=tc, spacing=4, align='center')
    x += w
x = 85
for label, col in zip(labels, cols):
    d.rounded_rectangle((x, 330, x+26, 356), radius=4, fill=col)
    d.text((x+38, 326), label, font=font(23), fill=INK)
    x += 540
save(im, 'call_outcomes.png')

def horizontal_bars(name, chart_title, rows, total, maxv):
    im, d = canvas(1800, 1050); title(d, chart_title)
    left, right, top, gap, bh = 650, 1680, 120, 96, 50
    for i in range(0, maxv+1, 25):
        x = left + (right-left)*i/maxv
        d.line((x, top, x, 965), fill=GRID, width=2)
        d.text((x-12, 980), str(i), font=font(18), fill=MID)
    for idx, (label, v) in enumerate(rows):
        cy = top + idx*gap + 20
        d.text((45, cy-5), label, font=font(24), fill=INK)
        w = (right-left)*v/maxv
        col = GREEN if v >= 25 else MINT
        d.rounded_rectangle((left, cy, left+w, cy+bh), radius=8, fill=col)
        d.text((left+w+18, cy+7), f'{v}  ({pct(v,total)})', font=font(22, True), fill=DARK)
    save(im, name)

horizontal_bars('proshop_reasons.png', 'Why calls reached the golf shop (267 transfers)', [
    ('Immediate / unspecified routing',120), ('Booking modify or confirm',32),
    ('New tee time / availability',31), ('Cancellation',25),
    ('Course / current conditions',12), ('Lost and found',11),
    ('Group / multiple tee times',9), ('Rates / promotions',9),
    ('Other specialist needs',18)], 267, 125)

# Initiation share as proportional strip
im, d = canvas(1500, 650); title(d, 'Who initiated the golf-shop transfer?')
x0, y, full, h = 60, 150, 1380, 140
vals=[153,103,11]; labels=['Caller asked immediately','AI initiated','Caller escalated later']; cols=[GREEN,GOLD,GRAY]; x=x0
for v,label,col in zip(vals,labels,cols):
    w=round(full*v/267); d.rectangle((x,y,x+w,y+h),fill=col,outline='white',width=3)
    tc='white' if col in [GREEN,GOLD] else INK
    txt=f'{v}\n{pct(v,267)}'; box=d.multiline_textbbox((0,0),txt,font=font(29,True),spacing=4,align='center')
    d.multiline_text((x+w/2-box[2]/2,y+h/2-box[3]/2),txt,font=font(29,True),fill=tc,spacing=4,align='center')
    x+=w
for i,(label,col,v) in enumerate(zip(labels,cols,vals)):
    yy=355+i*75; d.rounded_rectangle((90,yy,120,yy+30),radius=5,fill=col)
    d.text((145,yy-2),f'{label}: {v} ({pct(v,267)})',font=font(25),fill=INK)
save(im,'initiation_donut.png')

horizontal_bars('opportunity_levers.png', 'Primary reduction lever for golf-shop transfers', [
    ('Caller adoption / AI-first framing',131), ('Product or workflow capability',76),
    ('Conversation / booking UX',24), ('Knowledge and live data',21),
    ('Appropriate specialist routing',15)], 267, 140)

# Week stability
im,d=canvas(1400,700); title(d,'Golf-shop transfer rate remained flat')
base=590; xvals=[350,850]; vals=[51.5,50.8]; labs=['21-27 Jul','28 Jul-3 Aug']
for i in range(0,61,10):
    yy=base-(i/60)*420; d.line((160,yy,1280,yy),fill=GRID,width=2); d.text((85,yy-12),f'{i}%',font=font(19),fill=MID)
for x,v,lab,col in zip(xvals,vals,labs,[GREEN,DARK]):
    hh=(v/60)*420; d.rounded_rectangle((x,base-hh,x+260,base),radius=10,fill=col)
    d.text((x+74,base-hh-48),f'{v:.1f}%',font=font(29,True),fill=DARK)
    d.text((x+58,base+25),lab,font=font(24),fill=INK)
save(im,'weekly_rate.png')
