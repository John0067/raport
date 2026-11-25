#!/usr/bin/env python3
"""Rulează generate.py cu descărcarea vremii mai robustă.

Problema rezolvată: o singură cerere eșuată (ex. „SSL handshake timed out”) făcea ca un oraș
să dispară din raport. Acum:
  1. toate orașele se cer într-o singură cerere către Open-Meteo, cu până la 4 încercări;
  2. dacă cererea grupată pică, se încearcă fiecare oraș separat, tot cu reîncercări;
  3. dacă un oraș tot nu merge, se folosesc ultimele date bune (max. 36 h), iar în subsol apare un avertisment;
  4. la fiecare rulare se salvează site/weather_cache.json, ca să existe date de rezervă data viitoare.

Rulare: python run_report.py   (aceleași opțiuni ca generate.py: --demo, --edition, --out)
"""
import argparse, json, os, sys, time, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import generate

ROOT = Path(__file__).parent
API = "https://api.open-meteo.com/v1/forecast"
CURRENT = "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m"
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
         "apparent_temperature_min,precipitation_probability_max,precipitation_sum,"
         "wind_speed_10m_max,uv_index_max,sunrise,sunset")
TIMEOUT = 45      # secunde per cerere (generate.py avea 20)
TRIES = 4         # încercări per cerere
MAX_AGE_H = 36    # cât de vechi poate fi un oraș luat din cache


def log(msg):
    print(f"[vreme] {msg}", file=sys.stderr)


def retry(fn, what, tries=TRIES, pause=4):
    err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            err = e
            log(f"{what}: încercarea {i + 1}/{tries} a eșuat ({str(e)[:90]})")
            if i < tries - 1:
                time.sleep(pause * (i + 1))
    raise err


def query(locs):
    """Una sau mai multe locații într-o cerere; întoarce mereu o listă."""
    q = {"latitude": ",".join(str(l["lat"]) for l in locs),
         "longitude": ",".join(str(l["lon"]) for l in locs),
         "timezone": "auto", "forecast_days": 5, "current": CURRENT, "daily": DAILY}
    raw = generate.http_get(API + "?" + urllib.parse.urlencode(q), TIMEOUT)
    d = json.loads(raw.decode("utf-8"))
    d = d if isinstance(d, list) else [d]
    if len(d) != len(locs):
        raise ValueError(f"răspuns cu {len(d)} locații în loc de {len(locs)}")
    return d


def convert(loc, d):
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
    # valori lipsă (null) ar strica pagina: refuz datele incomplete, ca să se reîncerce / să intre cache-ul
    for k in ("temperature_2m", "apparent_temperature", "weather_code", "wind_speed_10m", "relative_humidity_2m"):
        if c.get(k) is None:
            raise ValueError(f"valoare lipsă: {k}")
    for day in days:
        for k in ("code", "tmax", "tmin", "fmax", "fmin"):
            if day[k] is None:
                raise ValueError(f"valoare lipsă în prognoză: {k}")
    return {"loc": loc, "cur": {"temp": c["temperature_2m"], "feels": c["apparent_temperature"],
                                "code": c["weather_code"], "wind": c["wind_speed_10m"],
                                "hum": c["relative_humidity_2m"]}, "days": days}


def load_cache():
    repo = os.environ.get("GITHUB_REPOSITORY", "John0067/raport")
    owner, name = repo.split("/", 1)
    url = f"https://{owner.lower()}.github.io/{name}/weather_cache.json"
    try:
        return json.loads(generate.http_get(url, 20).decode("utf-8"))
    except Exception as e:
        log(f"nu am cache anterior ({str(e)[:80]})")
        return {}


def from_cache(entry, loc, today_iso, now_utc):
    """Date vechi, dar utilizabile: nu mai vechi de MAX_AGE_H și cu zile încă valabile."""
    try:
        age_h = (now_utc - datetime.fromisoformat(entry["fetched"])).total_seconds() / 3600
        if age_h > MAX_AGE_H:
            return None
        w = dict(entry["w"])
        w["loc"] = loc
        w["days"] = [d for d in w["days"] if d["date"] >= today_iso]
        return w if w["days"] else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--edition", choices=["morning", "evening"])
    ap.add_argument("--out", default="site")
    args = ap.parse_args()
    if args.demo:
        return generate.build(args)

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg.get("timezone", "Europe/Prague"))
    today_iso = datetime.now(tz).date().isoformat()
    now_utc = datetime.now(timezone.utc)
    locs = cfg["locations"]
    cache = load_cache()
    fresh, batch = {}, {}

    try:
        for loc, d in zip(locs, retry(lambda: query(locs), "cerere grupată")):
            try:
                batch[loc["name"]] = convert(loc, d)
            except Exception as e:
                log(f"{loc['name']}: date incomplete în cererea grupată ({e})")
    except Exception as e:
        log(f"cererea grupată a eșuat, încerc orașele pe rând ({str(e)[:80]})")

    def fetch_weather(loc):
        name = loc["name"]
        w = batch.get(name)
        if w is None:
            try:
                w = retry(lambda: convert(loc, query([loc])[0]), name)
            except Exception as e:
                old = from_cache(cache.get(name, {}), loc, today_iso, now_utc)
                if old is None:
                    raise
                generate.warn(f"vreme {name}", f"date vechi din {cache[name]['fetched'][:16].replace('T', ' ')} UTC "
                                              f"(sursa nu a răspuns: {str(e)[:50]})")
                return old
        fresh[name] = {"fetched": now_utc.isoformat(timespec="seconds"), "w": w}
        return w

    generate.fetch_weather = fetch_weather
    generate.build(args)

    keep = {n: cache[n] for n in cache if n in {l["name"] for l in locs}}
    keep.update(fresh)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "weather_cache.json").write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    log(f"gata: {len(fresh)}/{len(locs)} orașe proaspete")


if __name__ == "__main__":
    main()
