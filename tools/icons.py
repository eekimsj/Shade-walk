import os
from PIL import Image, ImageDraw
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons'); os.makedirs(d, exist_ok=True)
S = 1024
def draw(maskable):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); g = ImageDraw.Draw(im)
    bg = (52, 56, 62, 255)
    if maskable: g.rectangle([0, 0, S, S], fill=bg)
    else: g.rounded_rectangle([0, 0, S - 1, S - 1], radius=220, fill=bg)
    pad = 150 if maskable else 0  # keep art inside the maskable safe zone
    sc = lambda v: pad + v * (S - 2 * pad) / S
    # sun
    g.ellipse([sc(600), sc(150), sc(860), sc(410)], fill=(242, 174, 72, 255))
    # building block and its cast shadow (shadow falls away from the sun, down-left)
    g.polygon([(sc(330), sc(420)), (sc(560), sc(420)), (sc(360), sc(860)), (sc(130), sc(860))], fill=(18, 19, 22, 255))
    g.rectangle([sc(330), sc(300), sc(560), sc(640)], fill=(122, 127, 136, 255))
    # walking path through the shade
    g.line([(sc(170), sc(930)), (sc(300), sc(700)), (sc(250), sc(560)), (sc(360), sc(420))], fill=(201, 84, 90, 255), width=int(56 * (S - 2 * pad) / S), joint='curve')
    return im
for name, size, m in [('icon-192.png', 192, False), ('icon-512.png', 512, False), ('icon-maskable-512.png', 512, True), ('apple-touch-icon.png', 180, True)]:
    draw(m).resize((size, size), Image.LANCZOS).save(os.path.join(d, name))
print('ok', os.listdir(d))
