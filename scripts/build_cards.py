#!/usr/bin/env python3
"""
Aurora-style GitHub profile cards (animated SVG, live data).

Usage:
  GITHUB_TOKEN=... python scripts/build_cards.py            # real data
  python scripts/build_cards.py --demo                      # offline preview data

Writes: cards/scan.svg, cards/signal.svg, cards/activity.svg,
        cards/languages.svg, cards/work.svg
"""
import base64, datetime as dt, io, json, math, os, random, sys, urllib.request
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cards")
CFG = json.load(open(os.path.join(ROOT, "profile.config.json"), encoding="utf-8"))
USER = CFG["username"]
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DEMO = "--demo" in sys.argv

# ---------------------------------------------------------------- theme
BG0, BG1 = "#06110f", "#0a1f1b"
EDGE = "#2dd4bf"
ACC = "#5eead4"
ACC2 = "#99f6e4"
TXT = "#d7fff6"
DIM = "#6f9b93"
FONT = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"
SANS = "Inter,'Segoe UI',Helvetica,Arial,sans-serif"
LEVELS = ["#0f2a26", "#0e4d43", "#13806d", "#22b39a", "#5eead4"]
LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "CSS": "#663399", "HTML": "#e34c26", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Go": "#00ADD8", "Rust": "#dea584", "PLpgSQL": "#336790", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "C++": "#f34b7d", "C#": "#178600", "Dart": "#00B4AB",
    "Vue": "#41b883", "PHP": "#4F5D95", "Swift": "#F05138", "SCSS": "#c6538c",
}


# ---------------------------------------------------------------- data
def api(path, body=None):
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-cards")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def load_live():
    user = api(f"/users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r.get("fork")]
    langs, repo_langs = {}, {}
    for r in own:
        try:
            l = api(f"/repos/{USER}/{r['name']}/languages")
        except Exception:
            l = {}
        repo_langs[r["name"]] = l
        for k, v in l.items():
            langs[k] = langs.get(k, 0) + v
    q = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}}}}"""
    try:
        cal = api("/graphql", {"query": q, "variables": {"login": USER}})
        cal = cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        weeks = [[d["contributionCount"] for d in w["contributionDays"]] for w in cal["weeks"]]
        total = cal["totalContributions"]
    except Exception as e:
        print("contribution calendar unavailable:", e)
        weeks, total = [[0] * 7 for _ in range(53)], 0
    try:
        avatar = fetch_bytes(user["avatar_url"] + "&s=160" if "?" in user["avatar_url"] else user["avatar_url"] + "?s=160")
    except Exception:
        avatar = None
    return {
        "name": CFG.get("name") or user.get("name") or USER,
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", 0),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "langs": langs, "repo_langs": repo_langs,
        "total": total, "weeks": weeks, "avatar": avatar,
    }


def load_demo():
    random.seed(4)
    weeks = []
    for w in range(53):
        base = 0.25 + 0.6 * (0.5 + 0.5 * math.sin(w / 6))
        weeks.append([max(0, int(random.gauss(base * 8, 3))) if random.random() < base else 0 for _ in range(7)])
    return {
        "name": CFG["name"], "followers": 24, "public_repos": 10, "stars": 37,
        "langs": {"TypeScript": 61, "JavaScript": 22, "Python": 6, "CSS": 7, "PLpgSQL": 4},
        "repo_langs": {"inhayat-uz": {"TypeScript": 92, "CSS": 6, "PLpgSQL": 2},
                       "smart-monitor": {"JavaScript": 64, "TypeScript": 33, "CSS": 3}},
        "total": sum(map(sum, weeks)), "weeks": weeks, "avatar": None,
    }


# ---------------------------------------------------------------- svg helpers
def defs(extra=""):
    return f"""<defs>
  <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0d2a25"/><stop offset=".55" stop-color="#081a17"/><stop offset="1" stop-color="#0b2622"/>
  </linearGradient>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{ACC}" stop-opacity=".9"/><stop offset=".5" stop-color="{EDGE}" stop-opacity=".25"/><stop offset="1" stop-color="{ACC}" stop-opacity=".7"/>
  </linearGradient>
  <radialGradient id="aur" cx=".15" cy="0" r="1">
    <stop offset="0" stop-color="{EDGE}" stop-opacity=".22"/><stop offset="1" stop-color="{EDGE}" stop-opacity="0"/>
  </radialGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>
  {extra}
</defs>"""


def frame(w, h, inner, extra_defs="", label=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
{defs(extra_defs)}
<rect x="6" y="6" width="{w-12}" height="{h-12}" rx="22" fill="{EDGE}" opacity=".10" filter="url(#glow)"/>
<rect x="8" y="8" width="{w-16}" height="{h-16}" rx="20" fill="url(#panel)"/>
<rect x="8" y="8" width="{w-16}" height="{h-16}" rx="20" fill="url(#aur)"/>
<rect x="8.5" y="8.5" width="{w-17}" height="{h-17}" rx="20" fill="none" stroke="url(#edge)" stroke-width="1.4"/>
{inner}
</svg>"""


def txt(x, y, s, size=14, fill=TXT, weight=400, font=FONT, anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>'


def fmt(n):
    return f"{n:,}"


# ---------------------------------------------------------------- avatar → dot matrix
def avatar_grid(png, n=44):
    """Return n x n brightness grid (0..1) or a generated silhouette."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(png)).convert("L")
        img = ImageOps.fit(img, (n, n))
        img = ImageOps.autocontrast(img)
        return [[img.getpixel((x, y)) / 255 for x in range(n)] for y in range(n)]
    except Exception:
        g = []
        for y in range(n):
            row = []
            for x in range(n):
                cx, cy = x - n / 2, y - n / 2
                head = (cx / 9.5) ** 2 + ((y - n * .38) / 11) ** 2 <= 1
                body = y > n * .66 and abs(cx) < (y - n * .55) * 1.3
                v = 0.15 + 0.1 * math.sin(x * .7 + y * .4)
                if head: v = 0.9 - 0.25 * ((cx / 9.5) ** 2)
                if body: v = 0.75
                row.append(max(0, min(1, v)))
            g.append(row)
        return g


# ---------------------------------------------------------------- cards
def card_scan(d):
    W, H = 1000, 440
    n = 44
    grid = avatar_grid(d["avatar"], n)
    ox, oy, cell = 52, 116, 6.6
    R = n * cell / 2
    cxm, cym = ox + R, oy + R
    dots = []
    for y in range(n):
        for x in range(n):
            px_, py_ = ox + x * cell + cell / 2, oy + y * cell + cell / 2
            if (px_ - cxm) ** 2 + (py_ - cym) ** 2 > (R - 2) ** 2:
                continue
            v = grid[y][x]
            r = 0.6 + v * 2.4
            op = 0.25 + v * 0.75
            dots.append(f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="{r:.2f}" fill="{ACC}" fill-opacity="{op:.2f}"/>')
    portrait = "\n".join(dots)
    rows = [
        ("Subject", d["name"]), ("Handle", f"@{USER}"), ("Role", CFG["role"]),
        ("Status", CFG["status"]),
        ("Languages", ", ".join(k for k, _ in sorted(d["langs"].items(), key=lambda kv: -kv[1])[:3]) or "-"),
        ("Repositories", fmt(d["public_repos"])), ("Contributions", fmt(d["total"])),
        ("Stars", fmt(d["stars"])), ("Followers", fmt(d["followers"])),
        ("Active days", fmt(sum(1 for w in d["weeks"] for c in w if c > 0))),
        ("Contact", CFG["contact"]),
    ]
    info = []
    for i, (k, v) in enumerate(rows):
        y = 150 + i * 24
        b = 0.6 + i * 0.12
        info.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{b:.2f}s" dur=".35s" fill="freeze"/>'
                    + txt(436, y, k, 13, DIM) + txt(590, y, v, 13, TXT) + "</g>")
        info.append(f'<line x1="436" y1="{y+8}" x2="948" y2="{y+8}" stroke="{EDGE}" stroke-opacity=".08"/>')
    inner = f"""
<circle cx="30" cy="34" r="5" fill="#ff5f57"/><circle cx="48" cy="34" r="5" fill="#febc2e"/><circle cx="66" cy="34" r="5" fill="#28c840"/>
{txt(W/2, 39, f"{USER.lower()}@github:~$ ./profile-scan --live", 13, DIM, anchor="middle")}
<circle cx="{W-48}" cy="34" r="4" fill="{ACC}"><animate attributeName="opacity" values="1;.2;1" dur="1.6s" repeatCount="indefinite"/></circle>
{txt(W-58, 39, "LIVE", 11, ACC, 700, anchor="end")}
<line x1="8" y1="58" x2="{W-8}" y2="58" stroke="{EDGE}" stroke-opacity=".18"/>

<rect x="34" y="76" width="366" height="340" rx="14" fill="#06130f" stroke="{EDGE}" stroke-opacity=".28"/>
{txt(52, 100, "VISUAL.MAP", 12, ACC, 700, extra='letter-spacing="2"')}
{txt(382, 100, f"{n}x{n}", 11, DIM, anchor="end")}
<clipPath id="reveal"><rect x="34" y="{oy}" width="366" height="0">
  <animate attributeName="height" from="0" to="{n*cell+4}" dur="2.2s" fill="freeze" calcMode="spline" keySplines=".4 0 .2 1" keyTimes="0;1"/>
</rect></clipPath>
<g clip-path="url(#reveal)">{portrait}</g>
<rect x="40" y="{oy}" width="354" height="3" fill="{ACC2}" filter="url(#soft)" opacity=".9">
  <animate attributeName="y" values="{oy};{oy+n*cell};{oy}" dur="4.5s" begin="2.2s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="0;.9;.9;0" keyTimes="0;.05;.95;1" dur="4.5s" begin="2.2s" repeatCount="indefinite"/>
</rect>

<rect x="418" y="76" width="548" height="340" rx="14" fill="#06130f" stroke="{EDGE}" stroke-opacity=".28"/>
{txt(436, 100, "SYSTEM.INFO", 12, ACC, 700, extra='letter-spacing="2"')}
{txt(948, 100, "updated " + dt.date.today().isoformat(), 11, DIM, anchor="end")}
{''.join(info)}
"""
    return frame(W, H, inner, label=f"{d['name']} profile scan")


def card_signal(d):
    W, H = 1000, 200
    if d["avatar"]:
        b64 = base64.b64encode(d["avatar"]).decode()
        av = f'<image x="52" y="52" width="96" height="96" clip-path="url(#avc)" href="data:image/png;base64,{b64}" xlink:href="data:image/png;base64,{b64}"/>'
    else:
        av = f'<rect x="52" y="52" width="96" height="96" fill="#0e4d43" clip-path="url(#avc)"/>' + txt(100, 114, "".join(w[0] for w in d["name"].split()[:2]), 34, ACC2, 700, SANS, "middle")
    extra = '<clipPath id="avc"><circle cx="100" cy="100" r="48"/></clipPath>'
    stats = [("STARS", d["stars"]), ("REPOS", d["public_repos"]), ("FOLLOWERS", d["followers"])]
    st = []
    for i, (k, v) in enumerate(stats):
        x = 700 + i * 100
        st.append(txt(x, 108, fmt(v), 30, ACC2, 800, SANS, "middle") + txt(x, 132, k, 11, DIM, 600, anchor="middle", extra='letter-spacing="1.5"'))
    inner = f"""
<circle cx="100" cy="100" r="56" fill="none" stroke="{ACC}" stroke-opacity=".5" stroke-width="2" stroke-dasharray="6 8">
  <animateTransform attributeName="transform" type="rotate" from="0 100 100" to="360 100 100" dur="18s" repeatCount="indefinite"/>
</circle>
{av}
{txt(176, 78, "@" + USER.lower(), 14, DIM)}
{txt(176, 116, d["name"], 34, TXT, 800, SANS)}
{txt(176, 146, CFG["role"], 15, ACC, 500)}
<line x1="640" y1="56" x2="640" y2="144" stroke="{EDGE}" stroke-opacity=".2"/>
{''.join(st)}
"""
    return frame(W, H, inner, extra, label="Profile signal")


def card_activity(d):
    weeks = d["weeks"][-53:]
    W, H = 1000, 262
    cell, gap = 14, 3.6
    gx0 = (W - len(weeks) * (cell + gap)) / 2
    gy0 = 96
    flat = [(c, wi, di) for wi, w in enumerate(weeks) for di, c in enumerate(w)]
    mx = max([c for c, _, _ in flat] + [1])

    def lvl(c):
        if c == 0: return 0
        r = c / mx
        return 1 if r < .25 else 2 if r < .5 else 3 if r < .75 else 4

    D = 9.0  # seconds for one pass
    targets = sorted([f for f in flat if f[0] > 0], key=lambda f: -f[0])[:14]
    tset = {(wi, di) for _, wi, di in targets}
    cells, shots = [], []
    jet_y = gy0 + 7 * (cell + gap) + 22
    for c, wi, di in flat:
        x, y = gx0 + wi * (cell + gap), gy0 + di * (cell + gap)
        col = LEVELS[lvl(c)]
        if (wi, di) in tset:
            t = max(0.001, min(0.97, (wi + .5) / len(weeks)))
            kt = f"0;{t:.3f};{t+0.004:.3f};{min(t+0.05,0.995):.3f};1"
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{col}">'
                         f'<animate attributeName="fill" values="{col};{col};#ffffff;#0f2a26;{col}" keyTimes="{kt}" dur="{D}s" repeatCount="indefinite"/></rect>')
            cx = x + cell / 2
            shots.append(f'<line x1="{cx:.1f}" y1="{jet_y-10}" x2="{cx:.1f}" y2="{y+cell/2:.1f}" stroke="{ACC2}" stroke-width="2" opacity="0">'
                         f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{kt}" dur="{D}s" repeatCount="indefinite"/></line>')
            shots.append(f'<circle cx="{cx:.1f}" cy="{y+cell/2:.1f}" r="2" fill="#fff" opacity="0">'
                         f'<animate attributeName="r" values="2;2;2;14;14" keyTimes="{kt}" dur="{D}s" repeatCount="indefinite"/>'
                         f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{kt}" dur="{D}s" repeatCount="indefinite"/></circle>')
        else:
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{col}"/>')
    legend = "".join(f'<rect x="{W-150+i*17}" y="44" width="12" height="12" rx="3" fill="{c}"/>' for i, c in enumerate(LEVELS))
    x0, x1 = gx0, gx0 + len(weeks) * (cell + gap)
    jet = f"""<g>
  <path d="M0 -12 L7 6 L0 2 L-7 6 Z" fill="{ACC2}"/>
  <path d="M-3 6 L0 14 L3 6 Z" fill="#fbbf24"><animate attributeName="opacity" values="1;.3;1" dur=".2s" repeatCount="indefinite"/></path>
  <animateTransform attributeName="transform" type="translate" values="{x0:.1f} {jet_y};{x1:.1f} {jet_y}" dur="{D}s" repeatCount="indefinite"/>
</g>"""
    inner = f"""
{txt(36, 52, "Contribution Activity", 22, TXT, 800, SANS)}
{txt(36, 76, f"{fmt(d['total'])} contributions in the last year", 13, ACC)}
{txt(W-160, 54, "Less", 11, DIM, anchor="end")}{legend}{txt(W-60, 54, "More", 11, DIM)}
{''.join(cells)}
{''.join(shots)}
{jet}
"""
    return frame(W, H, inner, label="Contribution activity")


def card_languages(d):
    tot = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    W, H = 1000, 110 + len(top) * 36
    rows = []
    bx, bw = 420, 520
    for i, (k, v) in enumerate(top):
        y = 112 + i * 36
        p = v / tot * 100
        c = LANG_COLORS.get(k, ACC)
        w = max(4, bw * p / 100)
        rows.append(f'<circle cx="44" cy="{y-5}" r="6" fill="{c}"/>' + txt(62, y, k, 15, TXT, 600)
                    + txt(380, y, f"{p:.0f}%", 15, c, 700, anchor="end")
                    + f'<rect x="{bx}" y="{y-13}" width="{bw}" height="10" rx="5" fill="#0f2a26"/>'
                    + f'<rect x="{bx}" y="{y-13}" width="0" height="10" rx="5" fill="{c}">'
                      f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{.2+i*.15:.2f}s" dur="1.2s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/></rect>')
    inner = f"""
{txt(36, 52, "Language Stack", 22, TXT, 800, SANS)}
{txt(36, 74, "Repository-weighted technologies", 13, ACC)}
{''.join(rows)}
"""
    return frame(W, H, inner, label="Language stack")


def card_work(d):
    projs = CFG["projects"]
    W, H = 1000, 290
    cw = (W - 72 - 24 * (len(projs) - 1)) / len(projs)
    parts = [txt(36, 50, "PROJECTS.LIST", 14, ACC, 700, extra='letter-spacing="2"'),
             txt(196, 50, "~/builds --all", 13, DIM),
             f'<line x1="8" y1="68" x2="{W-8}" y2="68" stroke="{EDGE}" stroke-opacity=".18"/>']
    for i, p in enumerate(projs):
        x = 36 + i * (cw + 24)
        y = 90
        rl = d["repo_langs"].get(p["name"], {})
        lt = sum(rl.values()) or 1
        lang, share = (max(rl.items(), key=lambda kv: kv[1])[0], max(rl.values()) / lt * 100) if rl else ("—", 0)
        c = LANG_COLORS.get(lang, ACC)
        r = 30
        circ = 2 * math.pi * r
        gx, gy = x + cw - 52, y + 54
        tags = []
        tx = x + 20
        for s in p["stack"]:
            tw = 9 * len(s) + 18
            tags.append(f'<rect x="{tx}" y="{y+136}" width="{tw}" height="24" rx="12" fill="#0f2a26" stroke="{EDGE}" stroke-opacity=".3"/>'
                        + txt(tx + tw / 2, y + 152, s, 12, ACC2, 600, anchor="middle"))
            tx += tw + 8
        desc = p["description"]
        words, lines, cur = desc.split(), [], ""
        for w_ in words:
            if len(cur) + len(w_) + 1 > 44:
                lines.append(cur); cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        parts.append(f"""
<rect x="{x}" y="{y}" width="{cw}" height="176" rx="14" fill="#06130f" stroke="{EDGE}" stroke-opacity=".3"/>
{txt(x+20, y+30, "▸ " + p["name"], 13, DIM)}
{txt(x+20, y+60, p["title"], 20, TXT, 800, SANS)}
{''.join(txt(x+20, y+88+j*20, l, 13, DIM) for j, l in enumerate(lines[:2]))}
<circle cx="{gx}" cy="{gy}" r="{r}" fill="none" stroke="#0f2a26" stroke-width="7"/>
<circle cx="{gx}" cy="{gy}" r="{r}" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round"
  stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {gx} {gy})">
  <animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{circ*(1-share/100):.1f}" begin="{.3+i*.3:.1f}s" dur="1.4s" fill="freeze"/>
</circle>
{txt(gx, gy+5, f"{share:.0f}%", 15, TXT, 800, SANS, "middle")}
{txt(gx, gy+r+22, lang, 11, DIM, anchor="middle")}
{''.join(tags)}
""")
    return frame(W, H, "".join(parts), label="Projects")


def main():
    data = load_demo() if DEMO else load_live()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("scan", card_scan), ("signal", card_signal), ("activity", card_activity),
                     ("languages", card_languages), ("work", card_work)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(data))
        print("wrote", name)


if __name__ == "__main__":
    main()
