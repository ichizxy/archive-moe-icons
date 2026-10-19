"""Size-specific flat archive badges, including crisp native 16px lettering."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PAPER = '#FFF6DF'
INK = '#07294F'

# Hand-fitted 3x5 glyphs keep long labels complete at 16px without fuzzy
# fractional strokes. Short labels use a wider 4x7 grid.
TINY = {
    'A': '010/101/111/101/101', 'B': '110/101/110/101/110',
    'C': '011/100/100/100/011', 'D': '110/101/101/101/110',
    'E': '111/100/110/100/111', 'F': '111/100/110/100/100',
    'G': '011/100/101/101/011', 'H': '101/101/111/101/101',
    'I': '111/010/010/010/111', 'J': '001/001/001/101/010',
    'K': '101/101/110/101/101', 'L': '100/100/100/100/111',
    'M': '101/111/111/101/101', 'N': '101/111/111/111/101',
    'O': '010/101/101/101/010', 'P': '110/101/110/100/100',
    'Q': '010/101/101/111/011', 'R': '110/101/110/101/101',
    'S': '011/100/010/001/110', 'T': '111/010/010/010/010',
    'U': '101/101/101/101/111', 'V': '101/101/101/101/010',
    'W': '101/101/111/111/101', 'X': '101/101/010/101/101',
    'Y': '101/101/010/010/010', 'Z': '111/001/010/100/111',
    '0': '111/101/101/101/111', '1': '010/110/010/010/111',
    '2': '110/001/010/100/111', '3': '110/001/010/001/110',
    '4': '101/101/111/001/001', '5': '111/100/110/001/110',
    '6': '011/100/110/101/010', '7': '111/001/010/010/010',
    '8': '010/101/010/101/010', '9': '010/101/011/001/110',
    '.': '000/000/000/000/010', '+': '000/010/111/010/000',
    '_': '000/000/000/000/111', '-': '000/000/111/000/000',
}
PIXEL = {
    'A': '0110/1001/1001/1111/1001/1001/1001',
    'B': '1110/1001/1001/1110/1001/1001/1110',
    'C': '0111/1000/1000/1000/1000/1000/0111',
    'D': '1110/1001/1001/1001/1001/1001/1110',
    'E': '1111/1000/1000/1110/1000/1000/1111',
    'F': '1111/1000/1000/1110/1000/1000/1000',
    'G': '0111/1000/1000/1011/1001/1001/0111',
    'H': '1001/1001/1001/1111/1001/1001/1001',
    'I': '1111/0110/0110/0110/0110/0110/1111',
    'J': '0011/0001/0001/0001/0001/1001/0110',
    'K': '1001/1010/1100/1100/1010/1001/1001',
    'L': '1000/1000/1000/1000/1000/1000/1111',
    'M': '1001/1111/1111/1001/1001/1001/1001',
    'N': '1001/1101/1101/1011/1011/1001/1001',
    'O': '0110/1001/1001/1001/1001/1001/0110',
    'P': '1110/1001/1001/1110/1000/1000/1000',
    'Q': '0110/1001/1001/1001/1011/0110/0001',
    'R': '1110/1001/1001/1110/1010/1001/1001',
    'S': '0111/1000/1000/0110/0001/0001/1110',
    'T': '1111/0110/0110/0110/0110/0110/0110',
    'U': '1001/1001/1001/1001/1001/1001/0110',
    'V': '1001/1001/1001/1001/1001/0110/0110',
    'W': '1001/1001/1001/1001/1111/1111/1001',
    'X': '1001/1001/0110/0110/0110/1001/1001',
    'Y': '1001/1001/0110/0110/0110/0110/0110',
    'Z': '1111/0001/0010/0110/0100/1000/1111',
    '0': '0110/1001/1011/1011/1101/1001/0110',
    '1': '0110/1110/0110/0110/0110/0110/1111',
    '2': '0110/1001/0001/0010/0100/1000/1111',
    '3': '1110/0001/0001/0110/0001/0001/1110',
    '4': '1001/1001/1001/1111/0001/0001/0001',
    '5': '1111/1000/1000/1110/0001/0001/1110',
    '6': '0111/1000/1000/1110/1001/1001/0110',
    '7': '1111/0001/0010/0010/0100/0100/0100',
    '8': '0110/1001/1001/0110/1001/1001/0110',
    '9': '0110/1001/1001/0111/0001/0001/1110',
    '.': '0000/0000/0000/0000/0000/0110/0110',
    '+': '0000/0110/0110/1111/0110/0110/0000',
    '_': '0000/0000/0000/0000/0000/0000/1111',
    '-': '0000/0000/0000/1111/0000/0000/0000',
}


def label_lines(label, size):
    if size <= 32 and len(label) > 3:
        cut = (len(label)+1)//2
        return [label[:cut], label[cut:]]
    return [label]


def bitmap_line(label, tiny=False):
    glyphs = TINY if tiny else PIXEL
    width, height = (3, 5) if tiny else (4, 7)
    image = Image.new('L', (len(label)*(width+1)-1, height))
    draw = ImageDraw.Draw(image)
    for index, char in enumerate(label):
        for y, row in enumerate(glyphs[char].split('/')):
            for x, value in enumerate(row):
                if value == '1':
                    draw.point((index*(width+1)+x, y), fill=255)
    return image


def draw_text(image, lines, box, size):
    left, top, right, bottom = box
    width, height = right-left+1, bottom-top+1
    if size == 16:
        masks = [bitmap_line(line, tiny=len(lines) > 1) for line in lines]
        gap = 1
        total_h = sum(mask.height for mask in masks)+gap*(len(masks)-1)
        y = top+(height-total_h)//2
        if len(lines) == 1:
            factor = 1.4 if len(lines[0]) <= 2 else 1.0
            masks = [mask.resize((min(width, round(mask.width*factor)), 10 if len(lines[0]) <= 2 else 9), Image.Resampling.NEAREST) for mask in masks]
            y = top+(height-masks[0].height)//2
        for mask in masks:
            if mask.width > width:
                # User-defined eight-letter labels can use the full badge
                # width, keeping all letters instead of abbreviating them.
                mask = mask.resize((width, mask.height), Image.Resampling.NEAREST)
            x = left+(width-mask.width)//2
            image.paste(INK, (x, y, x+mask.width, y+mask.height), mask)
            y += mask.height+gap
        return
    candidates = (['C:/Windows/Fonts/ARIALNB.TTF'] if max(map(len, lines)) >= 3 else []) + ['C:/Windows/Fonts/tahomabd.ttf', 'C:/Windows/Fonts/segoeuib.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    font_path = next((p for p in candidates if Path(p).exists()), None)
    font = ImageFont.truetype(font_path, max(20, size*2)) if font_path else ImageFont.load_default()
    masks = []
    gap = max(1, round(size*.055)) if len(lines) > 1 else 0
    row_h = (height-gap*(len(lines)-1))//len(lines)
    for line in lines:
        bounds = font.getbbox(line)
        mask = Image.new('L', (bounds[2]-bounds[0]+2, bounds[3]-bounds[1]+2))
        ImageDraw.Draw(mask).text((1-bounds[0], 1-bounds[1]), line, fill=255, font=font)
        ratio = min(width/mask.width, row_h/mask.height)
        cap_fraction = .52 if len(lines) == 1 and len(line) > 3 else .60
        target_h = min(row_h, max(round(mask.height*ratio), round(size*cap_fraction)))
        mask = mask.resize((max(1, round(mask.width*ratio)), max(1, target_h)), Image.Resampling.LANCZOS)
        if size <= 32:
            # Keep every tiny stroke opaque and crisp, with no washed-out
            # gray antialiasing against the pale label.
            mask = mask.point(lambda value: 255 if value >= 108 else 0)
        masks.append(mask)
    total_h = sum(mask.height for mask in masks)+gap*(len(masks)-1)
    y = top+(height-total_h)//2
    for mask in masks:
        x = left+(width-mask.width)//2
        image.paste(INK, (x, y, x+mask.width, y+mask.height), mask)
        y += mask.height+gap


def render_compact(item, size):
    if not isinstance(size, int) or size < 16:
        raise ValueError('简洁图标尺寸至少为 16 像素。')
    image = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(image)
    frame = max(1, round(size*.065))
    radius = max(2, round(size*.11))
    draw.rounded_rectangle((0, 0, size-1, size-1), radius=radius, fill=item['body'])
    draw.rounded_rectangle((frame, frame, size-frame-1, size-frame-1), radius=max(1, radius-frame), fill=PAPER)
    if size >= 32 and item['hair'].upper() != item['body'].upper():
        draw.line((radius, 0, size-radius-1, 0), fill=item['hair'], width=max(1, round(size*.025)))
    # All available area goes to the label. No mascot, zipper, folds, shadow,
    # fabric grain or other illustration detail enters these frames.
    padding = 1 if size == 16 else max(frame+1, round(size*.12))
    draw_text(image, label_lines(item['label'], size), (padding, padding, size-padding-1, size-padding-1), size)
    return image
