#!/usr/bin/env python3
"""
Aurora GitHub profile cards v2 — animated SVG, live GitHub data.

  GITHUB_TOKEN=... python scripts/build_cards.py     # live data (GitHub Actions)
  python scripts/build_cards.py --demo                # offline preview

Writes cards/hero.svg, scan.svg, activity.svg, work.svg, languages.svg
"""
import base64, datetime as dt, io, json, math, os, random, sys, urllib.request
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cards")
CFG = json.load(open(os.path.join(ROOT, "profile.config.json"), encoding="utf-8"))
USER = CFG["username"]
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DEMO = "--demo" in sys.argv

# ------------------------------------------------------------------ theme
EDGE, ACC, ACC2, TXT, DIM, DIM2 = "#2dd4bf", "#5eead4", "#99f6e4", "#e6fffa", "#7aa59d", "#4d7069"
VIO, CYAN, LIME = "#a78bfa", "#22d3ee", "#a3e635"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "Inter,'Segoe UI',-apple-system,Helvetica,Arial,sans-serif"
LEVELS = ["#0e2622", "#0d4a40", "#12806b", "#20b69b", "#6ff2db"]
LANG_COLORS = {
    "TypeScript": "#3b82f6", "JavaScript": "#facc15", "Python": "#38bdf8", "CSS": "#a78bfa",
    "HTML": "#fb7185", "Java": "#f59e0b", "Kotlin": "#c084fc", "Go": "#22d3ee", "Rust": "#fdba74",
    "PLpgSQL": "#60a5fa", "Shell": "#a3e635", "Jupyter Notebook": "#fb923c", "C++": "#f472b6",
    "C#": "#4ade80", "Dart": "#2dd4bf", "Vue": "#34d399", "PHP": "#818cf8", "Swift": "#fb923c",
    "SCSS": "#f472b6",
}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


# ------------------------------------------------------------------ data
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
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "profile-cards"}), timeout=30) as r:
        return r.read()


def readme_summary(name):
    """First meaningful sentence of a repo README (used when the repo has no description)."""
    import re
    try:
        data = api(f"/repos/{USER}/{name}/readme")
        text = base64.b64decode(data.get("content", "")).decode("utf-8", "ignore")
    except Exception:
        return ""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!", "[!", "<", "|", "-", "*", ">", "```", "=")):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[*_`]", "", line).strip()
        if len(line) < 15 or line.lower().startswith(("npm ", "cd ", "git ", "http")):
            continue
        m = re.match(r"(.{15,140}?[.!?])(\s|$)", line)
        out = m.group(1) if m else line
        return out[:137].rstrip() + ("…" if len(out) > 137 else "")
    return ""


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
    langs, repo_langs, repo_meta = {}, {}, {}
    for r in own:
        try:
            l = api(f"/repos/{USER}/{r['name']}/languages")
        except Exception:
            l = {}
        repo_langs[r["name"]] = l
        repo_meta[r["name"]] = {
            "stars": r.get("stargazers_count", 0), "pushed": (r.get("pushed_at") or "")[:10],
            "description": r.get("description") or "", "language": r.get("language") or "",
            "homepage": r.get("homepage") or "", "url": r.get("html_url", ""), "archived": r.get("archived", False),
        }
        for k, v in l.items():
            langs[k] = langs.get(k, 0) + v
        if not repo_meta[r["name"]]["description"]:
            repo_meta[r["name"]]["description"] = readme_summary(r["name"])
    q = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}}}}"""
    try:
        cal = api("/graphql", {"query": q, "variables": {"login": USER}})
        cal = cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
        total = cal["totalContributions"]
    except Exception as e:
        print("contribution calendar unavailable:", e)
        today = dt.date.today()
        days, total = [((today - dt.timedelta(days=i)).isoformat(), 0) for i in range(364, -1, -1)], 0
    try:
        sep = "&" if "?" in user["avatar_url"] else "?"
        avatar = fetch_bytes(user["avatar_url"] + sep + "s=200")
    except Exception:
        avatar = None
    return {
        "name": CFG.get("name") or user.get("name") or USER,
        "followers": user.get("followers", 0), "public_repos": user.get("public_repos", 0),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "langs": langs, "repo_langs": repo_langs, "repo_meta": repo_meta,
        "repo_order": [r["name"] for r in sorted(own, key=lambda r: r.get("pushed_at") or "", reverse=True)],
        "total": total, "days": days, "avatar": avatar,
        "since": (user.get("created_at") or "")[:4],
    }


def load_demo():
    random.seed(11)
    today = dt.date(2026, 11, 25)
    days = []
    for i in range(364, -1, -1):
        d = today - dt.timedelta(days=i)
        wave = 0.5 + 0.5 * math.sin(i / 38)
        active = random.random() < 0.35 + 0.55 * wave
        c = max(0, int(random.gauss(2 + 9 * wave, 3))) if active else 0
        if d.weekday() >= 5 and random.random() < .5:
            c //= 3
        days.append((d.isoformat(), c))
    return {
        "name": CFG["name"], "followers": 24, "public_repos": 10, "stars": 37,
        "langs": {"TypeScript": 61, "JavaScript": 22, "CSS": 7, "Python": 6, "PLpgSQL": 4},
        "repo_langs": {"inhayat-uz": {"TypeScript": 92, "CSS": 6, "PLpgSQL": 2},
                       "smart-monitor": {"JavaScript": 64, "TypeScript": 33, "CSS": 3}},
        "repo_meta": {
            "inhayat-uz": {"stars": 12}, "smart-monitor": {"stars": 9},
            "farangiz": {"stars": 2, "language": "HTML", "description": "Interactive web page project.", "pushed": "2026-11-24"},
            "Sarvinoz": {"stars": 1, "language": "HTML", "description": "Personal web project.", "pushed": "2026-11-19"},
            "heart-qr": {"stars": 3, "language": "JavaScript", "description": "QR code generator with heart-shaped design.", "pushed": "2026-11-15"},
            "sentinel": {"stars": 4, "language": "Python", "description": "Security monitoring and alerting toolkit.", "pushed": "2026-11-08"},
            "phishguard": {"stars": 5, "language": "TypeScript", "description": "Phishing URL detection and user protection.", "pushed": "2026-11-08"},
            "netguard": {"stars": 3, "language": "Python", "description": "Network traffic monitoring and anomaly detection.", "pushed": "2026-11-08"},
            "sofia": {"stars": 1, "language": "JavaScript", "description": "", "pushed": "2026-05-17"},
            "CorruptStop": {"stars": 6, "language": "TypeScript", "description": "Anti-corruption reporting platform.", "homepage": "", "pushed": "2026-04-26"},
        },
        "repo_order": ["farangiz", "Sarvinoz", "smart-monitor", "heart-qr", "sentinel", "phishguard", "netguard", "inhayat-uz", "sofia", "CorruptStop"],
        "total": sum(c for _, c in days), "days": days, "avatar": None, "since": "2023",
    }


def local_file(key):
    path = CFG.get(key)
    if path and os.path.exists(os.path.join(ROOT, path)):
        with open(os.path.join(ROOT, path), "rb") as f:
            return f.read()
    return None


def derive(d):
    d["photo"] = local_file("avatar") or d.get("avatar")
    d["avatar"] = local_file("avatar_face") or d["photo"]
    days = d["days"][-371:]
    d["days"] = days
    counts = [c for _, c in days]
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1  # today may not have contributions yet
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    best = max(days, key=lambda x: x[1]) if days else ("-", 0)
    d.update(longest=longest, current=current, best=best, active=sum(1 for c in counts if c > 0))
    return d


# ------------------------------------------------------------------ svg kit
def t(x, y, s, size=14, fill=TXT, w=400, font=MONO, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" font-weight="{w}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')


def fmt(n):
    return f"{n:,}"


def fade(begin, dur=.45, dy=8):
    return (f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="{dur}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 {dy}" to="0 0" begin="{begin:.2f}s" '
            f'dur="{dur}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/>')


def base_defs(uid, w, h):
    return f"""
<linearGradient id="{uid}p" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#0c2824"/><stop offset=".5" stop-color="#071816"/><stop offset="1" stop-color="#0a2320"/>
</linearGradient>
<linearGradient id="{uid}e" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{ACC}" stop-opacity=".95"/><stop offset=".35" stop-color="{EDGE}" stop-opacity=".15"/>
  <stop offset=".7" stop-color="{CYAN}" stop-opacity=".2"/><stop offset="1" stop-color="{ACC}" stop-opacity=".8"/>
</linearGradient>
<filter id="{uid}blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="60"/></filter>
<filter id="{uid}glow" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="{uid}soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4"/></filter>
<clipPath id="{uid}clip"><rect x="8" y="8" width="{w-16}" height="{h-16}" rx="22"/></clipPath>
<pattern id="{uid}grid" width="28" height="28" patternUnits="userSpaceOnUse">
  <path d="M28 0H0V28" fill="none" stroke="{EDGE}" stroke-opacity=".05"/>
</pattern>"""


def aurora(uid, w, h, strength=1.0):
    blobs = [
        (w * .18, h * .1, w * .32, h * .55, EDGE, .22, f"0 0;{w*.08:.0f} {h*.12:.0f};0 0", 16),
        (w * .78, h * .0, w * .30, h * .5, CYAN, .14, f"0 0;-{w*.1:.0f} {h*.1:.0f};0 0", 19),
        (w * .55, h * 1.0, w * .35, h * .5, VIO, .12, f"0 0;{w*.06:.0f} -{h*.12:.0f};0 0", 22),
    ]
    out = []
    for cx, cy, rx, ry, c, o, vals, dur in blobs:
        out.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}" fill="{c}" opacity="{min(1, o*strength):.2f}" filter="url(#{uid}blur)">'
                   f'<animateTransform attributeName="transform" type="translate" values="{vals}" dur="{dur}s" repeatCount="indefinite" '
                   f'calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/></ellipse>')
    return "".join(out)


def frame(uid, w, h, inner, extra_defs="", label="", aur=1.0):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<defs>{base_defs(uid, w, h)}{extra_defs}</defs>
<rect x="5" y="5" width="{w-10}" height="{h-10}" rx="25" fill="{EDGE}" opacity=".08" filter="url(#{uid}glow)"/>
<rect x="8" y="8" width="{w-16}" height="{h-16}" rx="22" fill="url(#{uid}p)"/>
<g clip-path="url(#{uid}clip)">{aurora(uid, w, h, aur)}<rect x="8" y="8" width="{w-16}" height="{h-16}" fill="url(#{uid}grid)"/></g>
<rect x="8.5" y="8.5" width="{w-17}" height="{h-17}" rx="22" fill="none" stroke="url(#{uid}e)" stroke-width="1.5"/>
{inner}
</svg>"""


def brackets(x, y, w, h, c=ACC, L=14, op=.8):
    p = (f"M{x} {y+L}V{y}H{x+L} M{x+w-L} {y}H{x+w}V{y+L} "
         f"M{x+w} {y+h-L}V{y+h}H{x+w-L} M{x+L} {y+h}H{x}V{y+h-L}")
    return f'<path d="{p}" fill="none" stroke="{c}" stroke-width="2" stroke-opacity="{op}"/>'


def chip(x, y, label, color=ACC2, bg="#0b2622"):
    w = 8.2 * len(label) + 22
    return (f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="26" rx="13" fill="{bg}" stroke="{EDGE}" stroke-opacity=".35"/>'
            + t(x + w / 2, y + 17.5, label, 12, color, 600, anchor="middle")), w


# ------------------------------------------------------------------ avatar
def avatar_grid(png, n):
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(png)).convert("L")
        img = ImageOps.autocontrast(ImageOps.fit(img, (n, n), method=Image.LANCZOS), cutoff=1)
        img = img.point(lambda v: int(255 * (v / 255) ** 0.75))
        return [[img.getpixel((x, y)) / 255 for x in range(n)] for y in range(n)]
    except Exception:
        g = []
        for y in range(n):
            row = []
            for x in range(n):
                cx = x - n / 2 + .5
                head = (cx / (n * .2)) ** 2 + ((y - n * .38) / (n * .23)) ** 2 <= 1
                body = y > n * .68 and abs(cx) < (y - n * .56) * 1.25
                v = .08 + .06 * math.sin(x * .9 + y * .5)
                if head:
                    v = .95 - .35 * (cx / (n * .2)) ** 2 - .15 * max(0, (y - n * .38) / (n * .23))
                if body:
                    v = .7 - .2 * abs(cx) / (n * .5)
                row.append(max(0, min(1, v)))
            g.append(row)
        return g


def dot_portrait(d, cx, cy, R, n, color=ACC):
    grid = avatar_grid(d["avatar"], n)
    cell = 2 * R / n
    out = []
    for y in range(n):
        for x in range(n):
            px_, py_ = cx - R + x * cell + cell / 2, cy - R + y * cell + cell / 2
            if (px_ - cx) ** 2 + (py_ - cy) ** 2 > (R - 1) ** 2:
                continue
            v = grid[y][x]
            r = .45 + v * cell * .46
            out.append(f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="{r:.2f}" fill="{color}" fill-opacity="{.18 + v * .82:.2f}"/>')
    return "".join(out)


def hero_photo(d, cx, cy, R):
    if not d.get("photo"):
        return dot_portrait(d, cx, cy, R, 40)
    mime = "image/png" if d["photo"][:4] == b"\x89PNG" else "image/jpeg"
    b64 = base64.b64encode(d["photo"]).decode()
    href = f"data:{mime};base64,{b64}"
    return (f'<image x="{cx-R}" y="{cy-R}" width="{2*R}" height="{2*R}" href="{href}" xlink:href="{href}" '
            f'preserveAspectRatio="xMidYMid slice" filter="url(#duo)"/>'
            f'<rect x="{cx-R}" y="{cy-R}" width="{2*R}" height="{2*R}" fill="url(#hscan)"/>')


# ------------------------------------------------------------------ cards
def card_hero(d):
    uid, W, H = "h", 1000, 330
    roles = CFG.get("roles") or [CFG["role"]]
    D = 3.0 * len(roles)
    role_els = []
    for i, r in enumerate(roles):
        a, b = i / len(roles), (i + 1) / len(roles)
        kt = f"0;{a:.3f};{a+.03:.3f};{b-.03:.3f};{b:.3f};1"
        role_els.append(f'<g opacity="0">{t(56, 196, "> " + r, 22, ACC, 600)}'
                        f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kt}" dur="{D}s" begin="1s" repeatCount="indefinite"/></g>')
    cx, cy, R = 822, 158, 88
    chips, x = [], 56
    items = [(d["stars"], f"★ {fmt(d['stars'])} stars"), (d["public_repos"], f"{fmt(d['public_repos'])} repos"),
             (d["followers"], f"{fmt(d['followers'])} followers"), (d["total"], f"{fmt(d['total'])} contributions"),
             (d["active"], f"{d['active']} active days")]
    labels = [lab for v, lab in items if v][:4]
    for lab in labels:
        s, w = chip(x, 256, lab)
        chips.append(s)
        x += w + 10
    name = d["name"]
    extra = f"""
<linearGradient id="hname" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{TXT}"/><stop offset=".42" stop-color="{ACC2}"/><stop offset=".5" stop-color="#ffffff"/>
  <stop offset=".58" stop-color="{ACC2}"/><stop offset="1" stop-color="{TXT}"/>
  <animateTransform attributeName="gradientTransform" type="translate" values="-1 0;1 0" dur="6s" repeatCount="indefinite"/>
</linearGradient>
<clipPath id="hav"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath>
<filter id="duo" color-interpolation-filters="sRGB">
  <feColorMatrix type="matrix" values=".33 .33 .33 0 0  .33 .33 .33 0 0  .33 .33 .33 0 0  0 0 0 1 0"/>
  <feComponentTransfer>
    <feFuncR type="table" tableValues="0.02 0.18 0.75 0.95"/>
    <feFuncG type="table" tableValues="0.07 0.55 0.95 1"/>
    <feFuncB type="table" tableValues="0.06 0.50 0.86 0.97"/>
  </feComponentTransfer>
</filter>
<pattern id="hscan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#000" fill-opacity=".22"/></pattern>"""
    inner = f"""
<g opacity="0">{fade(.1)}
  <circle cx="62" cy="68" r="5" fill="{LIME}"><animate attributeName="r" values="4;7;4" dur="2s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="1;.35;1" dur="2s" repeatCount="indefinite"/></circle>
  {t(78, 73, CFG.get("available", "Available").upper() + "  ·  " + CFG.get("location", "").upper(), 12, LIME, 700, extra='letter-spacing="2"')}
</g>
<g opacity="0">{fade(.3, .6, 14)}{t(54, 142, name, 56, "url(#hname)", 800, SANS, extra='letter-spacing="-1.5"')}</g>
{''.join(role_els)}
<g opacity="0">{fade(.7)}{t(56, 232, CFG.get("tagline", ""), 15, DIM)}</g>
<g opacity="0">{fade(.9)}{''.join(chips)}</g>

<circle cx="{cx}" cy="{cy}" r="{R+30}" fill="none" stroke="{EDGE}" stroke-opacity=".14"/>
<circle cx="{cx}" cy="{cy}" r="{R+17}" fill="none" stroke="{ACC}" stroke-opacity=".55" stroke-width="2" stroke-dasharray="2 10" stroke-linecap="round">
  <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="30s" repeatCount="indefinite"/></circle>
<circle cx="{cx}" cy="{cy}" r="{R+30}" fill="none" stroke="{CYAN}" stroke-width="3" stroke-linecap="round"
  stroke-dasharray="70 {2*math.pi*(R+30)-70:.0f}">
  <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="-360 {cx} {cy}" dur="9s" repeatCount="indefinite"/></circle>
<circle cx="{cx}" cy="{cy}" r="{R+5}" fill="#061412" stroke="{ACC}" stroke-opacity=".5"/>
<g clip-path="url(#hav)">{hero_photo(d, cx, cy, R)}
  <rect x="{cx-R}" y="{cy-R}" width="{2*R}" height="4" fill="{ACC2}" filter="url(#{uid}soft)">
    <animate attributeName="y" values="{cy-R};{cy+R};{cy-R}" dur="5s" repeatCount="indefinite"/></rect>
</g>
{t(cx, cy+R+54, f"@{USER}", 13, DIM, 600, anchor="middle")}
"""
    return frame(uid, W, H, inner, extra, label=f"{name} — {CFG['role']}", aur=1.3)


def card_scan(d):
    uid, W, H = "s", 1000, 400
    rows = [
        ("subject", d["name"]), ("handle", f"@{USER}"), ("role", CFG["role"]), ("status", CFG["status"]),
        ("languages", " · ".join(k for k, _ in sorted(d["langs"].items(), key=lambda kv: -kv[1])[:3]) or "-"),
        ("repositories", fmt(d["public_repos"])), ("contributions", f"{fmt(d['total'])} / last year"),
        ("active_days", f"{d['active']} days"), ("streak", f"{d['current']}d current · {d['longest']}d best"),
        ("github_since", d.get("since") or "-"), ("contact", CFG["contact"]),
    ]
    lines = []
    for i, (k, v) in enumerate(rows):
        y = 126 + i * 21
        b = 1.0 + i * .14
        lines.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{b:.2f}s" dur=".01s" fill="freeze"/>'
                     + t(408, y, k, 13, DIM2) + t(548, y, ":", 13, DIM2) + "</g>")
        lines.append(f'<clipPath id="sc{i}"><rect x="562" y="{y-16}" width="0" height="22">'
                     f'<animate attributeName="width" from="0" to="390" begin="{b:.2f}s" dur=".55s" fill="freeze"/></rect></clipPath>'
                     f'<g clip-path="url(#sc{i})">{t(562, y, v, 13, TXT, 500)}</g>')
    py = 126 + len(rows) * 21 + 2
    total = 1.0 + len(rows) * .14 + .5
    inner = f"""
<circle cx="34" cy="34" r="5.5" fill="#ff5f57"/><circle cx="53" cy="34" r="5.5" fill="#febc2e"/><circle cx="72" cy="34" r="5.5" fill="#28c840"/>
{t(W/2, 39, f"{USER.lower()}@github ~ % ./profile-scan --live --deep", 13, DIM, anchor="middle")}
<circle cx="{W-50}" cy="34" r="4" fill="#ff4d6d"><animate attributeName="opacity" values="1;.15;1" dur="1.2s" repeatCount="indefinite"/></circle>
{t(W-60, 39, "REC", 11, "#ff4d6d", 700, anchor="end", extra='letter-spacing="1.5"')}
<line x1="8" y1="58" x2="{W-8}" y2="58" stroke="{EDGE}" stroke-opacity=".18"/>

<rect x="32" y="78" width="340" height="296" rx="14" fill="#051210" fill-opacity=".85"/>
{brackets(32, 78, 340, 296)}
{t(50, 102, "VISUAL.MAP", 11, ACC, 700, extra='letter-spacing="2.5"')}
{t(354, 102, "dot-matrix · 58²", 11, DIM2, anchor="end")}
<clipPath id="sreveal"><rect x="32" y="112" width="340" height="0">
  <animate attributeName="height" from="0" to="256" dur="2.4s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"/></rect></clipPath>
<g clip-path="url(#sreveal)">{dot_portrait(d, 202, 240, 122, 58)}</g>
<rect x="40" y="118" width="324" height="3" fill="{ACC2}" filter="url(#{uid}soft)" opacity="0">
  <animate attributeName="y" values="118;360;118" dur="5s" begin="2.4s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.05;.95;1" dur="5s" begin="2.4s" repeatCount="indefinite"/></rect>

<rect x="390" y="78" width="578" height="296" rx="14" fill="#051210" fill-opacity=".85"/>
{brackets(390, 78, 578, 296)}
{t(408, 102, "SYSTEM.INFO", 11, ACC, 700, extra='letter-spacing="2.5"')}
{t(950, 102, "synced " + dt.date.today().isoformat(), 11, DIM2, anchor="end")}
{''.join(lines)}
<rect x="408" y="{py-2:.1f}" width="300" height="4" rx="2" fill="#0e2622"/>
<rect x="408" y="{py-2:.1f}" width="0" height="4" rx="2" fill="{ACC}">
  <animate attributeName="width" from="0" to="300" begin=".8s" dur="{total-.8:.2f}s" fill="freeze"/></rect>
<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{total:.2f}s" dur=".3s" fill="freeze"/>
  {t(724, py+3, "SCAN COMPLETE · 100%", 11, LIME, 700, extra='letter-spacing="1.5"')}</g>
"""
    return frame(uid, W, H, inner, label=f"{d['name']} profile scan", aur=.8)


def card_activity(d):
    uid, W, H = "a", 1000, 420
    days = d["days"]
    first = dt.date.fromisoformat(days[0][0])
    pad = (first.weekday() + 1) % 7  # weeks start on Sunday
    cl = [None] * pad + days
    nweeks = math.ceil(len(cl) / 7)
    gap = 3.2
    gx0, gy0 = 70, 124
    cell = (W - gx0 - 36) / nweeks - gap
    gw = nweeks * (cell + gap)
    mx = max([c for _, c in days] + [1])

    def lvl(c):
        if c == 0:
            return 0
        r = c / mx
        return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4

    D = 10.0
    ranked = sorted([(x[1], i) for i, x in enumerate(cl) if x and x[1] > 0], reverse=True)[:16]
    targets = {i for _, i in ranked}
    jet_y = gy0 + 7 * (cell + gap) + 24
    cells, fx, months = [], [], []
    seen = set()
    for i, x in enumerate(cl):
        if x is None:
            continue
        wi, di = divmod(i, 7)
        px_, py_ = gx0 + wi * (cell + gap), gy0 + di * (cell + gap)
        ds, c = x
        dd = dt.date.fromisoformat(ds)
        if dd.day <= 7 and (dd.year, dd.month) not in seen and wi < nweeks - 2 and di == 0:
            seen.add((dd.year, dd.month))
            months.append(t(px_, gy0 - 12, MONTHS[dd.month - 1], 11, DIM))
        col = LEVELS[lvl(c)]
        if i in targets:
            tt = min(.95, max(.01, (wi + .5) / nweeks))
            kt = f"0;{tt:.3f};{tt+.006:.3f};{tt+.06:.3f};{min(tt+.2,.999):.3f};1"
            cells.append(f'<rect x="{px_:.1f}" y="{py_:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" fill="{col}">'
                         f'<animate attributeName="fill" values="{col};{col};#ffffff;#06110f;#06110f;{col}" keyTimes="{kt}" dur="{D}s" repeatCount="indefinite"/></rect>')
            cx_, cy_ = px_ + cell / 2, py_ + cell / 2
            k3 = f"0;{tt:.3f};{tt+.006:.3f};{tt+.05:.3f};1"
            fx.append(f'<line x1="{cx_:.1f}" y1="{jet_y-14:.1f}" x2="{cx_:.1f}" y2="{cy_:.1f}" stroke="{ACC2}" stroke-width="2.2" '
                      f'stroke-linecap="round" opacity="0" filter="url(#{uid}glow)">'
                      f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{k3}" dur="{D}s" repeatCount="indefinite"/></line>')
            fx.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="3" fill="none" stroke="#fff" stroke-width="2" opacity="0">'
                      f'<animate attributeName="r" values="3;3;3;22;22" keyTimes="{k3}" dur="{D}s" repeatCount="indefinite"/>'
                      f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{k3}" dur="{D}s" repeatCount="indefinite"/></circle>')
            for k in range(6):
                ang = k * math.pi / 3 + .4
                dx, dy = math.cos(ang) * 18, math.sin(ang) * 18
                fx.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="1.8" fill="{ACC2}" opacity="0">'
                          f'<animateTransform attributeName="transform" type="translate" values="0 0;0 0;0 0;{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f}" '
                          f'keyTimes="{k3}" dur="{D}s" repeatCount="indefinite"/>'
                          f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{k3}" dur="{D}s" repeatCount="indefinite"/></circle>')
        else:
            cells.append(f'<rect x="{px_:.1f}" y="{py_:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="3" fill="{col}"/>')
    wdl = "".join(t(gx0 - 10, gy0 + di * (cell + gap) + cell - 2, lab, 10, DIM2, anchor="end")
                  for di, lab in [(1, "Mon"), (3, "Wed"), (5, "Fri")])
    legend = "".join(f'<rect x="{W-152+i*17}" y="42" width="12" height="12" rx="3" fill="{c}"/>' for i, c in enumerate(LEVELS))
    x0, x1 = gx0 - 10, gx0 + gw
    jet = f"""<g>
  <animateTransform attributeName="transform" type="translate" values="{x0:.1f} {jet_y:.1f};{x1:.1f} {jet_y:.1f}" dur="{D}s" repeatCount="indefinite"/>
  <rect x="-70" y="3" width="66" height="2" fill="url(#atrail)"/>
  <path d="M-3 -2 L-14 7 L-3 4 Z" fill="{EDGE}"/><path d="M3 -2 L14 7 L3 4 Z" fill="{EDGE}"/>
  <path d="M0 -15 L5 4 L0 8 L-5 4 Z" fill="{ACC2}"/>
  <circle cx="0" cy="11" r="3" fill="#fbbf24" filter="url(#{uid}soft)"><animate attributeName="r" values="2;4;2" dur=".15s" repeatCount="indefinite"/></circle>
</g>"""
    extra = (f'<linearGradient id="atrail" x1="1" x2="0"><stop offset="0" stop-color="{ACC2}" stop-opacity=".8"/>'
             f'<stop offset="1" stop-color="{ACC2}" stop-opacity="0"/></linearGradient>')
    best_d, best_c = d["best"]
    try:
        bd = dt.date.fromisoformat(best_d)
        best_s = f"{MONTHS[bd.month-1]} {bd.day}"
    except Exception:
        best_s = "-"
    stats = [("TOTAL", fmt(d["total"]), "contributions"), ("CURRENT STREAK", str(d["current"]), "days"),
             ("LONGEST STREAK", str(d["longest"]), "days"), ("BEST DAY", str(best_c), best_s)]
    sw = (W - 72 - 3 * 14) / 4
    st = []
    for i, (k, v, sub) in enumerate(stats):
        x = 36 + i * (sw + 14)
        st.append(f'<g opacity="0">{fade(.4 + i * .12)}<rect x="{x:.1f}" y="306" width="{sw:.1f}" height="82" rx="12" fill="#051210" '
                  f'fill-opacity=".8" stroke="{EDGE}" stroke-opacity=".22"/>'
                  + t(x + 18, 330, k, 10.5, DIM, 700, extra='letter-spacing="1.6"')
                  + t(x + 18, 368, v, 30, ACC2, 800, SANS) + t(x + sw - 16, 368, sub, 12, DIM, anchor="end") + "</g>")
    inner = f"""
{t(36, 52, "Contribution Activity", 22, TXT, 800, SANS)}
{t(36, 76, f"{fmt(d['total'])} contributions in the last year · {d['active']} active days", 13, ACC)}
{t(W-162, 52, "Less", 11, DIM, anchor="end")}{legend}{t(W-62, 52, "More", 11, DIM)}
{''.join(months)}{wdl}
{''.join(cells)}
{''.join(fx)}
{jet}
{''.join(st)}
"""
    return frame(uid, W, H, inner, extra, label="Contribution activity", aur=.7)


def wrap(text, n):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        if cur and len(cur) + len(w_) + 1 > n:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def fmt_date(s):
    try:
        x = dt.date.fromisoformat(s[:10])
        return f"{MONTHS[x.month-1]} {x.year}"
    except Exception:
        return "-"


def live_pill(x_right, y, live):
    if not live:
        return ""
    return (f'<circle cx="{x_right-38:.1f}" cy="{y-4}" r="3.5" fill="{LIME}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>'
            + t(x_right, y, "LIVE", 10.5, LIME, 700, anchor="end", extra='letter-spacing="1.4"'))


def other_repos(d):
    featured = {p["name"].lower() for p in CFG["projects"]}
    hidden = {n.lower() for n in CFG.get("exclude", [])} | {USER.lower()}
    order = d.get("repo_order") or list(d.get("repo_meta", {}).keys())
    return [n for n in order if n.lower() not in featured and n.lower() not in hidden]


def card_work(d):
    uid, W = "w", 1000
    projs = CFG["projects"]
    others = other_repos(d)
    ncol, gh_, gv = 3, 16, 16
    ch2 = 136
    rows_ = math.ceil(len(others) / ncol)
    H = 86 + 230 + (48 + rows_ * (ch2 + gv) if others else 0) + 26
    cw = (W - 72 - 20 * (len(projs) - 1)) / len(projs)
    parts = [t(36, 48, "PROJECTS.LIST", 13, ACC, 700, extra='letter-spacing="2.5"'), t(180, 48, "~/builds --all --live", 13, DIM2),
             t(W - 36, 48, f"{len(projs) + len(others)} repositories · {len(projs)} in production", 12, DIM, anchor="end"),
             f'<line x1="8" y1="66" x2="{W-8}" y2="66" stroke="{EDGE}" stroke-opacity=".18"/>']
    for i, p in enumerate(projs):
        x, y, ch = 36 + i * (cw + 20), 86, 230
        rl = d["repo_langs"].get(p["name"], {})
        lt = sum(rl.values()) or 1
        meta = d.get("repo_meta", {}).get(p["name"], {})
        segs, sx, bw = [], x + 22, cw - 44
        top = sorted(rl.items(), key=lambda kv: -kv[1])
        for k, v in top[:4]:
            w = bw * v / lt
            segs.append(f'<rect x="{sx:.1f}" y="{y+152}" width="{w:.1f}" height="6" fill="{LANG_COLORS.get(k, ACC)}"/>')
            sx += w
        lang_lbl = "   ".join(f"● {k} {v/lt*100:.0f}%" for k, v in top[:3])
        words, lines, cur = p["description"].split(), [], ""
        for w_ in words:
            if len(cur) + len(w_) + 1 > 46:
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        tags, tx = [], x + 22
        for s in p["stack"]:
            c_, w_ = chip(tx, y + 186, s)
            tags.append(c_)
            tx += w_ + 8
        parts.append(f"""<g opacity="0">{fade(.2 + i * .25, .6, 12)}
<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" rx="16" fill="#051210" fill-opacity=".85" stroke="{EDGE}" stroke-opacity=".28"/>
{brackets(x, y, cw, ch, L=12, op=.5)}
{t(x+22, y+32, "▸ " + p["name"], 12.5, DIM)}
<circle cx="{x+cw-(124 if meta.get("stars") else 74):.1f}" cy="{y+28}" r="4" fill="{LIME}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>
{t(x+cw-(114 if meta.get("stars") else 64), y+32, "LIVE", 11, LIME, 700, extra='letter-spacing="1.5"')}
{t(x+cw-22, y+32, "★ " + str(meta.get("stars", 0)), 12, ACC2, 700, anchor="end") if meta.get("stars") else ""}
{t(x+22, y+68, p["title"], 23, TXT, 800, SANS)}
{t(x+22, y+92, "↗ " + p.get("domain", ""), 12.5, ACC, 600)}
{''.join(t(x+22, y+118+j*19, l, 12.5, DIM) for j, l in enumerate(lines[:2]))}
<clipPath id="wb{i}"><rect x="{x+22:.1f}" y="{y+152}" width="{bw:.1f}" height="6" rx="3"/></clipPath>
<rect x="{x+22:.1f}" y="{y+152}" width="{bw:.1f}" height="6" rx="3" fill="#0e2622"/>
<g clip-path="url(#wb{i})">{''.join(segs)}</g>
{t(x+22, y+176, lang_lbl, 11, DIM2)}
{''.join(tags)}
</g>""")
    if others:
        y0 = 86 + 230 + 48
        parts.append(t(36, y0 - 12, "MORE.BUILDS", 11, ACC, 700, extra='letter-spacing="2.5"'))
        parts.append(f'<line x1="150" y1="{y0-16}" x2="{W-36}" y2="{y0-16}" stroke="{EDGE}" stroke-opacity=".15"/>')
        cw2 = (W - 72 - gh_ * (ncol - 1)) / ncol
        for j, name in enumerate(others):
            m = d["repo_meta"].get(name, {})
            r_, c_ = divmod(j, ncol)
            x, y = 36 + c_ * (cw2 + gh_), y0 + r_ * (ch2 + gv)
            lang = m.get("language") or ""
            lc = LANG_COLORS.get(lang, DIM)
            desc = m.get("description") or "No description yet."
            lines = wrap(desc, 36)[:2]
            if len(wrap(desc, 36)) > 2:
                lines[1] = lines[1][:33].rstrip() + "…"
            foot = m.get("homepage", "").replace("https://", "").replace("http://", "").rstrip("/")
            room = int((cw2 - 60 - 7 * len(lang or "—")) / 6.4) - 2
            foot = ("↗ " + (foot if len(foot) <= room else foot[:room-1] + "…")) if foot else ("updated " + fmt_date(m.get("pushed", "")))
            badge = ""
            if m.get("archived"):
                badge = t(x + cw2 - 18, y + 30, "ARCHIVED", 9.5, DIM, 700, anchor="end", extra='letter-spacing="1.2"')
            parts.append(f"""<g opacity="0">{fade(.6 + j * .08, .5, 10)}
<rect x="{x:.1f}" y="{y}" width="{cw2:.1f}" height="{ch2}" rx="14" fill="#051210" fill-opacity=".8" stroke="{EDGE}" stroke-opacity=".2"/>
{t(x+18, y+30, name, 15, TXT, 800, SANS)}
{badge or (t(x+cw2-18, y+30, "★ " + str(m.get("stars", 0)), 12, ACC2, 700, anchor="end") if m.get("stars") else live_pill(x+cw2-18, y+30, bool(m.get("homepage"))))}
{''.join(t(x+18, y+56+k*18, l, 11.5, DIM) for k, l in enumerate(lines))}
<circle cx="{x+22:.1f}" cy="{y+ch2-22}" r="4.5" fill="{lc}"/>
{t(x+32, y+ch2-18, lang or "—", 11, DIM2, 600)}
{t(x+cw2-18, y+ch2-18, foot, 10.5, DIM2, anchor="end")}
</g>""")
    return frame(uid, W, H, "".join(parts), label="Projects", aur=.7)


def card_languages(d):
    uid, W = "l", 1000
    tot = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    H = max(300, 128 + len(top) * 38)
    cx, cy, R, SW = 160, H / 2 + 16, 80, 20
    circ = 2 * math.pi * R
    arcs, acc = [], 0
    for i, (k, v) in enumerate(top):
        frac = v / tot
        c = LANG_COLORS.get(k, ACC)
        L = max(0, circ * frac - 3)
        arcs.append(f'<circle cx="{cx}" cy="{cy:.1f}" r="{R}" fill="none" stroke="{c}" stroke-width="{SW}" '
                    f'stroke-dasharray="0 {circ:.1f}" stroke-dashoffset="{-acc*circ:.1f}" transform="rotate(-90 {cx} {cy:.1f})">'
                    f'<animate attributeName="stroke-dasharray" from="0 {circ:.1f}" to="{L:.1f} {circ-L:.1f}" begin="{.2+i*.18:.2f}s" '
                    f'dur=".9s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/></circle>')
        acc += frac
    lead = top[0] if top else ("-", 0)
    rows, bx, bw = [], 530, 420
    for i, (k, v) in enumerate(top):
        y = 122 + i * 38
        p = v / tot * 100
        c = LANG_COLORS.get(k, ACC)
        w = max(5, bw * p / 100)
        rows.append(f'<g opacity="0">{fade(.2 + i * .12)}<rect x="320" y="{y-12}" width="12" height="12" rx="3" fill="{c}"/>'
                    + t(342, y, k, 14.5, TXT, 600) + t(bx - 16, y, f"{p:.1f}%", 14, c, 700, anchor="end")
                    + f'<rect x="{bx}" y="{y-10}" width="{bw}" height="8" rx="4" fill="#0e2622"/>'
                    + f'<rect x="{bx}" y="{y-10}" width="0" height="8" rx="4" fill="{c}">'
                    f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{.3+i*.12:.2f}s" dur="1.1s" fill="freeze" '
                    f'calcMode="spline" keyTimes="0;1" keySplines=".2 .8 .2 1"/></rect></g>')
    inner = f"""
{t(36, 52, "Language Stack", 22, TXT, 800, SANS)}
{t(36, 74, "Repository-weighted · bytes of code across own repos", 13, ACC)}
<circle cx="{cx}" cy="{cy:.1f}" r="{R}" fill="none" stroke="#0e2622" stroke-width="{SW}"/>
{''.join(arcs)}
<circle cx="{cx}" cy="{cy:.1f}" r="{R+SW/2+9}" fill="none" stroke="{EDGE}" stroke-opacity=".3" stroke-dasharray="1 7">
  <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy:.1f}" to="360 {cx} {cy:.1f}" dur="40s" repeatCount="indefinite"/></circle>
{t(cx, cy+4, f"{lead[1]/tot*100:.0f}%", 30, TXT, 800, SANS, "middle")}
{t(cx, cy+24, lead[0], 12, DIM, 600, anchor="middle")}
{''.join(rows)}
"""
    return frame(uid, W, H, inner, label="Language stack", aur=.7)


def update_readme(d):
    path = os.path.join(ROOT, "README.md")
    a, b = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return
    if a not in text or b not in text:
        return
    rows = ["| Loyiha | Tavsif | Til | ⭐ |", "|:--|:--|:--|:--:|"]
    featured = [p["name"] for p in CFG["projects"]]
    for name in featured + other_repos(d):
        m = d["repo_meta"].get(name, {})
        p = next((p for p in CFG["projects"] if p["name"] == name), None)
        desc = (p["description"] if p else m.get("description")) or "—"
        url = m.get("url") or f"https://github.com/{USER}/{name}"
        home = (p and p.get("url")) or m.get("homepage") or ""
        title = f"[**{name}**]({url})" + (f" · [demo]({home})" if home else "")
        rows.append(f"| {title} | {desc.replace('|', '/')} | {m.get('language') or '—'} | {m.get('stars', 0)} |")
    block = a + "\n\n" + "\n".join(rows) + "\n\n" + b
    text = text[:text.index(a)] + block + text[text.index(b) + len(b):]
    open(path, "w", encoding="utf-8").write(text)
    print("README projects table updated")


def main():
    data = derive(load_demo() if DEMO else load_live())
    os.makedirs(OUT, exist_ok=True)
    try:
        os.remove(os.path.join(OUT, "signal.svg"))
    except FileNotFoundError:
        pass
    for name, fn in [("hero", card_hero), ("scan", card_scan), ("activity", card_activity),
                     ("work", card_work), ("languages", card_languages)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(data))
        print("wrote", name)
    if not DEMO:
        update_readme(data)


if __name__ == "__main__":
    main()
