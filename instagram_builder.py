#!/usr/bin/env python3
import json, urllib.request, io, zipfile, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/okasama0767/kyodokonomall-data/main/"
START, END = "2026-11-21", "2026-11-23"
OUT = ROOT / "instagram_output"
OUT.mkdir(exist_ok=True)
for p in OUT.glob("*.jpg"): p.unlink()

def load_json(name):
    req = urllib.request.Request(BASE + name, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

mall = load_json("events.json")
housing_data = load_json("housing-events.json")
housing = housing_data.get("events", [])
def overlaps(e):
    d1 = str(e.get("date",""))[:10]
    d2 = str(e.get("endDate") or e.get("date",""))[:10]
    return bool(d1 and d2 and d1 <= END and d2 >= START)

def eligible(e):
    return (e.get("area") == "愛知県" and overlaps(e) and e.get("image")
            and e.get("imageStatus") == "official_detail_page"
            and any(k in str(e.get("place","")) for k in ("イオンモール","ららぽーと","ハウジング")))

rows = [e for e in mall + housing if eligible(e)]
unique = []
seen = set()
for e in rows:
    key = (e.get("id"), e.get("place"), e.get("title"))
    if key in seen: continue
    seen.add(key)
    # This is an exhibition, not a family/children event; keep the carousel child-focused.
    if e.get("title") == "防火作品展": continue
    unique.append(e)

# Prioritize family and children's events, while preserving all qualifying unique entries.
priority = ("アンパンマン","パウ・パトロール","すみっコ","こども","キッズ","親子","ワークショップ",
            "体験","トミカ","プラレール","ウッドパーク","こびと","縁日","マルシェ","チョーク","ピザ")
def score(e):
    title = str(e.get("title",""))
    return sum(10 for word in priority if word in title)
unique.sort(key=lambda e: (-score(e), str(e.get("date","")), str(e.get("place",""))))
events = unique[:20]
if len(events) != 20:
    raise SystemExit(f"公式画像付きの対象イベントが20件ありません: {len(events)}件。差し込み枠で代用せず停止します。")

def get_image(e):
    source = str(e["image"])
    if source.startswith("http://") or source.startswith("https://"):
        url = source
    else:
        url = BASE + source.lstrip("/")
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":str(e.get("officialUrl",""))})
    with urllib.request.urlopen(req, timeout=40) as r: data = r.read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width < 160 or im.height < 100: raise ValueError("official image too small")
    return im

loaded = []
for e in events:
    im = get_image(e)  # fail the entire build if any official image is unavailable
    loaded.append((e, im))

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
def font(size): return ImageFont.truetype(FONT_PATH, size)
W,H = 1080,1350
YELLOW=(255,224,74); RED=(197,38,34); DARK=(45,29,18); WHITE=(255,255,255); PALE=(255,249,231)
def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
def wrap(draw, text, f, maxw):
    lines=[]; line=""
    for ch in str(text):
        if draw.textlength(line+ch,font=f) <= maxw or not line: line += ch
        else: lines.append(line); line=ch
    if line: lines.append(line)
    return lines
def draw_text(draw, text, xy, size, maxw, fill=DARK, maxlines=3, spacing=6):
    f=font(size); x,y=xy
    for line in wrap(draw,text,f,maxw)[:maxlines]:
        draw.text((x,y),line,font=f,fill=fill,stroke_width=0)
        y += size+spacing
    return y
def frame():
    im=Image.new("RGB",(W,H),YELLOW); d=ImageDraw.Draw(im)
    rounded(d,(12,12,W-12,H-12),34,YELLOW,RED,18)
    return im,d

# Cover uses the established yellow / red visual identity.
im,d=frame()
rounded(d,(50,45,1030,260),35,RED)
draw_text(d,"今週末どこ行く？",(95,88),82,890,WHITE,1)
draw_text(d,"愛知県　イベントまとめ",(85,355),72,910,DARK,1)
rounded(d,(78,500,1002,635),28,WHITE,RED,7)
draw_text(d,"11/21（土）〜11/23（月・祝）",(110,535),46,860,RED,1)
draw_text(d,"イオンモール・ららぽーと・住宅展示場",(85,730),36,910,DARK,1)
draw_text(d,"家族で楽しめる週末イベント",(85,820),46,910,DARK,1)
draw_text(d,"20選！",(245,925),120,590,RED,1)
rounded(d,(110,1160,970,1265),24,RED)
draw_text(d,"公式告知画像で紹介",(180,1185),42,720,WHITE,1)
im.save(OUT/"01_cover.jpg",quality=95,optimize=True)

# Ten pages, two event cards per page. Each card's official artwork fills its image frame edge-to-edge.
for page in range(10):
    im,d=frame()
    rounded(d,(38,32,1042,145),24,RED)
    draw_text(d,"愛知県　今週末のイベントまとめ",(68,61),43,900,WHITE,1)
    draw_text(d,"11/21（土）〜11/23（月・祝）",(68,165),28,900,DARK,1)
    for slot in range(2):
        e,art=loaded[page*2+slot]
        top=220+slot*545; bottom=top+520
        rounded(d,(38,top,1042,bottom),25,WHITE,RED,7)
        # Image is cropped only to fill the allotted frame; no blank image placeholders.
        bx=(62,top+26,505,top+492)
        fitted=ImageOps.fit(art,(bx[2]-bx[0],bx[3]-bx[1]),method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
        im.paste(fitted,(bx[0],bx[1]))
        x=528; y=top+28; maxw=475
        y=draw_text(d,e.get("place",""),(x,y),25,maxw,RED,2)+7
        y=draw_text(d,e.get("title",""),(x,y),36,maxw,DARK,4)+9
        date=str(e.get("date",""))
        end=str(e.get("endDate") or date)
        ds=date[5:10].replace("-","/")
        de=end[5:10].replace("-","/")
        y=draw_text(d,ds+("〜"+de if de!=ds else ""), (x,y),27,maxw,RED,1)+8
        for label,key in (("時間","time"),("会場","location"),("料金","priceText")):
            val=str(e.get(key) or "")
            if val and val not in ("公式ページで確認","公式案内をご確認ください","料金は公式情報をご確認ください"):
                y=draw_text(d,label+"："+val,(x,y),22,maxw,DARK,2)+5
        rounded(d,(528,top+438,1015,top+485),12,YELLOW)
        draw_text(d,"詳細・参加条件は公式ページで確認",(545,top+447),18,450,DARK,1)
    draw_text(d,f"{page+1}/10",(950,1288),24,75,RED,1)
    im.save(OUT/f"{page+2:02d}_page_{page+1:02d}.jpg",quality=95,optimize=True)

zip_path=ROOT/"aichi_instagram_11_jpegs.zip"
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.glob("*.jpg")): z.write(p,p.name)
with zipfile.ZipFile(zip_path) as z:
    names=z.namelist()
    if len(names)!=11 or any(not n.lower().endswith(".jpg") for n in names) or z.testzip():
        raise SystemExit("ZIP validation failed")
# Verify every image frame is populated by a downloaded official image before saving.
print("OK: 20 official event images downloaded; 11 JPEG pages built; ZIP contains only 11 JPEGs.")
print(zip_path)
