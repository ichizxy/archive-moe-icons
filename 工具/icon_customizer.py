"""Offline archive-girl icon customizer. No network or model API is required."""
from pathlib import Path
import argparse
import colorsys
import copy
import datetime
import json
import re
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Also support importing this file through importlib from external scripts.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from compact_icons import render_compact

HERE = Path(__file__).resolve().parent
DEFAULT_PALETTE = HERE.parent/'配色方案'/'默认配色.json'
MASTER_PATH = HERE.parent/'模板素材'/'无字底图.png'
EXPORTS_DIR = HERE.parent/'导出图标'
SIZES = [16, 24, 32, 48, 64, 128, 256]
STYLES = {'adaptive': '自动切换（推荐）', 'compact': '全部简洁文字', 'character': '全部角色图标'}
NAVY = '#07294F'
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
SAFE_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,29}$')
LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+_-]{0,7}$')


def find_font(bold=True, chinese=False):
    if chinese:
        candidates = ['C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc']
    else:
        candidates = ['C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/segoeuib.ttf']
    candidates += ['C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    return next((p for p in candidates if Path(p).exists()), None)


def parse_hex(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError('颜色必须是 #RRGGBB 格式，例如 #3978F6。')
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def validate_palette(data):
    if not isinstance(data, list) or not data or len(data) > 200:
        raise ValueError('配色文件应包含 1～200 个格式。')
    clean, ids = [], set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('配色条目必须是对象。')
        key = str(item.get('id', '')).lower()
        label = str(item.get('label', '')).upper()
        if not SAFE_ID.fullmatch(key) or key in ids:
            raise ValueError('文件名需唯一，仅使用英文字母、数字、下划线和短横线。')
        if not LABEL.fullmatch(label):
            raise ValueError('标签需为 1～8 个英文字母、数字或 . + _ -。')
        hair, body = item.get('hair', ''), item.get('body', '')
        parse_hex(hair)
        parse_hex(body)
        ids.add(key)
        extensions = item.get('extensions', [key])
        if not isinstance(extensions, list) or any(not isinstance(x, str) for x in extensions):
            raise ValueError('extensions 必须是字符串列表。')
        clean.append({'id': key, 'label': label, 'hair': hair.upper(), 'body': body.upper(), 'extensions': extensions})
    return clean


def read_palette(path):
    return validate_palette(json.loads(Path(path).read_text(encoding='utf-8-sig')))


class Renderer:
    def __init__(self, master=None, style='adaptive'):
        if style not in STYLES:
            raise ValueError('未知图标风格。')
        self.style = style
        self.master_path = Path(master or MASTER_PATH)
        with Image.open(self.master_path) as im:
            self.master = im.convert('RGBA')
        self.raw = np.array(self.master)
        colors = self.raw[:, :, :3].astype(np.float32)
        r, g, b = colors[:, :, 0], colors[:, :, 1], colors[:, :, 2]
        # The AI-prepared master has a blank label. Its blue hair and pouch
        # are the two user-editable color regions; navy ink is left intact.
        self.color_region = (b > 96) & (b > r*1.24) & (b > g*1.09) & (self.raw[:, :, 3] > 0)
        yy = np.indices(self.raw.shape[:2])[0]
        self.hair_region = self.color_region & (yy < self.master.height*.345)
        self.body_region = self.color_region & ~self.hair_region
        self.source_v = np.max(colors, axis=2)/255.0
        self.font_path = find_font()

    def render(self, item, size=1024):
        item = validate_palette([item])[0]
        if self.style == 'compact' or (self.style == 'adaptive' and size <= 48):
            return render_compact(item, size)
        arr = self.raw.copy()
        for region, requested in [(self.hair_region, item['hair']), (self.body_region, item['body'])]:
            target = np.array(parse_hex(requested), dtype=np.float32)/255.0
            h, sat, value = colorsys.rgb_to_hsv(*target)
            # Preserve the approved master's restrained shading and alpha.
            shades = np.clip(self.source_v[region]/.95, .35, 1.06)
            color_at_full_v = np.array(colorsys.hsv_to_rgb(h, sat, 1.0))
            arr[:, :, :3][region] = np.clip(shades[:, None]*value*color_at_full_v[None, :]*255, 0, 255).astype(np.uint8)
        result = Image.fromarray(arr)
        w, h = result.size
        font = ImageFont.truetype(self.font_path, round(h*.48)) if self.font_path else ImageFont.load_default()
        bounds = font.getbbox(item['label'])
        tw, th = bounds[2]-bounds[0], bounds[3]-bounds[1]
        text = Image.new('RGBA', (tw+8, th+8))
        ImageDraw.Draw(text).text((4-bounds[0], 4-bounds[1]), item['label'], font=font, fill=NAVY)
        target_h = round(h*.302)
        target_w = min(round(w*.523), round(text.width/text.height*target_h))
        text = text.resize((target_w, target_h), Image.Resampling.LANCZOS)
        result.alpha_composite(text, (round(w*.548-target_w/2), round(h*.652-target_h/2)))
        return result if result.size == (size, size) else result.resize((size, size), Image.Resampling.LANCZOS)


def save_icon(image, png_path, ico_path, frames=None):
    png_path, ico_path = Path(png_path), Path(ico_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path)
    if frames is not None:
        frames = list(frames)
        if sorted(frame.size for frame in frames) != sorted((n, n) for n in SIZES):
            raise ValueError('ICO 必须包含全部 7 个独立尺寸。')
    image.save(ico_path, format='ICO', sizes=[(n, n) for n in SIZES], append_images=frames or [])


def contact_sheet(images, palette, path, title='压缩包娘 · 自动尺寸切换'):
    cols, cw, ch, margin = 6, 232, 268, 48
    rows = (len(images)+cols-1)//cols
    board = Image.new('RGB', (cols*cw+margin*2, rows*ch+170), '#F2F4F8')
    draw = ImageDraw.Draw(board)
    cn = find_font(chinese=True)
    head = ImageFont.truetype(cn, 34) if cn else ImageFont.load_default()
    regular = ImageFont.truetype(find_font(), 17)
    small = ImageFont.truetype(find_font(), 12)
    draw.text((margin, 32), title, font=head, fill='#172C4B')
    draw.text((margin, 88), f'{len(palette)} FORMATS  /  PNG + ICO  /  NATIVE SMALL-SIZE LETTERING', font=regular, fill='#6B7890')
    for i, (image, item) in enumerate(zip(images, palette)):
        x, y = margin+(i%cols)*cw, 140+(i//cols)*ch
        draw.rounded_rectangle((x+8, y, x+cw-8, y+ch-18), radius=18, fill='white')
        thumb = image.resize((174, 174), Image.Resampling.LANCZOS)
        board.paste(thumb, (x+(cw-174)//2, y+16), thumb)
        label = '.'+item['id']
        box = draw.textbbox((0, 0), label, font=regular)
        draw.text((x+(cw-(box[2]-box[0]))/2, y+200), label, font=regular, fill='#263D5A')
        color_caption = item['hair']+' / '+item['body']
        box = draw.textbbox((0, 0), color_caption, font=small)
        draw.text((x+(cw-(box[2]-box[0]))/2, y+228), color_caption, font=small, fill='#8290A3')
    board.save(path)


def export_batch(renderer, palette, output, progress=None, make_zip=True):
    palette = validate_palette(palette)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    images = []
    for index, item in enumerate(palette):
        im = renderer.render(item)
        save_icon(im, output/'png'/f"{item['id']}.png", output/'ico'/f"{item['id']}.ico", frames=[renderer.render(item, n) for n in SIZES])
        images.append(im)
        if progress:
            progress(index+1, len(palette))
    (output/'palette.json').write_text(json.dumps(palette, ensure_ascii=False, indent=2), encoding='utf-8')
    (output/'rendering.json').write_text(json.dumps({'style': renderer.style, 'sizes': SIZES}, ensure_ascii=False, indent=2), encoding='utf-8')
    contact_sheet(images, palette, output/'preview.png', title='压缩包娘 · '+STYLES[renderer.style])
    if make_zip:
        with zipfile.ZipFile(str(output)+'.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in sorted(output.rglob('*')):
                if p.is_file():
                    z.write(p, Path(output.name)/p.relative_to(output))
    return output


class App:
    def __init__(self, root, renderer, palette):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root, self.renderer = root, renderer
        self.palette = copy.deepcopy(palette)
        self.index, self.pending = 0, None
        root.title('压缩包娘 · 批量图标工具')
        root.geometry('1060x840')
        root.minsize(920, 790)
        root.configure(bg='#F2F4F8')
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('TButton', padding=(10, 7))
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TEntry', padding=4)
        header = tk.Frame(root, bg='#F2F4F8')
        header.pack(fill='x', padx=28, pady=(22, 12))
        tk.Label(header, text='压缩包娘', font=('Microsoft YaHei UI', 24, 'bold'), bg='#F2F4F8', fg='#172C4B').pack(anchor='w')
        tk.Label(header, text='小尺寸简洁、大尺寸精细，由 Windows 按显示尺寸自动选取。', font=('Microsoft YaHei UI', 10), bg='#F2F4F8', fg='#64748B').pack(anchor='w', pady=(4, 0))
        main = tk.Frame(root, bg='#F2F4F8')
        main.pack(fill='both', expand=True, padx=28, pady=12)
        left = ttk.Frame(main)
        left.pack(side='left', fill='y', padx=(0, 18))
        ttk.Label(left, text='格式列表').pack(anchor='w', pady=(0, 8))
        self.listbox = tk.Listbox(left, width=17, height=24, font=('Segoe UI', 11), relief='flat', selectbackground='#3578EB', activestyle='none', exportselection=False)
        self.listbox.pack(fill='y', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.select)
        row = ttk.Frame(left)
        row.pack(fill='x', pady=(10, 0))
        ttk.Button(row, text='添加', command=self.add).pack(side='left')
        ttk.Button(row, text='删除', command=self.remove).pack(side='left', padx=(6, 0))
        middle = tk.Frame(main, bg='#F2F4F8')
        middle.pack(side='left', fill='both', expand=True)
        self.style_display = tk.StringVar(value=STYLES[renderer.style])
        style_picker = ttk.Combobox(middle, state='readonly', textvariable=self.style_display, values=list(STYLES.values()), width=29)
        style_picker.pack(pady=(0, 6))
        style_picker.bind('<<ComboboxSelected>>', self.change_style)
        self.preview = tk.Canvas(middle, width=360, height=360, highlightthickness=0, bg='white')
        self.preview.pack(pady=(10, 12), expand=True)
        self.dark = tk.BooleanVar(value=False)
        ttk.Checkbutton(middle, text='深色背景预览', variable=self.dark, command=self.redraw).pack(anchor='center')
        self.native = tk.Canvas(middle, width=360, height=76, highlightthickness=0, bg='#F2F4F8')
        self.native.pack(pady=(10, 0))
        ttk.Label(middle, text='原生预览：16 / 24 / 32 / 48 / 64 px').pack(anchor='center')
        right = ttk.Frame(main, width=240)
        right.pack(side='right', fill='y', padx=(20, 0))
        right.pack_propagate(False)
        self.key, self.label = tk.StringVar(), tk.StringVar()
        self.hair, self.body = tk.StringVar(), tk.StringVar()
        for title, var in [('文件名（不含扩展名）', self.key), ('图标上的格式标签', self.label)]:
            ttk.Label(right, text=title).pack(anchor='w', pady=(9, 4))
            ttk.Entry(right, textvariable=var).pack(fill='x')
        self.color_buttons = {}
        for title, var, field in [('角色发色 / 简洁版点缀色', self.hair, 'hair'), ('包体 / 格式主题色', self.body, 'body')]:
            ttk.Label(right, text=title).pack(anchor='w', pady=(18, 5))
            line = ttk.Frame(right)
            line.pack(fill='x')
            button = tk.Button(line, text='选色', width=5, relief='flat', command=lambda f=field: self.pick_color(f))
            button.pack(side='left', padx=(0, 8))
            self.color_buttons[field] = button
            ttk.Entry(line, textvariable=var, width=13).pack(side='left', fill='x', expand=True)
        ttk.Button(right, text='包体颜色跟随发色', command=lambda: self.body.set(self.hair.get())).pack(fill='x', pady=(12, 0))
        ttk.Separator(right).pack(fill='x', pady=20)
        ttk.Button(right, text='导出当前 PNG + ICO', command=self.export_current).pack(fill='x', pady=4)
        ttk.Button(right, text='批量导出整套 + ZIP', command=self.export_all).pack(fill='x', pady=4)
        ttk.Button(right, text='保存配色方案', command=self.save_palette).pack(fill='x', pady=(20, 4))
        ttk.Button(right, text='载入配色方案', command=self.load_palette).pack(fill='x', pady=4)
        ttk.Button(right, text='恢复默认配色', command=self.restore).pack(fill='x', pady=4)
        self.status = tk.StringVar(value='就绪 · 离线运行 · 不会修改系统文件关联')
        ttk.Label(root, textvariable=self.status, wraplength=980).pack(fill='x', padx=28, pady=(4, 18))
        self._loading = False
        for var in [self.key, self.label, self.hair, self.body]:
            var.trace_add('write', self.changed)
        self.refresh_list()
        self.load_fields(0)

    def refresh_list(self):
        self.listbox.delete(0, 'end')
        for item in self.palette:
            self.listbox.insert('end', item['label']+'   .'+item['id'])
        self.listbox.selection_set(self.index)

    def load_fields(self, index):
        self._loading = True
        self.index = index
        item = self.palette[index]
        for name in ['key', 'label', 'hair', 'body']:
            getattr(self, name).set(item['id' if name == 'key' else name])
        self._loading = False
        self.redraw()

    def current(self):
        item = dict(self.palette[self.index])
        item.update(id=self.key.get().strip().lower(), label=self.label.get().strip().upper(), hair=self.hair.get().strip(), body=self.body.get().strip())
        clean = validate_palette([item])[0]
        if any(i != self.index and x['id'] == clean['id'] for i, x in enumerate(self.palette)):
            raise ValueError('这个文件名已被其他格式使用。')
        return clean

    def commit(self):
        item = self.current()
        self.palette[self.index] = item
        self.listbox.delete(self.index)
        self.listbox.insert(self.index, item['label']+'   .'+item['id'])
        self.listbox.selection_set(self.index)
        return item

    def changed(self, *_):
        if self._loading:
            return
        if self.pending:
            self.root.after_cancel(self.pending)
        self.pending = self.root.after(220, self.redraw)

    def change_style(self, _event=None):
        self.renderer.style = next(key for key, label in STYLES.items() if label == self.style_display.get())
        self.redraw()

    def redraw(self):
        self.pending = None
        try:
            item = self.commit()
            rendered = self.renderer.render(item, 360)
        except ValueError as e:
            self.status.set(str(e))
            return
        bg = '#182E4D' if self.dark.get() else '#FFFFFF'
        self.preview.configure(bg=bg)
        self.preview.delete('all')
        self.photo = ImageTk.PhotoImage(rendered)
        self.preview.create_image(180, 180, image=self.photo)
        self.native.delete('all')
        self.native_photos = []
        x = 14
        for size in SIZES[:5]:
            photo = ImageTk.PhotoImage(self.renderer.render(item, size))
            self.native_photos.append(photo)
            self.native.create_image(x, 36, image=photo, anchor='w')
            x += size+22
        for field in ['hair', 'body']:
            self.color_buttons[field].configure(bg=item[field], fg='white' if sum(parse_hex(item[field])) < 380 else '#132A48')
        self.status.set(f"{item['label']} · 发色 {item['hair']} · 包体 {item['body']} · 预览已更新")

    def select(self, _event):
        sel = self.listbox.curselection()
        if not sel or sel[0] == self.index:
            return
        old = self.index
        try:
            self.commit()
        except ValueError as e:
            self.status.set(str(e))
            self.listbox.selection_clear(0, 'end')
            self.listbox.selection_set(old)
            return
        self.listbox.selection_clear(0, 'end')
        self.listbox.selection_set(sel[0])
        self.load_fields(sel[0])

    def pick_color(self, field):
        from tkinter import colorchooser
        result = colorchooser.askcolor(color=getattr(self, field).get(), title='选择发色' if field == 'hair' else '选择包体颜色', parent=self.root)
        if result[1]:
            getattr(self, field).set(result[1].upper())

    def add(self):
        try:
            self.commit()
            n = 1
            while any(x['id'] == f'new{n}' for x in self.palette):
                n += 1
            self.palette.append({'id': f'new{n}', 'label': 'NEW', 'hair': '#3978F6', 'body': '#3978F6', 'extensions': []})
            self.index = len(self.palette)-1
            self.refresh_list()
            self.load_fields(self.index)
        except Exception as e:
            self.error(e)

    def remove(self):
        if len(self.palette) == 1:
            self.status.set('至少保留一个格式。')
            return
        del self.palette[self.index]
        self.index = max(0, self.index-1)
        self.refresh_list()
        self.load_fields(self.index)

    def error(self, error):
        from tkinter import messagebox
        messagebox.showerror('未完成', str(error), parent=self.root)

    def export_current(self):
        from tkinter import filedialog
        try:
            item = self.commit()
            folder = filedialog.askdirectory(initialdir=str(EXPORTS_DIR), title='选择 PNG 和 ICO 保存文件夹', parent=self.root)
            if folder:
                out = Path(folder)
                save_icon(self.renderer.render(item), out/'png'/f"{item['id']}.png", out/'ico'/f"{item['id']}.ico", frames=[self.renderer.render(item, n) for n in SIZES])
                self.status.set(f'已导出 PNG 和多尺寸 ICO：{out}')
        except Exception as e:
            self.error(e)

    def export_all(self):
        from tkinter import filedialog
        try:
            self.commit()
            folder = filedialog.askdirectory(initialdir=str(EXPORTS_DIR), title='选择整套图标的输出目录', parent=self.root)
            if not folder:
                return
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            out = Path(folder)/('archive-moe-'+stamp)
            def progress(done, total):
                self.status.set(f'正在批量导出 {done}/{total}…')
                self.root.update_idletasks()
            export_batch(self.renderer, self.palette, out, progress)
            self.status.set(f'已导出 {len(self.palette)} 个格式、预览图、配色方案和 ZIP：{out}')
        except Exception as e:
            self.error(e)

    def save_palette(self):
        from tkinter import filedialog
        try:
            self.commit()
            path = filedialog.asksaveasfilename(initialdir=str(DEFAULT_PALETTE.parent), title='保存配色方案', defaultextension='.json', initialfile='my-palette.json', filetypes=[('JSON 配色', '*.json')], parent=self.root)
            if path:
                Path(path).write_text(json.dumps(self.palette, ensure_ascii=False, indent=2), encoding='utf-8')
                self.status.set('配色方案已保存。')
        except Exception as e:
            self.error(e)

    def load_palette(self):
        from tkinter import filedialog
        try:
            path = filedialog.askopenfilename(initialdir=str(DEFAULT_PALETTE.parent), title='载入配色方案', filetypes=[('JSON 配色', '*.json')], parent=self.root)
            if path:
                self.palette, self.index = read_palette(path), 0
                self.refresh_list()
                self.load_fields(0)
        except Exception as e:
            self.error(e)

    def restore(self):
        self.palette, self.index = read_palette(DEFAULT_PALETTE), 0
        self.refresh_list()
        self.load_fields(0)


def main():
    parser = argparse.ArgumentParser(description='离线批量生成可自定义颜色的压缩包娘图标')
    parser.add_argument('--palette', type=Path, default=DEFAULT_PALETTE)
    parser.add_argument('--export', type=Path, help='不打开窗口，按 JSON 配色批量导出')
    parser.add_argument('--style', choices=list(STYLES), default='adaptive', help='adaptive 自动切换（默认）；compact 全部简洁文字；character 全部角色')
    parser.add_argument('--smoke-ui', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    palette, renderer = read_palette(args.palette), Renderer(style=args.style)
    if args.export:
        export_batch(renderer, palette, args.export)
        print(f'Exported {len(palette)} formats to {args.export}')
        return
    import tkinter as tk
    root = tk.Tk()
    if args.smoke_ui:
        root.withdraw()
    app = App(root, renderer, palette)
    if args.smoke_ui:
        root.update()
        app.hair.set('#FF66AA')
        app.body.set('#22AA88')
        app.redraw()
        root.update()
        for style, display in STYLES.items():
            app.style_display.set(display)
            app.change_style()
            root.update()
        root.destroy()
        print('UI initialized; color updates and all three rendering styles passed.')
    else:
        root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--export' in sys.argv or '--smoke-ui' in sys.argv:
            raise
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror('图标工具启动失败', str(error))
            root.destroy()
        except Exception:
            raise
