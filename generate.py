#!/usr/bin/env python3
"""Raport zilnic relaxat -> site/index.html

Rulare:  python generate.py            (date reale, ca pe GitHub)
         python generate.py --demo     (date de test, fără internet)
Variabile de mediu (secrete în GitHub):
  ICAL_URLS      adresele secrete iCal din Google Calendar, câte una pe rând
  PAGE_PASSWORD  parola cu care se deschide secțiunea de calendar
"""
import argparse, base64, html, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (RaportZilnic)"}
STATUS = []  # probleme întâlnite, afișate discret în subsol

ZILE = ["luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"]
LUNI = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
        "august", "septembrie", "octombrie", "noiembrie", "decembrie"]
TARI = {"RO": "România", "CZ": "Cehia", "GB": "Marea Britanie", "DE": "Germania",
        "FR": "Franța", "IT": "Italia", "ES": "Spania", "PL": "Polonia",
        "HU": "Ungaria", "AT": "Austria", "BG": "Bulgaria", "GR": "Grecia",
        "SK": "Slovacia", "IE": "Irlanda", "NL": "Olanda", "BE": "Belgia",
        "PT": "Portugalia", "MD": "Moldova", "CH": "Elveția", "SE": "Suedia"}

GANDURI = [
    "Respiră adânc. Lista de azi nu fuge nicăieri 🌿",
    "Un pas mic tot pas e. Și cafeaua ajută ☕",
    "Nu trebuie să faci totul azi. Doar ce contează 🍃",
    "Fă o pauză de 5 minute. Serios. Corpul îți mulțumește 🫖",
    "Azi poate fi o zi bună, chiar dacă începe încet 🌤️",
    "Apă, soare (dacă e) și un gând frumos 💧",
    "Nu compara ziua ta cu a altcuiva 🌸",
    "Mai încet = mai departe, uneori 🐢",
    "Un zâmbet costă zero și merge cu orice haină 😊",
    "Bifează un lucru mic, bucură-te de el ✅",
    "Fii blând cu tine azi 🤍",
    "Mâncarea bună face parte din productivitate 🥐",
    "Câteva minute de aer curat schimbă tot 🌬️",
    "Ce nu iese azi, iese mâine. Promit 🌙",
]

WMO = {
    0: ("☀️", "Senin"), 1: ("🌤️", "Mai mult senin"), 2: ("⛅", "Parțial noros"),
    3: ("☁️", "Noros"), 45: ("🌫️", "Ceață"), 48: ("🌫️", "Ceață cu chiciură"),
    51: ("🌦️", "Burniță"), 53: ("🌦️", "Burniță"), 55: ("🌧️", "Burniță deasă"),
    56: ("🌧️", "Burniță înghețată"), 57: ("🌧️", "Burniță înghețată"),
    61: ("🌧️", "Ploaie ușoară"), 63: ("🌧️", "Ploaie"), 65: ("🌧️", "Ploaie puternică"),
    66: ("🌧️", "Ploaie înghețată"), 67: ("🌧️", "Ploaie înghețată"),
    71: ("🌨️", "Ninsoare ușoară"), 73: ("🌨️", "Ninsoare"), 75: ("❄️", "Ninsoare puternică"),
    77: ("🌨️", "Fulgi"), 80: ("🌦️", "Averse"), 81: ("🌧️", "Averse"),
    82: ("⛈️", "Averse puternice"), 85: ("🌨️", "Averse de ninsoare"),
    86: ("❄️", "Averse de ninsoare"), 95: ("⛈️", "Furtună"),
    96: ("⛈️", "Furtună cu grindină"), 99: ("⛈️", "Furtună cu grindină"),
}

# Plasă de siguranță dacă sursa online pentru sărbători nu răspunde (sărbători mari, date fixe)
SARBATORI_FIXE = {
    "01-01": "Anul Nou · Sf. Vasile cel Mare (ortodox) · Sfânta Maria, Maica lui Dumnezeu (catolic)",
    "01-06": "Botezul Domnului – Boboteaza (ortodox) · Epifania (catolic)",
    "01-07": "Soborul Sf. Ioan Botezătorul (ortodox)",
    "02-02": "Întâmpinarea Domnului (ortodox) · Prezentarea Domnului (catolic)",
    "03-25": "Buna Vestire / Bunavestire (ortodox și catolic)",
    "04-23": "Sf. Gheorghe",
    "05-21": "Sf. Constantin și Elena",
    "06-24": "Nașterea Sf. Ioan Botezătorul",
    "06-29": "Sf. Apostoli Petru și Pavel",
    "07-20": "Sf. Ilie",
    "08-06": "Schimbarea la Față",
    "08-15": "Adormirea Maicii Domnului (ortodox) · Asumpțiunea (catolic)",
    "08-29": "Tăierea capului Sf. Ioan Botezătorul",
    "09-08": "Nașterea Maicii Domnului",
    "09-14": "Înălțarea Sfintei Cruci",
    "10-14": "Sf. Cuvioasă Parascheva",
    "10-26": "Sf. Dimitrie",
    "11-01": "Toți Sfinții (catolic)",
    "11-08": "Sf. Arhangheli Mihail și Gavriil",
    "11-21": "Intrarea în biserică a Maicii Domnului",
    "11-25": "Sf. Ecaterina",
    "11-30": "Sf. Apostol Andrei",
    "12-06": "Sf. Nicolae",
    "12-08": "Nemaculata Zămislire (catolic)",
    "12-25": "Nașterea Domnului – Crăciunul",
    "12-26": "Soborul Maicii Domnului",
    "12-27": "Sf. Ștefan",
}


def esc(s):
    return html.escape(str(s), quote=True)


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url):
    return json.loads(http_get(url).decode("utf-8"))


def warn(what, err):
    STATUS.append(f"{what}: {str(err)[:90]}")
    print(f"[!] {what}: {err}", file=sys.stderr)


def flag(cc):
    cc = "GB" if cc == "UK" else cc
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def soft_error(what):
    return f'<p class="muted">N-am reușit să încarc „{esc(what)}” acum 🙈 Mai încerc la următoarea rulare.</p>'


# ───────────────────────── VREME ─────────────────────────

def fetch_weather(loc):
    q = {
        "latitude": loc["lat"], "longitude": loc["lon"], "timezone": "auto", "forecast_days": 3,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                  "apparent_temperature_min,precipitation_probability_max,precipitation_sum,"
                  "wind_speed_10m_max,uv_index_max,sunrise,sunset"),
    }
    d = get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    c, dd = d["current"], d["daily"]
    days = []
    for i in range(len(dd["time"])):
        days.append({
            "date": dd["time"][i], "code": dd["weather_code"][i],
            "tmax": dd["temperature_2m_max"][i], "tmin": dd["temperature_2m_min"][i],
            "fmax": dd["apparent_temperature_max"][i], "fmin": dd["apparent_temperature_min"][i],
            "pop": dd["precipitation_probability_max"][i] or 0,
            "precip": dd["precipitation_sum"][i] or 0,
            "wind": dd["wind_speed_10m_max"][i] or 0, "uv": dd["uv_index_max"][i] or 0,
            "sunrise": dd["sunrise"][i], "sunset": dd["sunset"][i],
        })
    return {"loc": loc, "cur": {"temp": c["temperature_2m"], "feels": c["apparent_temperature"],
                                "code": c["weather_code"], "wind": c["wind_speed_10m"],
                                "hum": c["relative_humidity_2m"]}, "days": days}


def clothing(day):
    """Reguli simple, pe înțelesul tuturor."""
    t = (day["fmax"] + day["fmin"]) / 2
    if t <= -5:
        base = [("🧥", "Geacă groasă de iarnă, căciulă, mănuși și fular"),
                ("🥾", "Ghete călduroase, cu talpă bună"), ("🧦", "Șosete groase – degetele îți vor mulțumi")]
    elif t <= 2:
        base = [("🧥", "Geacă de iarnă, căciulă și mănuși"), ("🧣", "Fularul nu strică"),
                ("🥾", "Încălțăminte călduroasă")]
    elif t <= 8:
        base = [("🧥", "Geacă călduroasă sau palton"), ("🧶", "Pulover gros, pantaloni lungi"),
                ("🧣", "Un fular ușor")]
    elif t <= 13:
        base = [("🧥", "Jachetă sau geacă de tranziție"), ("👕", "Pulover peste tricou")]
    elif t <= 18:
        base = [("🧶", "Hanorac sau cardigan"), ("👖", "Pantaloni lungi")]
    elif t <= 23:
        base = [("👕", "Tricou, plus ceva ușor pentru seară")]
    elif t <= 28:
        base = [("👕", "Haine ușoare, respirabile"), ("🧢", "Pălărie sau șapcă")]
    else:
        base = [("🩳", "Cât mai ușor și cât mai puțin"), ("💧", "Apă la tine, umbră la prânz")]
    code = day["code"]
    snow = code in (71, 73, 75, 77, 85, 86)
    if snow:
        base.append(("🥾", "Bocanci – pe jos poate fi alunecos"))
    elif day["pop"] >= 50 or code in (61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
        base.append(("☂️", f"Umbrelă sau geacă impermeabilă (șanse de ploaie {day['pop']}%)"))
    elif day["pop"] >= 30:
        base.append(("☂️", "O umbrelă mică în geantă, just in case"))
    if day["wind"] >= 30:
        base.append(("🌬️", f"Vânt serios (până la {day['wind']:.0f} km/h) – ceva care oprește vântul"))
    if day["fmax"] - day["fmin"] >= 10:
        base.append(("🧅", "Diferență mare între dimineață și prânz – îmbracă-te în straturi"))
    if day["uv"] >= 6:
        base.append(("😎", "UV ridicat – ochelari și cremă"))
    if code in (45, 48):
        base.append(("🚗", "Ceață – dacă mergi cu mașina, mai ușor pe accelerator"))
    return base


def hhmm(iso):
    return iso[11:16] if iso and len(iso) >= 16 else "–"


def render_weather(wlist, edition, show_clothing):
    out = []
    idx = 1 if edition == "evening" else 0
    for w in wlist:
        loc, cur, days = w["loc"], w["cur"], w["days"]
        today = days[0]
        e, txt = WMO.get(cur["code"], ("🌡️", ""))
        tgt = days[min(idx, len(days) - 1)]
        te, ttxt = WMO.get(tgt["code"], ("🌡️", ""))
        nxt = days[1] if len(days) > 1 else None
        ne, ntxt = WMO.get(nxt["code"], ("🌡️", "")) if nxt else ("", "")
        card = [f'<div class="card"><h2>{esc(loc.get("emoji", "📍"))} {esc(loc["name"])}</h2>',
                f'<div class="now"><span class="big">{e} {cur["temp"]:.0f}°</span>'
                f'<span class="desc">{esc(txt)} · se simte ca {cur["feels"]:.0f}°</span></div>',
                '<div class="chips">'
                f'<span>🌡️ {today["tmin"]:.0f}° / {today["tmax"]:.0f}°</span>'
                f'<span>☔ {today["pop"]:.0f}%</span>'
                f'<span>💨 {cur["wind"]:.0f} km/h</span>'
                f'<span>💧 {cur["hum"]:.0f}%</span>'
                f'<span>🌅 {hhmm(today["sunrise"])}</span><span>🌇 {hhmm(today["sunset"])}</span></div>']
        if nxt and edition != "evening":
            card.append(f'<p class="muted">Mâine: {ne} {ntxt} · {nxt["tmin"]:.0f}° / {nxt["tmax"]:.0f}° · ☔ {nxt["pop"]:.0f}%</p>')
        if show_clothing:
            title = "Ce îmbraci mâine" if edition == "evening" else "Ce îmbraci azi"
            if edition == "evening":
                card.append(f'<p class="muted">Mâine: {te} {ttxt} · {tgt["tmin"]:.0f}° / {tgt["tmax"]:.0f}°</p>')
            card.append(f'<h3>🧥 {title}</h3><ul class="dress">')
            for em, t in clothing(tgt):
                card.append(f"<li><span>{em}</span> {esc(t)}</li>")
            card.append("</ul>")
        card.append("</div>")
        out.append("".join(card))
    return '<div class="grid two">' + "".join(out) + "</div>"


# ───────────────────────── CALENDAR (criptat) ─────────────────────────

def fetch_calendar_events(urls, tz, days_dates):
    import icalendar, recurring_ical_events
    result = {d: [] for d in days_dates}
    for url in urls:
        try:
            cal = icalendar.Calendar.from_ical(http_get(url, 30))
            q = recurring_ical_events.of(cal)
            cname = str(cal.get("X-WR-CALNAME", "") or "")
            for d in days_dates:
                for ev in q.at(d):
                    s = ev.get("DTSTART").dt
                    allday = not isinstance(s, datetime)
                    if not allday:
                        s = s.astimezone(tz) if s.tzinfo else s
                    result[d].append({
                        "time": None if allday else s.strftime("%H:%M"),
                        "title": str(ev.get("SUMMARY", "(fără titlu)")),
                        "where": str(ev.get("LOCATION", "") or ""), "cal": cname,
                    })
        except Exception as e:
            warn("calendar", e)
    for d in result:
        result[d].sort(key=lambda x: (x["time"] is not None, x["time"] or ""))
    return result


def render_calendar_inner(events, today):
    parts = []
    for d, label in ((today, "Azi"), (today + timedelta(days=1), "Mâine")):
        evs = events.get(d, [])
        parts.append(f"<h3>🗓️ {label}</h3>")
        if not evs:
            parts.append('<p class="muted">Nimic în calendar. Zi liberă pentru ce vrei tu 🍃</p>')
            continue
        parts.append('<ul class="events">')
        for ev in evs:
            when = ev["time"] or "toată ziua"
            place = f' <span class="muted">· 📍 {esc(ev["where"])}</span>' if ev["where"] else ""
            parts.append(f'<li><b>{esc(when)}</b> {esc(ev["title"])}{place}</li>')
        parts.append("</ul>")
    return "".join(parts)


def encrypt_block(plain_html, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv, iters = os.urandom(16), os.urandom(12), 200000
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(password.encode())
    ct = AESGCM(key).encrypt(iv, plain_html.encode("utf-8"), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"salt": b(salt), "iv": b(iv), "ct": b(ct), "iter": iters}


def render_calendar(events, today, password, demo):
    inner = render_calendar_inner(events, today)
    enc = encrypt_block(inner, password)
    hint = ' <span class="muted">(demo: parola este <b>demo</b>)</span>' if demo else ""
    return (
        '<div class="card"><h2>🗓️ Calendarul tău</h2>'
        f'<div id="cal-lock" data-enc=\'{json.dumps(enc)}\'>'
        '<p class="muted">Conținut protejat 🔒 Introdu parola o singură dată – o țin minte pe acest dispozitiv.' + hint + '</p>'
        '<form id="cal-form"><input id="cal-pw" type="password" placeholder="parola" autocomplete="current-password">'
        '<button type="submit">Deschide</button></form><p id="cal-err" class="muted"></p></div>'
        '<div id="cal-open" hidden></div></div>'
    )


# ───────────────────────── SĂRBĂTORI ─────────────────────────

def clean_wiki(s):
    s = re.sub(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:nowrap|nobr|lang\|[a-z-]+)\|([^{}|]*)\}\}", r"\1", s, flags=re.I)
    for _ in range(4):
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:Fișier|File|Imagine|Categorie|Category):[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip(" :;")


def parse_wiki_sarbatori(wikitext):
    m = re.search(r"^==\s*Sărbători\s*==\s*$", wikitext, flags=re.M | re.I)
    if not m:
        return []
    rest = wikitext[m.end():]
    n = re.search(r"^==[^=].*$", rest, flags=re.M)
    section = rest[:n.start()] if n else rest
    group, items = "", []
    for line in section.splitlines():
        h = re.match(r"^===+\s*(.+?)\s*===+\s*$", line)
        if h:
            group = clean_wiki(h.group(1))
            continue
        b = re.match(r"^(\*+)\s*(.*)$", line)
        if not b:
            continue
        depth, txt = len(b.group(1)), clean_wiki(b.group(2))
        if not txt:
            continue
        if depth == 1 and b.group(2).rstrip().endswith(":"):
            group = txt
            continue
        items.append((group, txt))
    return items


def fetch_sarbatori_ro(d):
    title = f"{d.day} {LUNI[d.month - 1]}"
    url = "https://ro.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
        "titles": title, "format": "json", "formatversion": 2})
    data = get_json(url)
    wt = data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    items = parse_wiki_sarbatori(wt)
    if not items:
        raise ValueError("secțiunea Sărbători negăsită")
    return items


def fetch_public_holidays(cc, year):
    return get_json(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{cc}")


def holidays_for(cfg_h, today):
    today_s, per_country, upcoming = today.isoformat(), {}, {}
    for cc in cfg_h["countries"]:
        try:
            lst = fetch_public_holidays(cc, today.year)
            if cc in cfg_h.get("upcoming_for", []):
                try:
                    lst = lst + fetch_public_holidays(cc, today.year + 1)
                except Exception:
                    pass
            hits = [h for h in lst if h["date"] == today_s]
            if hits:
                per_country[cc] = [h.get("localName") or h["name"] for h in hits]
            if cc in cfg_h.get("upcoming_for", []):
                nxt = [h for h in lst if h["date"] > today_s]
                if nxt:
                    n = min(nxt, key=lambda h: h["date"])
                    upcoming[cc] = (n.get("localName") or n["name"], date.fromisoformat(n["date"]))
        except Exception as e:
            warn(f"sărbători legale {cc}", e)
    return per_country, upcoming


def render_holidays(today, saints, saints_src, per_country, upcoming):
    p = ['<div class="grid two">']
    p.append('<div class="card"><h2>🕯️ Sfinți și sărbători religioase</h2>')
    if saints:
        groups = {}
        for g, t in saints:
            groups.setdefault(g, []).append(t)
        for g, lst in groups.items():
            if g:
                p.append(f"<h3>{esc(g)}</h3>")
            p.append('<ul class="plain">' + "".join(f"<li>{esc(t)}</li>" for t in lst[:8]) + "</ul>")
        p.append(f'<p class="muted tiny">Sursă: {esc(saints_src)}</p>')
    else:
        p.append(soft_error("sărbători religioase"))
    p.append("</div>")
    p.append('<div class="card"><h2>🎈 Ce se mai sărbătorește azi</h2>')
    if per_country:
        p.append('<ul class="plain">')
        for cc, names in per_country.items():
            p.append(f"<li>{flag(cc)} <b>{esc(TARI.get(cc, cc))}</b>: {esc(', '.join(names))}</li>")
        p.append("</ul>")
    else:
        p.append('<p class="muted">Azi nu e sărbătoare legală în țările urmărite – zi obișnuită, dar a ta 😌</p>')
    if upcoming:
        p.append("<h3>📅 Următoarea sărbătoare legală</h3><ul class=\"plain\">")
        for cc, (name, d) in upcoming.items():
            left = (d - today).days
            when = "mâine" if left == 1 else f"peste {left} zile"
            p.append(f"<li>{flag(cc)} {esc(name)} – {d.day} {LUNI[d.month - 1]} ({when})</li>")
        p.append("</ul>")
    p.append("</div></div>")
    return "".join(p)


# ───────────────────────── ȘTIRI ─────────────────────────

def feed_url(f):
    if "url" in f:
        return f["url"]
    loc = "hl=ro&gl=RO&ceid=RO:ro"
    if f.get("gnews_top"):
        return f"https://news.google.com/rss?{loc}"
    if "gnews_topic" in f:
        return f"https://news.google.com/rss/headlines/section/topic/{f['gnews_topic']}?{loc}"
    if "gnews" in f:
        return "https://news.google.com/rss/search?q=" + urllib.parse.quote(f["gnews"]) + "&" + loc
    raise ValueError("feed necunoscut")


def parse_feed(raw, label=""):
    root = ET.fromstring(raw)
    items = []
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = source = None
        for ch in it:
            t = ch.tag.split("}")[-1]
            if t == "title":
                title = (ch.text or "").strip()
            elif t == "link":
                link = (ch.text or "").strip() or ch.get("href")
            elif t == "source":
                source = (ch.text or "").strip()
        if not title or not link:
            continue
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({"title": title.strip(), "link": link, "source": source or label})
    return items


def fetch_news_category(feeds, n):
    lists = []
    for f in feeds:
        try:
            lists.append(parse_feed(http_get(feed_url(f), 20), f.get("label", "")))
        except Exception as e:
            warn("știri", e)
    out, seen, i = [], set(), 0
    while len(out) < n and any(i < len(l) for l in lists):  # amestec echilibrat între surse
        for l in lists:
            if i < len(l):
                key = re.sub(r"\W+", "", l[i]["title"].lower())[:45]
                if key not in seen:
                    seen.add(key)
                    out.append(l[i])
                    if len(out) >= n:
                        break
        i += 1
    return out


def render_news(title, emoji, cats):
    p = [f'<h2 class="sec">{emoji} {esc(title)}</h2><div class="grid three">']
    for name, items in cats.items():
        p.append(f'<div class="card"><h3 class="first">{esc(name)}</h3>')
        if not items:
            p.append(soft_error(name))
        else:
            p.append('<ul class="news">')
            for it in items:
                src = f' <span class="src">{esc(it["source"])}</span>' if it["source"] else ""
                p.append(f'<li><a href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>{src}</li>')
            p.append("</ul>")
        p.append("</div>")
    p.append("</div>")
    return "".join(p)


# ───────────────────────── CURS VALUTAR ─────────────────────────

def parse_bnr(raw):
    root = ET.fromstring(raw)
    out = {}
    for el in root.iter():
        if el.tag.split("}")[-1] == "Cube" and el.get("date"):
            day = {}
            for r in el:
                if r.tag.split("}")[-1] == "Rate" and r.text:
                    day[r.get("currency")] = float(r.text) / float(r.get("multiplier") or 1)
            if day:
                out[el.get("date")] = day
    return out


def fetch_fx(today, days):
    data = {}
    try:
        for y in (today.year - 1, today.year) if today.month <= 2 else (today.year,):
            data.update(parse_bnr(http_get(f"https://www.bnr.ro/files/xml/years/nbrfxrates{y}.xml", 25)))
        if data:
            return data, "BNR"
    except Exception as e:
        warn("curs BNR", e)
    try:  # plan B: BCE prin Frankfurter
        start = (today - timedelta(days=days + 10)).isoformat()
        j = get_json(f"https://api.frankfurter.dev/v1/{start}..?base=EUR&symbols=RON,USD,CZK")
        for dt, r in j["rates"].items():
            data[dt] = {"EUR": r["RON"], "USD": r["RON"] / r["USD"], "CZK": r["RON"] / r["CZK"]}
        if data:
            return data, "BCE (Frankfurter)"
    except Exception as e:
        warn("curs BCE", e)
    return {}, ""


def spark(vals, w=130, h=36):
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 4) / (len(vals) - 1) + 2:.1f},{h - 4 - (v - lo) / span * (h - 8):.1f}"
                   for i, v in enumerate(vals))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def render_fx(data, src, cfg, today):
    if not data:
        return '<div class="card"><h2>💶 Curs valutar</h2>' + soft_error("curs valutar") + "</div>"
    dates = sorted(data)[-(cfg["days"] + 1):]
    rows = []
    for cur in cfg["show"]:
        s = [data[d][cur] for d in dates if cur in data[d]]
        if len(s) >= 2:
            rows.append((f"1 {cur}", "RON", s, 4 if cur == "CZK" else 4))
    for a, b in cfg.get("cross", []):
        s = [data[d][a] / data[d][b] for d in dates if a in data[d] and b in data[d]]
        if len(s) >= 2:
            rows.append((f"1 {a}", b, s, 3))
    p = ['<h2 class="sec">💶 Curs valutar</h2><div class="grid three">']
    for label, unit, s, dec in rows:
        last, prev = s[-1], s[-2]
        diff = last - prev
        arrow, cls = ("▲", "up") if diff > 0 else ("▼", "down") if diff < 0 else ("•", "flat")
        p.append(f'<div class="card fx"><div class="fxl">{esc(label)} =</div>'
                 f'<div class="fxv">{last:.{dec}f} <small>{esc(unit)}</small></div>'
                 f'<div class="fxd {cls}">{arrow} {abs(diff):.{dec}f} față de ziua anterioară</div>'
                 f'{spark(s)}<div class="muted tiny">{len(s)} zile · min {min(s):.{dec}f} · max {max(s):.{dec}f}</div></div>')
    p.append(f'</div><p class="muted tiny">Sursă: {esc(src)} · ultima zi cu curs: {dates[-1]}</p>')
    return "".join(p)


# ───────────────────────── DEMO ─────────────────────────

def demo_weather(locs):
    import random
    rnd = random.Random(7)
    out = []
    for i, loc in enumerate(locs):
        base = 5 if i == 0 else 9
        days = []
        for k in range(3):
            tm = base + 3 + k - rnd.random()
            days.append({"date": f"2026-11-{24 + k}", "code": [3, 61, 2][(k + i) % 3], "tmax": tm, "tmin": tm - 7,
                         "fmax": tm - 2, "fmin": tm - 9, "pop": [40, 70, 20][(k + i) % 3], "precip": 1.2,
                         "wind": [18, 34, 12][(k + i) % 3], "uv": 1, "sunrise": f"2026-11-{24 + k}T07:04",
                         "sunset": f"2026-11-{24 + k}T15:56"})
        out.append({"loc": loc, "cur": {"temp": base + 1, "feels": base - 2, "code": 3, "wind": 14, "hum": 78}, "days": days})
    return out


def demo_fx(today, n=40):
    import random
    rnd = random.Random(3)
    data, e, u, c = {}, 5.09, 4.38, 0.2092
    for k in range(n, -1, -1):
        d = today - timedelta(days=k)
        if d.weekday() < 5:
            e += rnd.uniform(-0.012, 0.012); u += rnd.uniform(-0.02, 0.02); c += rnd.uniform(-0.0006, 0.0006)
            data[d.isoformat()] = {"EUR": e, "USD": u, "CZK": c}
    return data


DEMO_NEWS = {
    "📰 Generale": [("Exemplu de titlu: se anunță vreme mai blândă la final de săptămână", "Sursă demo")] * 3,
    "🏛️ Politică": [("Exemplu de titlu: ședință importantă în Parlament azi", "Sursă demo")] * 3,
    "⚽ Sport": [("Exemplu de titlu: programul etapei din weekend", "Sursă demo")] * 3,
}


def demo_news(cats):
    out = {}
    for name in cats:
        out[name] = [{"title": f"Exemplu de titlu #{i + 1} la „{name.split(' ', 1)[-1]}” (date demo)",
                      "link": "#", "source": "Sursă demo"} for i in range(4)]
    return out


# ───────────────────────── PAGINA ─────────────────────────

def build(args):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg.get("timezone", "Europe/Prague"))
    now = datetime.now(tz)
    if args.edition:
        edition = args.edition
    else:
        edition = "morning" if now.hour < 12 else "evening"
    today = now.date()
    n_news = cfg.get("news_items_per_category", 6)
    demo = args.demo
    sections, summary = [], []

    name = cfg.get("name", "").strip()
    greet = ("Bună dimineața" if edition == "morning" else "Bună seara") + (f", {name}" if name else "")
    greet += " ☕" if edition == "morning" else " 🌙"
    date_txt = f"{ZILE[today.weekday()].capitalize()}, {today.day} {LUNI[today.month - 1]} {today.year}"
    gand = GANDURI[today.timetuple().tm_yday % len(GANDURI)]

    for sec in cfg["sections"]:
        try:
            if sec == "weather":
                if demo:
                    wl = demo_weather(cfg["locations"])
                else:
                    wl = []
                    for loc in cfg["locations"]:
                        try:
                            wl.append(fetch_weather(loc))
                        except Exception as e:
                            warn(f"vreme {loc['name']}", e)
                if wl:
                    sections.append(render_weather(wl, edition, cfg.get("show_clothing", True)))
                    w0 = wl[0]
                    summary.append(f"{w0['loc']['name']} {w0['cur']['temp']:.0f}° {WMO.get(w0['cur']['code'], ('',''))[0]}"
                                   f" (azi {w0['days'][0]['tmin']:.0f}°/{w0['days'][0]['tmax']:.0f}°)")
                else:
                    sections.append('<div class="card"><h2>🌦️ Vremea</h2>' + soft_error("vremea") + "</div>")

            elif sec == "calendar":
                urls = [u.strip() for u in os.environ.get("ICAL_URLS", "").splitlines() if u.strip()]
                pw = "demo" if demo else os.environ.get("PAGE_PASSWORD", "")
                if demo:
                    ev = {today: [{"time": "09:30", "title": "Exemplu: ședință scurtă", "where": "Online", "cal": ""},
                                  {"time": None, "title": "Exemplu: zi de naștere – Maria 🎂", "where": "", "cal": ""}],
                          today + timedelta(days=1): [{"time": "17:00", "title": "Exemplu: sală", "where": "", "cal": ""}]}
                elif urls and pw:
                    ev = fetch_calendar_events(urls, tz, [today, today + timedelta(days=1)])
                else:
                    ev = None
                if ev is not None:
                    sections.append(render_calendar(ev, today, pw, demo))
                    summary.append(f"{len(ev.get(today, []))} în calendar azi")
                else:
                    why = ("Lipsește parola paginii (PAGE_PASSWORD)." if urls else
                           "Calendarul nu e conectat încă (secretul ICAL_URLS).")
                    sections.append(f'<div class="card"><h2>🗓️ Calendarul tău</h2><p class="muted">{why}</p></div>')

            elif sec == "holidays":
                if demo:
                    saints = [("Ortodoxă", "Sf. Mc. Clement, episcopul Romei (exemplu demo)"),
                              ("Romano-catolică", "Sf. Andrei Dung-Lac și tovarășii (exemplu demo)")]
                    src = "date demo"
                    per_c = {"RO": ["Exemplu demo"], "CZ": ["Exemplu demo"]}
                    upc = {"RO": ("Sfântul Andrei", date(2026, 11, 30)), "CZ": ("Ziua Independenței", date(2026, 12, 25))}
                else:
                    try:
                        saints, src = fetch_sarbatori_ro(today), "Wikipedia (ro)"
                    except Exception as e:
                        warn("sfinții zilei", e)
                        fb = SARBATORI_FIXE.get(today.strftime("%m-%d"))
                        saints, src = ([("", fb)], "listă internă – sărbători mari") if fb else ([], "")
                    per_c, upc = holidays_for(cfg["holidays"], today)
                sections.append(render_holidays(today, saints, src, per_c, upc))

            elif sec in ("news_ro", "news_world"):
                key = "ro" if sec == "news_ro" else "world"
                feeds = cfg["news"][key]
                cats = demo_news(feeds) if demo else {n: fetch_news_category(f, n_news) for n, f in feeds.items()}
                sections.append(render_news("Știri din România" if key == "ro" else "Știri din lume",
                                            "🇷🇴" if key == "ro" else "🌍", cats))

            elif sec == "fx":
                if demo:
                    data, src = demo_fx(today), "date demo"
                else:
                    data, src = fetch_fx(today, cfg["fx"]["days"])
                sections.append(render_fx(data, src, cfg["fx"], today))
                if data:
                    last = data[sorted(data)[-1]]
                    summary.append(f"EUR {last['EUR']:.2f} lei")
        except Exception as e:
            warn(f"secțiunea {sec}", e)
            sections.append(f'<div class="card">{soft_error(sec)}</div>')

    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    footer = f"Generat {now.strftime('%d.%m.%Y la %H:%M')} ({cfg.get('timezone')}) · surse: Open-Meteo, BNR, Nager.Date, Wikipedia, Google News, BBC"
    if STATUS:
        footer += "<br>⚠️ " + esc(" · ".join(STATUS[:6]))
    page = (tpl.replace("{{TITLE}}", esc(cfg.get("title", "Raport")))
            .replace("{{GREETING}}", esc(greet)).replace("{{DATE}}", esc(date_txt))
            .replace("{{THOUGHT}}", esc(gand)).replace("{{EDITION}}", edition)
            .replace("{{SECTIONS}}", "\n".join(sections)).replace("{{FOOTER}}", footer))
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    for f in ("manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"):
        if (ROOT / "assets" / f).exists():
            (out / f).write_bytes((ROOT / "assets" / f).read_bytes())
    (out / ".nojekyll").write_text("")
    (out / "summary.txt").write_text(" · ".join(summary) or "Raportul tău e gata", encoding="utf-8")
    print(f"OK -> {out / 'index.html'}  (ediția: {edition}, avertismente: {len(STATUS)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--edition", choices=["morning", "evening"])
    ap.add_argument("--out", default="site")
    build(ap.parse_args())
