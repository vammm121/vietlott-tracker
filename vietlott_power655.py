#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vietlott Power 6/55 - tracker, du doan nhieu model, tu kiem chung, dashboard.

Cach choi: chon 6 so (1..55) + 1 so dac biet (1..55).
  Jackpot 1 = 6/6
  Jackpot 2 = 5/6 + trung so dac biet
  Giai nhat = 5/6 (40 trieu), Giai nhi = 4/6 (500k), Giai ba = 3/6 (50k)

Lenh:
  python vietlott_power655.py backfill      # tai toan bo lich su (resume-safe)
  python vietlott_power655.py update        # chi lay cac ky moi
  python vietlott_power655.py report
  python vietlott_power655.py predict
  python vietlott_power655.py seed -n 250
  python vietlott_power655.py verify
  python vietlott_power655.py audit
  python vietlott_power655.py check -t 5,19,20,26,44,53 -b 39
  python vietlott_power655.py forecast
  python vietlott_power655.py dashboard
  python vietlott_power655.py auto
  python vietlott_power655.py watch -i 1800
"""
import argparse
import csv
import json
import math
import os
import random
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from math import comb

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CSV = "vietlott_power655_full_history.csv"
PRED = "vietlott_power655_predictions.json"
HTML = "vietlott_power655_dashboard.html"
BASE = "https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/power-6x55"
LAUNCH = date(2017, 8, 1)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MAXN = 55
DRAW = 6
C = comb(MAXN, DRAW)
P_J1 = 1 / C
P_J2 = DRAW / C
P_G1 = DRAW * (MAXN - DRAW) / C
P_G2 = comb(DRAW, 4) * comb(MAXN - DRAW, 2) / C
P_G3 = comb(DRAW, 3) * comb(MAXN - DRAW, 3) / C
PRIZE = {"g1": 40_000_000, "g2": 500_000, "g3": 50_000}
FIXED_EV = P_G1 * PRIZE["g1"] + P_G2 * PRIZE["g2"] + P_G3 * PRIZE["g3"]
TICKET = 10_000
PIT = 0.10
CALIB = 0.89
ICT = timezone(timedelta(hours=7))
BLOCK = '<div class="boxkqxsdientoan">'
BAR = "=" * 74
FIELDS = ["draw_id", "draw_date", "n1", "n2", "n3", "n4", "n5", "n6", "special",
          "jackpot1_vnd", "jackpot2_vnd",
          "jp1_winners", "jp2_winners", "g1_winners", "g2_winners", "g3_winners"]


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept-Language": "vi-VN,vi;q=0.9"})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 + 1.5 * i)
    raise RuntimeError("khong tai duoc %s: %s" % (url, last))


def parse_page(html):
    out = []
    for b in html.split(BLOCK)[1:]:
        m_id = re.search(r"Kỳ vé:\s*<span[^>]*>#?(\d+)<", b)
        m_dt = re.search(r"quay th\w*\s+(\d{2}/\d{2}/\d{4})", b)
        nums = re.findall(r'class="finnish[1-6] bool">(\d{2})<', b)
        m_sp = re.search(r'class="number_special">\s*<div[^>]*>(\d{2})<', b)
        if not (m_id and m_dt and m_sp) or len(nums) != 6:
            continue

        def cnt(key):
            m = re.search(r'id="DT6X55_S_%s">\s*([\d,]+)' % key, b)
            return int(m.group(1).replace(",", "")) if m else 0

        def amt(key):
            m = re.search(r'id="DT6X55_G_%s">\s*([\d,]+)' % key, b)
            return int(m.group(1).replace(",", "")) if m else 0

        d = datetime.strptime(m_dt.group(1), "%d/%m/%Y").date()
        nums = sorted(int(x) for x in nums)
        sp = int(m_sp.group(1))
        if len(set(nums)) != 6 or sp in nums or max(nums + [sp]) > MAXN:
            continue
        out.append({
            "draw_id": m_id.group(1).zfill(5), "draw_date": d.isoformat(),
            "nums": tuple(nums), "special": sp,
            "jackpot1": amt("JACKPOT"), "jackpot2": amt("JACKPOT2"),
            "w_jp1": cnt("JACKPOT"), "w_jp2": cnt("JACKPOT2"),
            "w_g1": cnt("G1"), "w_g2": cnt("G2"), "w_g3": cnt("G3"),
        })
    return out


def load_history():
    if not os.path.exists(CSV):
        return []
    rows = []
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "draw_id": r["draw_id"], "draw_date": r["draw_date"],
                    "nums": tuple(sorted(int(r["n%d" % i]) for i in range(1, 7))),
                    "special": int(r["special"]),
                    "jackpot1": int(float(r["jackpot1_vnd"])),
                    "jackpot2": int(float(r["jackpot2_vnd"])),
                    "w_jp1": int(float(r["jp1_winners"])),
                    "w_jp2": int(float(r["jp2_winners"])),
                    "w_g1": int(float(r["g1_winners"])),
                    "w_g2": int(float(r["g2_winners"])),
                    "w_g3": int(float(r["g3_winners"])),
                })
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda x: x["draw_id"])
    return rows


def save_history(rows):
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["draw_id"]):
            d = {"draw_id": r["draw_id"], "draw_date": r["draw_date"],
                 "special": r["special"], "jackpot1_vnd": r["jackpot1"],
                 "jackpot2_vnd": r["jackpot2"], "jp1_winners": r["w_jp1"],
                 "jp2_winners": r["w_jp2"], "g1_winners": r["w_g1"],
                 "g2_winners": r["w_g2"], "g3_winners": r["w_g3"]}
            for i in range(1, 7):
                d["n%d" % i] = r["nums"][i - 1]
            w.writerow(d)


def merge(history, fresh):
    known = {r["draw_id"] for r in history}
    added = [r for r in fresh if r["draw_id"] not in known]
    if added:
        history = sorted(history + added, key=lambda x: x["draw_id"])
        save_history(history)
    return history, sorted(added, key=lambda x: x["draw_id"])


def draw_days(history):
    if not history:
        return {1, 3, 6}
    c = Counter(date.fromisoformat(r["draw_date"]).weekday() for r in history)
    return {d for d, n in c.items() if n > len(history) * 0.02}


def next_draw(last_date, days):
    now = datetime.now(ICT)
    d = last_date + timedelta(days=1)
    while d.weekday() not in days:
        d += timedelta(days=1)
    while datetime(d.year, d.month, d.day, 18, 5, tzinfo=ICT) <= now:
        d += timedelta(days=1)
        while d.weekday() not in days:
            d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, 18, 5, tzinfo=ICT)


def tickets_from_g3(g3):
    return g3 / P_G3


def ev_model(j1, j2, tickets):
    lam1 = max(tickets * P_J1 * CALIB, 1e-12)
    lam2 = max(tickets * P_J2 * CALIB, 1e-12)
    s1 = (1 - math.exp(-lam1)) / lam1
    s2 = (1 - math.exp(-lam2)) / lam2
    ev1 = (1 - PIT) * j1 * P_J1 * s1
    ev2 = (1 - PIT) * j2 * P_J2 * s2
    return {"lam1": lam1, "lam2": lam2, "ev1": ev1, "ev2": ev2,
            "total": FIXED_EV + ev1 + ev2}


def ev_verdict(ev):
    if ev >= TICKET:
        return "DUONG EV (co loi the toan hoc)"
    if ev >= 0.9 * TICKET:
        return "gan hoa von"
    return "am EV"


def top6(scores):
    return sorted(sorted(range(1, MAXN + 1), key=lambda n: (-scores.get(n, 0), n))[:6])


def top_special(scores):
    return max(range(1, MAXN + 1), key=lambda n: (scores.get(n, 0), -n))


def m_random(history, idx=0):
    rng = random.Random(7000 + idx)
    t = sorted(rng.sample(range(1, MAXN + 1), 6))
    sp = rng.choice([x for x in range(1, MAXN + 1) if x not in t])
    return t, sp


def m_hot(window=None):
    def f(history, idx=0):
        h = history[-window:] if window else history
        c = Counter(n for d in h for n in d["nums"])
        cs = Counter(d["special"] for d in h)
        t = top6(c)
        return t, top_special({n: cs.get(n, 0) for n in range(1, MAXN + 1)})
    return f


def m_cold(window=100):
    def f(history, idx=0):
        h = history[-window:]
        c = Counter(n for d in h for n in d["nums"])
        cs = Counter(d["special"] for d in h)
        return (top6({n: -c.get(n, 0) for n in range(1, MAXN + 1)}),
                top_special({n: -cs.get(n, 0) for n in range(1, MAXN + 1)}))
    return f


def m_markov(history, idx=0):
    tr, ct = defaultdict(int), defaultdict(int)
    trs, cts = defaultdict(int), defaultdict(int)
    for a, b in zip(history, history[1:]):
        sb, sp = set(b["nums"]), b["special"]
        for n in set(a["nums"]):
            ct[n] += 1
            if n in sb:
                tr[n] += 1
        cts[a["special"]] += 1
        if a["special"] == sp:
            trs[a["special"]] += 1
    return (top6({n: tr[n] / ct[n] for n in ct if ct[n] > 10}),
            top_special({n: trs[n] / cts[n] for n in cts if cts[n] > 10}))


def m_overdue(history, idx=0):
    last, lastsp = {}, {}
    for i, d in enumerate(history):
        for n in d["nums"]:
            last[n] = i
        lastsp[d["special"]] = i
    return (top6({n: len(history) - last.get(n, -1) for n in range(1, MAXN + 1)}),
            top_special({n: len(history) - lastsp.get(n, -1) for n in range(1, MAXN + 1)}))


def m_decay(history, idx=0):
    sc, scs = defaultdict(float), defaultdict(float)
    for k, d in enumerate(reversed(history)):
        w = 0.997 ** k
        for n in d["nums"]:
            sc[n] += w
        scs[d["special"]] += w
    return top6(sc), top_special(scs)


def m_balanced(history, idx=0, samples=12000):
    freq = Counter(n for d in history for n in d["nums"])
    mean = len(history) * 6 / MAXN
    sdd = max(math.sqrt(mean * (1 - 6 / MAXN)), 1e-9)
    last = {}
    for i, d in enumerate(history):
        for n in d["nums"]:
            last[n] = i
    prev = set(history[-1]["nums"]) if history else set()
    # ky vong: tong 6 so = 6*28 = 168, 3 le, 3 nho (<=28), span ~49
    tsum = 6 * (MAXN + 1) / 2.0
    tsd = math.sqrt(6 * (MAXN ** 2 - 1) / 12 * (MAXN - 6) / (MAXN - 1))

    def score(c):
        s, sm = set(c), sum(c)
        odd = sum(1 for x in c if x % 2)
        low = sum(1 for x in c if x <= (MAXN + 1) // 2)
        cons = sum(1 for x in c if x + 1 in s)
        span = max(c) - min(c)
        pen = (((sm - tsum) / tsd) ** 2 * 3.0 + abs(odd - 3) * 0.55
               + abs(low - 3) * 0.55 + max(0, cons - 1) * 0.85
               + ((span - 49) / 12.0) ** 2 * 0.6 + len(s & prev) * 0.35)
        z = sum((freq[n] - mean) / sdd for n in c) / 6.0
        od = sum(len(history) - 1 - last.get(n, -1) for n in c) / 6.0
        return pen - 0.9 * z - 0.006 * od

    rng = random.Random(9000 + idx)
    best, bs = None, None
    for _ in range(samples):
        c = tuple(sorted(rng.sample(range(1, MAXN + 1), 6)))
        v = score(c)
        if bs is None or v < bs:
            best, bs = c, v
    sp = rng.choice([x for x in range(1, MAXN + 1) if x not in best])
    return list(best), sp


MODELS = [
    ("random", m_random),
    ("hot_all", m_hot()),
    ("hot_100", m_hot(100)),
    ("hot_30", m_hot(30)),
    ("cold_100", m_cold(100)),
    ("markov", m_markov),
    ("overdue", m_overdue),
    ("decay", m_decay),
    ("balanced", m_balanced),
]


def fmt(t, sp=None):
    s = "-".join("%02d" % x for x in t)
    return s + (" | %02d" % sp if sp else "")


def draw_iv(history, idx):
    hist = history[:idx]
    out = []
    for name, fn in MODELS:
        t, sp = fn(hist, idx)
        out.append({"model": name, "ticket": sorted(t), "special": sp})
    return out


def load_pred():
    if not os.path.exists(PRED):
        return []
    try:
        with open(PRED, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return []
    for r in rows:
        r.setdefault("late", False)
        r.setdefault("draw_id", "")
        r.setdefault("created_at", "unknown")
    return rows


def save_pred(rows):
    with open(PRED, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def record_next(history):
    if not history:
        return 0
    last = history[-1]
    nd = next_draw(date.fromisoformat(last["draw_date"]), draw_days(history))
    did = str(int(last["draw_id"]) + 1).zfill(5)
    rows = load_pred()
    have = {(r.get("draw_id"), r["model"]) for r in rows}
    late = datetime.now(ICT) >= nd
    added = 0
    for row in draw_iv(history, len(history)):
        if (did, row["model"]) in have:
            continue
        rows.append({"draw_id": did, "draw_date": nd.date().isoformat(),
                     "model": row["model"], "ticket": row["ticket"],
                     "special": row["special"], "late": late,
                     "created_at": datetime.now(ICT).isoformat(timespec="seconds")})
        added += 1
    if added:
        save_pred(rows)
    return added


def cmd_update(quiet=False):
    history = load_history()
    fresh = parse_page(fetch(BASE + ".html"))
    if not fresh:
        print("Khong parse duoc du lieu tu nguon.")
        return history, []
    history, added = merge(history, fresh)
    record_next(history)
    if not quiet:
        if added:
            print("Da cap nhat %d ky moi:" % len(added))
            for r in added:
                print("  #%s %s  %s  J1 %.2f ty  J2 %.2f ty  trung %d/%d"
                      % (r["draw_id"], r["draw_date"], fmt(r["nums"], r["special"]),
                         r["jackpot1"] / 1e9, r["jackpot2"] / 1e9, r["w_jp1"], r["w_jp2"]))
        else:
            print("Khong co ky moi (%d ky, moi nhat #%s %s)."
                  % (len(history), history[-1]["draw_id"], history[-1]["draw_date"]))
    return history, added


def cmd_backfill(history):
    known = {r["draw_date"] for r in history}
    if history:
        d = date.fromisoformat(history[-1]["draw_date"])
    else:
        d = datetime.now(ICT).date()
    days = draw_days(history) if history else None
    pages = 0
    added_total = 0
    while d >= LAUNCH:
        if d.isoformat() not in known:
            url = BASE + "/" + d.strftime("%d-%m-%Y") + ".html"
            try:
                rows = parse_page(fetch(url, tries=2))
            except Exception as e:
                print("  loi %s: %s" % (d, e))
                d -= timedelta(days=1)
                continue
            pages += 1
            if rows:
                fresh = [r for r in rows if r["draw_date"] not in known]
                if fresh:
                    history, added = merge(history, fresh)
                    added_total += len(added)
                    known |= {r["draw_date"] for r in fresh}
                oldest = min(date.fromisoformat(r["draw_date"]) for r in rows)
                if pages % 10 == 0:
                    save_history(history)
                    print("  %s  ky=%d  trang=%d  moi=%d"
                          % (oldest, len(history), pages, added_total))
                d = oldest - timedelta(days=1)
                if days is None:
                    days = draw_days(history)
                continue
        d -= timedelta(days=1)
    save_history(history)
    print("Backfill xong: %d ky, %d trang da tai." % (len(history), pages))
    return history


def cmd_report(history):
    if not history:
        print("Chua co du lieu. Chay: backfill")
        return
    last = history[-1]
    days = draw_days(history)
    nd = next_draw(date.fromisoformat(last["draw_date"]), days)
    tk3 = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    ev = ev_model(last["jackpot1"], last["jackpot2"], tk3)

    print(BAR)
    print("VIETLOTT POWER 6/55 - TRANG THAI")
    print(BAR)
    print("Du lieu      : %d ky (%s -> %s)" % (len(history), history[0]["draw_date"], last["draw_date"]))
    print("Ky moi nhat  : #%s  %s  %s" % (last["draw_id"], last["draw_date"], fmt(last["nums"], last["special"])))
    print("Jackpot 1    : %.3f ty (%d nguoi trung)" % (last["jackpot1"] / 1e9, last["w_jp1"]))
    print("Jackpot 2    : %.3f ty (%d nguoi trung)" % (last["jackpot2"] / 1e9, last["w_jp2"]))
    print("Ky ke tiep   : %s 18:05 ICT (con %s)"
          % (nd.strftime("%Y-%m-%d"), nd - datetime.now(ICT)))
    print("")
    print("UOC TINH VE BAN RA")
    print("  TB 3 ky    : giai ba %d -> %.2f trieu ve" % (last["w_g3"], tk3 / 1e6))
    print("  lambda J1  : %.4f nguoi trung ky vong" % ev["lam1"])
    print("  lambda J2  : %.4f nguoi trung ky vong" % ev["lam2"])
    print("  EV         : %.0f d/ve = co dinh %.0f + JP1 %.0f + JP2 %.0f  -> %s"
          % (ev["total"], FIXED_EV, ev["ev1"], ev["ev2"], ev_verdict(ev["total"])))
    be = (TICKET - FIXED_EV) * C / ((1 - PIT) * max((1 - math.exp(-ev["lam1"])) / ev["lam1"], 1e-9))
    print("  hoa von khi J1 >= %.1f ty (gia dinh J2 = %.1f ty)"
          % (be / 1e9, last["jackpot2"] / 1e9))
    print("")
    print("DU DOAN KY #%s (%s)" % (str(int(last["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d")))
    for r in draw_iv(history, len(history)):
        print("  %-9s %s" % (r["model"], fmt(r["ticket"], r["special"])))
    cons = Counter(n for r in draw_iv(history, len(history)) for n in r["ticket"])
    cons_sp = Counter(r["special"] for r in draw_iv(history, len(history)))
    print("  %-9s %s | %02d   <- dong thuan"
          % ("consensus", fmt(sorted(cons, key=lambda n: -cons[n])[:6]),
             cons_sp.most_common(1)[0][0]))
    print("")
    print("  Khong model nao co loi the - xem: verify / audit.")


def cmd_predict(history):
    if not history:
        print("Chua co du lieu.")
        return
    nd = next_draw(date.fromisoformat(history[-1]["draw_date"]), draw_days(history))
    print("Ky #%s  %s" % (str(int(history[-1]["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d")))
    for r in draw_iv(history, len(history)):
        print("  %-9s %s" % (r["model"], fmt(r["ticket"], r["special"])))


def cmd_seed(history, n, force=False):
    rows = load_pred()
    if force:
        dates = {r["draw_date"] for r in history[max(60, len(history) - n):]}
        rows = [r for r in rows if r["draw_date"] not in dates]
    have = {(r.get("draw_date"), r["model"]) for r in rows}
    start = max(60, len(history) - n)
    added = 0
    for idx in range(start, len(history)):
        d = history[idx]["draw_date"]
        for row in draw_iv(history, idx):
            if (d, row["model"]) in have:
                continue
            rows.append({"draw_id": history[idx]["draw_id"], "draw_date": d,
                         "model": row["model"], "ticket": row["ticket"],
                         "special": row["special"], "late": False,
                         "created_at": "backfill"})
            added += 1
    save_pred(rows)
    print("Da tao %d du doan lich su tren %d ky." % (added, len(history) - start))


def binom_p(k, n, p):
    if n == 0:
        return 1.0
    mu, sdd = n * p, math.sqrt(n * p * (1 - p))
    return 0.5 * math.erfc(((k - mu) / sdd if sdd else 0) / math.sqrt(2))


def verify_stats(history):
    bydate = {r["draw_date"]: r for r in history}
    agg = defaultdict(lambda: [0, 0, 0, 0, 0])
    for p in load_pred():
        if p.get("late"):
            continue
        d = bydate.get(p["draw_date"])
        if not d:
            continue
        m = agg[p["model"]]
        m[0] += len(set(p["ticket"]) & set(d["nums"]))
        m[1] += 6
        m[2] += 1
        m[3] += 1 if p.get("special") == d["special"] else 0
        m[4] += 1
    rows = []
    for name, (hits, picks, n, sphits, spn) in agg.items():
        if not picks:
            continue
        sdd = math.sqrt(picks * (6 / MAXN) * (1 - 6 / MAXN))
        sp_sd = math.sqrt(spn * (1 / MAXN) * (1 - 1 / MAXN))
        rows.append({"model": name, "draws": n, "hits": hits, "picks": picks,
                     "rate": hits / picks,
                     "lo": (hits - 1.96 * sdd) / picks,
                     "hi": (hits + 1.96 * sdd) / picks,
                     "p": binom_p(hits, picks, 6 / MAXN),
                     "sp_rate": sphits / spn if spn else 0,
                     "sp_lo": (sphits - 1.96 * sp_sd) / spn if spn else 0,
                     "sp_hi": (sphits + 1.96 * sp_sd) / spn if spn else 0,
                     "sp_p": binom_p(sphits, spn, 1 / MAXN)})
    holm(rows, "p", "p_holm")
    holm(rows, "sp_p", "sp_holm")
    rows.sort(key=lambda r: -r["rate"])
    return rows


def holm(rows, key, out):
    """Hieu chinh Holm-Bonferroni cho nhieu lan so sanh."""
    m = len(rows)
    order = sorted(range(m), key=lambda i: rows[i][key])
    run = 0.0
    for k, i in enumerate(order):
        adj = min(1.0, (m - k) * rows[i][key])
        run = max(run, adj)
        rows[i][out] = run


def cmd_verify(history):
    rows = verify_stats(history)
    scored = {r["draw_date"] for r in history}
    pending = sum(1 for p in load_pred()
                  if p["draw_date"] not in scored and not p.get("late"))
    if not rows:
        print("Chua co du doan da cham. Chay: seed -n 250")
        return
    print(BAR)
    print("TU KIEM CHUNG (walk-forward: chi dung du lieu truoc moi ky)")
    print(BAR)
    print("%-10s %5s %6s %8s %-18s %6s %6s" % ("model", "ky", "trung", "ty le", "CI95", "p", "p_Holm"))
    for r in rows:
        note = ""
        if r["p"] < 0.05:
            note = " <-- lech" if r["p_holm"] < 0.05 else " (mat y nghia sau Holm)"
        print("%-10s %5d %6d %7.2f%% [%5.2f%%,%5.2f%%] %.3f %.3f%s"
              % (r["model"], r["draws"], r["hits"], 100 * r["rate"],
                 100 * r["lo"], 100 * r["hi"], r["p"], r["p_holm"], note))
    tot_h = sum(r["hits"] for r in rows)
    tot_p = sum(r["picks"] for r in rows)
    print("")
    print("6 so  : %d/%d = %.2f%% (ky vong %.2f%%)"
          % (tot_h, tot_p, 100 * tot_h / tot_p, 100 * 6 / MAXN))
    print("")
    print("%-10s %8s %-18s %6s %6s" % ("model", "so DB", "CI95", "p", "p_Holm"))
    for r in sorted(rows, key=lambda r: -r["sp_rate"]):
        note = ""
        if r["sp_p"] < 0.05:
            note = " <-- lech" if r["sp_holm"] < 0.05 else " (mat y nghia sau Holm)"
        print("%-10s %7.2f%% [%5.2f%%,%5.2f%%] %.3f %.3f%s"
              % (r["model"], 100 * r["sp_rate"], 100 * r["sp_lo"], 100 * r["sp_hi"],
                 r["sp_p"], r["sp_holm"], note))
    print("")
    print("So dac biet: ky vong %.2f%% (1/%d). Cho cham: %d"
          % (100 / MAXN, MAXN, pending))


def cmd_audit(history):
    if len(history) < 100:
        print("Can it nhat 100 ky.")
        return
    n = len(history)
    ds = [r["nums"] for r in history]
    freq = Counter(x for d in ds for x in d)
    obs = [freq.get(i, 0) for i in range(1, MAXN + 1)]
    exp = n * 6 / MAXN
    chi2 = sum((o - exp) ** 2 / exp for o in obs)
    p = 1 - chi2_cdf(chi2, MAXN - 1)
    sums = [sum(d) for d in ds]
    rep = Counter(len(set(a) & set(b)) for a, b in zip(ds, ds[1:]))
    spf = Counter(r["special"] for r in history)

    print(BAR)
    print("KIEM DINH DU LIEU (%d ky, %s -> %s)" % (n, history[0]["draw_date"], history[-1]["draw_date"]))
    print(BAR)
    print("1) 55 so deu? chi2=%.2f df=%d p=%.4f -> %s"
          % (chi2, MAXN - 1, p, "deu/ngau nhien" if p > 0.05 else "lech"))
    print("   min=%d max=%d TB=%.2f (ky vong %.2f)" % (min(obs), max(obs), exp, exp))
    print("2) tong 6 so: TB %.2f (lt 168), sd %.2f" % (sum(sums) / n, sd(sums)))
    print("3) trung ky truoc: TB %.3f (lt %.3f) | %s"
          % (sum(len(set(a) & set(b)) for a, b in zip(ds, ds[1:])) / (n - 1),
             6 * 6 / MAXN, dict(sorted(rep.items()))))
    print("4) ACF tong: lag1=%.3f lag2=%.3f lag3=%.3f"
          % (corr(sums[:-1], sums[1:]), corr(sums[:-2], sums[2:]), corr(sums[:-3], sums[3:])))
    sc = sum(1 for r in history if r["special"] in r["nums"])
    print("5) so dac biet: TB tan suat %.1f (lt %.1f), trung 1 so chinh: %d ky"
          % (sum(spf.values()) / MAXN, n / MAXN, sc))
    chi2s = sum((spf.get(i, 0) - n / MAXN) ** 2 / (n / MAXN) for i in range(1, MAXN + 1))
    print("   chisq so dac biet=%.2f p=%.4f" % (chi2s, 1 - chi2_cdf(chi2s, MAXN - 1)))
    jp = [r["jackpot1"] for r in history if r["jackpot1"] > 0]
    print("6) jackpot1 (bo %d ky thieu du lieu): min %.1f ty, TB %.1f ty, max %.1f ty, ACF1 %.3f"
          % (n - len(jp), min(jp) / 1e9, sum(jp) / len(jp) / 1e9, max(jp) / 1e9,
             corr(jp[:-1], jp[1:])))
    print("")
    print("KET LUAN: khong phep thu nao bac bo ngau nhien doc lap.")
    print("Khong co cong thuc cho 6 so; chi co cong thuc cho giai thuong:")
    print("  T  = giai_ba / %.6f" % P_G3)
    print("  lam1 = %.2f*T/C, lam2 = 6*lam1, C = %d" % (CALIB, C))
    print("  EV = %.0f + 0.9*J1/C*s(lam1) + 0.9*6*J2/C*s(lam2)" % FIXED_EV)


def cmd_check(history, ticket, sp=None, day=None):
    if not history:
        print("Chua co du lieu.")
        return
    if day:
        row = next((r for r in history if r["draw_date"] == day), None)
        if not row:
            print("Khong co ky ngay %s" % day)
            return
    else:
        row = history[-1]
    t = sorted(set(ticket))
    if len(t) != 6 or min(t) < 1 or max(t) > MAXN:
        print("Ve khong hop le: can 6 so khac nhau trong 1..%d" % MAXN)
        return
    hit = len(set(t) & set(row["nums"]))
    sp_ok = sp == row["special"]
    if hit == 6:
        prize, name = row["jackpot1"], "JACKPOT 1"
    elif hit == 5 and sp_ok:
        prize, name = row["jackpot2"], "JACKPOT 2"
    elif hit == 5:
        prize, name = PRIZE["g1"], "Giai nhat"
    elif hit == 4:
        prize, name = PRIZE["g2"], "Giai nhi"
    elif hit == 3:
        prize, name = PRIZE["g3"], "Giai ba"
    else:
        prize, name = 0, "Khong trung"
    print("Ky #%s %s  ket qua %s" % (row["draw_id"], row["draw_date"], fmt(row["nums"], row["special"])))
    print("Ve       %s" % fmt(t, sp))
    print("Trung    %d/6, so DB %s  ->  %s%s"
          % (hit, "dung" if sp_ok else "sai", name,
             ("  %s d" % format(prize, ",")) if prize else ""))
    if prize:
        print("Lai/lo   %s d (ve 10.000 d)" % format(prize - TICKET, ","))


def cmd_forecast(history):
    if not history:
        print("Chua co du lieu.")
        return
    last = history[-1]
    tk = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    j2 = last["jackpot2"]
    print(BAR)
    print("EV THEO MUC JACKPOT 1 (J2 = %.1f ty, %.2f trieu ve, PIT 10%%)"
          % (j2 / 1e9, tk / 1e6))
    print(BAR)
    print("%-10s %-9s %-9s %-11s %-9s %s"
          % ("J1", "lam1", "EV JP1", "EV JP2", "EV tong", "ket luan"))
    for j1 in [20e9, 30e9, 50e9, 80e9, 100e9, 150e9, 200e9, 300e9]:
        ev = ev_model(j1, j2, tk)
        print("%-10s %-9.4f %-9.0f %-11.0f %-9.0f %s"
              % ("%.0f ty" % (j1 / 1e9), ev["lam1"], ev["ev1"], ev["ev2"],
                 ev["total"], ev_verdict(ev["total"])))
    print("")
    print("Co dinh (3 giai) = %.0f d/ve (%.1f%% gia ve)" % (FIXED_EV, 100 * FIXED_EV / TICKET))
    jp = sorted(r["jackpot1"] for r in history if r["jackpot1"] > 0)
    print("J1 trung binh %.1f ty, phan vi: p50 %.1f, p90 %.1f, p99 %.1f, max %.1f"
          % (sum(jp) / len(jp) / 1e9, jp[len(jp) // 2] / 1e9,
             jp[int(len(jp) * 0.9)] / 1e9, jp[int(len(jp) * 0.99)] / 1e9, jp[-1] / 1e9))



def svg_bar(values, labels, w=880, h=260, color="#4ade80", hires=None, lo=None):
    lo_v = lo if lo is not None else min(values)
    rng = max(max(values) - lo_v, 1)
    n = len(values)
    bw = w / n
    parts = []
    for i, v in enumerate(values):
        bh = (v - lo_v) / rng * (h - 40)
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="2"/>'
                     % (i * bw + 2, h - 24 - bh, bw - 3, bh, (hires or {}).get(i, color)))
        if n <= 60:
            parts.append('<text x="%.1f" y="%.1f" fill="#94a3b8" font-size="8" '
                         'text-anchor="middle">%s</text>' % (i * bw + bw / 2, h - 8, labels[i]))
    return '<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg">%s</svg>' % (w, h, "".join(parts))


def svg_line(values, w=880, h=220, color="#38bdf8"):
    if not values:
        return ""
    lo_v, hi_v = min(values), max(values)
    rng = max(hi_v - lo_v, 1e-9)
    n = len(values)
    pts = ["%.1f,%.1f" % (10 + i * (w - 20) / max(n - 1, 1),
                          h - 20 - (v - lo_v) / rng * (h - 40))
           for i, v in enumerate(values)]
    return ('<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6"/></svg>'
            % (w, h, " ".join(pts), color))


CSS = """
:root{--bg:#0b1220;--panel:#111c31;--line:#1e2d47;--txt:#e2e8f0;--dim:#8fa3bf;
--green:#4ade80;--red:#f87171;--blue:#38bdf8;--gold:#fbbf24;--pink:#f472b6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}
h1 span{color:var(--pink)}
.sub{color:var(--dim);margin-bottom:20px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:0 0 10px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim)}
.kpi{font-size:26px;font-weight:600}
.kpi small{font-size:13px;font-weight:400;color:var(--dim)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:18px}
.panel h3{margin:0 0 12px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500;font-size:12px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.balls{display:flex;gap:7px;flex-wrap:wrap;align-items:center}
.ball{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;
font-weight:600;background:#1c2f4d;border:1px solid #2c4570}
.ball.sp{background:#3b0a1f;border-color:#7a1233;color:var(--pink)}
.ball.j{background:#3b2a05;border-color:#7c5a12;color:var(--gold)}
.sep{width:2px;height:26px;background:#334155;margin:0 2px}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;
border:1px solid var(--line);color:var(--dim)}
.tag.ok{color:var(--green);border-color:#14532d;background:#052e16}
.tag.bad{color:var(--red);border-color:#7f1d1d;background:#2b0b0b}
.tag.warn{color:var(--gold);border-color:#78350f;background:#2a1a05}
.muted{color:var(--dim);font-size:12px}
.row{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid var(--line)}
.row:last-child{border:0}
code{background:#0a1526;padding:1px 6px;border-radius:5px;font-size:12px;color:#a5d6ff}
a{color:var(--blue)}
"""


def cmd_dashboard(history):
    if not history:
        print("Chua co du lieu.")
        return
    last = history[-1]
    nd = next_draw(date.fromisoformat(last["draw_date"]), draw_days(history))
    tk3 = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    ev = ev_model(last["jackpot1"], last["jackpot2"], tk3)
    preds = draw_iv(history, len(history))
    vrows = verify_stats(history)
    freq = Counter(n for r in history for n in r["nums"])
    spf = Counter(r["special"] for r in history)
    sums = [sum(r["nums"]) for r in history]

    bins = [0] * 13
    lo_s, hi_s = 6, 6 * MAXN
    step = (hi_s - lo_s) / 13.0
    for s in sums:
        bins[min(12, max(0, int((s - lo_s) // step)))] += 1
    labels = ["%d" % (lo_s + step * i) for i in range(13)]

    hires = {}
    for n in sorted(freq, key=lambda n: -freq[n])[:6]:
        hires[n - 1] = "#fbbf24"
    for n in sorted(freq, key=lambda n: freq[n])[:6]:
        hires[n - 1] = "#64748b"

    def tag(ok, txt):
        return '<span class="tag %s">%s</span>' % ("ok" if ok else "bad", txt)

    ev_cls = "ok" if ev["total"] >= TICKET else ("warn" if ev["total"] >= 0.9 * TICKET else "bad")
    rows_draws = "".join(
        "<tr><td>#%s</td><td>%s</td><td class='muted'>%s</td>"
        "<td class='num'>%.2f ty</td><td class='num'>%.2f ty</td>"
        "<td class='num'>%d</td><td class='num'>%d</td><td class='num'>%.2f tr</td></tr>"
        % (r["draw_id"], r["draw_date"], fmt(r["nums"], r["special"]),
           r["jackpot1"] / 1e9, r["jackpot2"] / 1e9, r["w_jp1"], r["w_jp2"],
           tickets_from_g3(r["w_g3"]) / 1e6)
        for r in history[-12:][::-1])
    rows_pred = "".join(
        "<tr><td>%s</td><td class='muted'>%s</td><td class='num muted'>%02d</td></tr>"
        % (r["model"], fmt(r["ticket"]), r["special"]) for r in preds)
    rows_ver = "".join(
        "<tr><td>%s</td><td class='num'>%d</td><td class='num'>%d</td>"
        "<td class='num'>%.2f%%</td><td class='num muted'>[%.2f%%, %.2f%%]</td>"
        "<td>%s</td><td class='num'>%.2f%%</td><td>%s</td></tr>"
        % (r["model"], r["draws"], r["hits"], 100 * r["rate"], 100 * r["lo"],
           100 * r["hi"], tag(r["p"] >= 0.05, "p=%.3f" % r["p"]),
           100 * r["sp_rate"], tag(r["sp_p"] >= 0.05, "p=%.3f" % r["sp_p"]))
        for r in vrows)
    cons = Counter(n for r in preds for n in r["ticket"])
    cons_sp = Counter(r["special"] for r in preds).most_common(1)[0][0]
    cons_t = sorted(cons, key=lambda n: -cons[n])[:6]
    jp_series = [r["jackpot1"] / 1e9 for r in history[-400:]]

    html = (
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Vietlott Power 6/55 - Tracker</title><style>" + CSS +
        "</style></head><body><div class='wrap'>"
        "<h1>Vietlott <span>Power 6/55</span> - Tracker</h1>"
        "<div class='sub'>Cap nhat %s (ICT) &middot; %d ky &middot; %s &rarr; %s "
        "&middot; <a href='index.html'>Mega 6/45</a></div>"
        % (datetime.now(ICT).strftime("%Y-%m-%d %H:%M"), len(history),
           history[0]["draw_date"], last["draw_date"]) +
        "<div class='grid'>"
        "<div class='card'><h3>Ky moi nhat</h3><div class='kpi'>#%s</div>"
        "<div class='muted'>%s</div><div class='balls' style='margin-top:10px'>%s</div></div>"
        "<div class='card'><h3>Jackpot 1</h3><div class='kpi'>%.2f <small>ty</small></div>"
        "<div class='muted'>%d nguoi trung</div></div>"
        "<div class='card'><h3>Jackpot 2</h3><div class='kpi'>%.2f <small>ty</small></div>"
        "<div class='muted'>%d nguoi trung</div></div>"
        "<div class='card'><h3>EV moi ve</h3><div class='kpi'>%s <small>d</small></div>"
        "<div class='muted'>%.2f trieu ve &middot; <span class='tag %s'>%s</span></div></div>"
        "</div>"
        % (last["draw_id"], last["draw_date"],
           "".join("<div class='ball'>%02d</div>" % x for x in last["nums"]) +
           "<div class='sep'></div><div class='ball sp'>%02d</div>" % last["special"],
           last["jackpot1"] / 1e9, last["w_jp1"], last["jackpot2"] / 1e9,
           last["w_jp2"], format(round(ev["total"]), ","), tk3 / 1e6,
           ev_cls, ev_verdict(ev["total"])) +
        "<div class='panel'><h3>Du doan ky #%s - %s 18:05 ICT</h3>"
        "<div class='balls' style='margin-bottom:14px'>%s<div class='sep'></div>"
        "<div class='ball j'>%02d</div></div>"
        "<table><thead><tr><th>Model</th><th>6 so</th><th class='num'>So DB</th></tr></thead>"
        "<tbody>%s</tbody></table></div>"
        % (str(int(last["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d"),
           "".join("<div class='ball j'>%02d</div>" % x for x in cons_t),
           cons_sp, rows_pred) +
        "<div class='panel'><h3>Tu kiem chung (walk-forward)</h3>"
        "<table><thead><tr><th>Model</th><th class='num'>Ky</th><th class='num'>Trung</th>"
        "<th class='num'>Ty le</th><th class='num'>CI95</th><th>p (H0 10.91%%)</th>"
        "<th class='num'>So DB</th><th>p</th></tr></thead><tbody>%s</tbody></table>"
        "<div class='muted' style='margin-top:10px'>Ky vong: 6/55 = 10.91%% moi so, "
        "so dac biet 1/55 = 1.82%%. p &gt; 0.05 = khong co loi the.</div></div>" % rows_ver +
        "<div class='grid' style='grid-template-columns:1fr 1fr'>"
        "<div class='panel'><h3>Tan suat 55 so + so dac biet</h3>%s%s</div>"
        "<div class='panel'><h3>Phan bo tong 6 so</h3>%s</div></div>"
        % (svg_bar([freq.get(i, 0) for i in range(1, MAXN + 1)],
                   [str(i) for i in range(1, MAXN + 1)], hires=hires),
           svg_bar([spf.get(i, 0) for i in range(1, MAXN + 1)],
                   [""] * MAXN, color="#f472b6", lo=0),
           svg_bar(bins, labels, color="#38bdf8", lo=0)) +
        "<div class='panel'><h3>Jackpot 1 - 400 ky gan nhat (ty d)</h3>%s</div>"
        % svg_line(jp_series) +
        "<div class='panel'><h3>12 ky gan nhat</h3>"
        "<table><thead><tr><th>Ky</th><th>Ngay</th><th>Ket qua</th>"
        "<th class='num'>JP1</th><th class='num'>JP2</th><th class='num'>Trung 1</th>"
        "<th class='num'>Trung 2</th><th class='num'>Ve uoc</th></tr></thead>"
        "<tbody>%s</tbody></table></div>" % rows_draws +
        "<div class='panel'><h3>Cong thuc da kiem chung</h3>"
        "<div class='row'><span>Ve ban ra</span><code>T = giai_ba / %.6f</code></div>"
        "<div class='row'><span>So nguoi trung JP1</span><code>lam1 = %.2f*T/%d</code></div>"
        "<div class='row'><span>So nguoi trung JP2</span><code>lam2 = 6*lam1</code></div>"
        "<div class='row'><span>EV</span><code>%.0f + 0.9*J1/C*s1 + 0.9*6*J2/C*s2</code></div>"
        "<div class='row'><span>Xac suat</span><code>JP1 1/%s, JP2 6/%s</code></div>"
        "<div class='muted' style='margin-top:10px'>6 so khong co quy luat: "
        "chi2 p=%.3f, ACF ~0.</div></div>"
        "</div></body></html>"
        % (P_G3, CALIB, C, FIXED_EV, format(C, ","), format(C, ","), 0.0))
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("Da xuat %s (%d KB)." % (HTML, os.path.getsize(HTML) // 1024))


def corr(a, b):
    n = len(a)
    if n < 3:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


def sd(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def chi2_cdf(x, k):
    if x <= 0:
        return 0.0
    a, xx = k / 2.0, x / 2.0
    if xx < a + 1:
        term, s = 1.0 / a, 1.0 / a
        for i in range(1, 400):
            term *= xx / (a + i)
            s += term
            if abs(term) < abs(s) * 1e-15:
                break
        return s * xx ** a * math.exp(-xx) / math.gamma(a)
    b, c = xx + 1 - a, 1e300
    d = 1.0 / (xx + 1 - a)
    h = d
    for i in range(1, 400):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-15:
            break
    return 1 - math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


def cmd_watch(history, interval):
    print("Theo doi moi %d giay. Ctrl+C de dung." % interval)
    while True:
        try:
            history, added = cmd_update(quiet=True)
            if added:
                print("\a[KY MOI] " + ", ".join(
                    "#%s %s %s" % (r["draw_id"], r["draw_date"], fmt(r["nums"], r["special"]))
                    for r in added))
                cmd_report(history)
            else:
                print("[%s] chua co ky moi (moi nhat #%s)"
                      % (datetime.now(ICT).strftime("%Y-%m-%d %H:%M"), history[-1]["draw_id"]))
        except Exception as e:
            print("Loi: %s" % e)
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="Vietlott Power 6/55 tracker")
    ap.add_argument("command", nargs="?", default="report",
                    choices=["backfill", "update", "report", "watch", "predict", "seed",
                             "verify", "audit", "check", "forecast", "dashboard", "auto"])
    ap.add_argument("-n", "--num", type=int, default=250)
    ap.add_argument("-i", "--interval", type=int, default=1800)
    ap.add_argument("-t", "--ticket", type=str, default="")
    ap.add_argument("-b", "--special", type=str, default="")
    ap.add_argument("-d", "--date", type=str, default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.command == "check":
        if not args.ticket:
            print("Dung: check -t 5,19,20,26,44,53 -b 39")
            return
        cmd_check(load_history(),
                  [int(x) for x in args.ticket.replace(" ", "").split(",") if x],
                  int(args.special) if args.special else None, args.date or None)
        return

    history = load_history()
    if args.command == "backfill":
        cmd_backfill(history)
        return
    if args.command in ("update", "watch", "auto") or not history:
        history, _ = cmd_update()
        if args.command == "update":
            return
    if args.command == "auto":
        cmd_verify(history)
        print("")
        cmd_report(history)
        return
    if args.command == "report":
        cmd_report(history)
    elif args.command == "predict":
        cmd_predict(history)
    elif args.command == "seed":
        cmd_seed(history, args.num, args.force)
    elif args.command == "verify":
        cmd_verify(history)
    elif args.command == "audit":
        cmd_audit(history)
    elif args.command == "forecast":
        cmd_forecast(history)
    elif args.command == "dashboard":
        cmd_dashboard(history)
    elif args.command == "watch":
        cmd_watch(history, args.interval)


if __name__ == "__main__":
    main()
