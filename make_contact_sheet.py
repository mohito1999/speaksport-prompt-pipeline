from PIL import Image, ImageDraw
from pathlib import Path

render_dir = Path('tmp/rendered_report_verified')
ps = sorted(render_dir.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[1]))
ims = []
for p in ps:
    im = Image.open(p).convert('RGB')
    im.thumbnail((340, 440))
    c = Image.new('RGB', (360, 480), '#DDDDDD')
    c.paste(im, ((360-im.width)//2, 25))
    ImageDraw.Draw(c).text((10, 5), p.stem, fill='black')
    ims.append(c)
out = Image.new('RGB', (1080, 1920), 'white')
for i, im in enumerate(ims):
    out.paste(im, ((i % 3)*360, (i // 3)*480))
out.save(render_dir / 'contact_sheet.png')
