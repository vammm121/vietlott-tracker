#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vietlott Mega 6/45 - tracker, du doan nhieu model, tu kiem chung, dashboard.

Lenh chinh:
  python vietlott_tracker.py update        # lay ky moi + ghi du doan ky toi
  python vietlott_tracker.py report        # trang thai + du doan + EV
  python vietlott_tracker.py predict       # ve du doan tung model
  python vietlott_tracker.py seed -n 250   # tao du doan lich su (walk-forward)
  python vietlott_tracker.py verify        # cham diem du doan (tu kiem chung)
  python vietlott_tracker.py audit         # kiem dinh thong ke toan bo du lieu
  python vietlott_tracker.py check -t 1,2,3,4,5,6
  python vietlott_tracker.py forecast      # EV theo muc jackpot
  python vietlott_tracker.py dashboard     # xuat vietlott_dashboard.html
  python vietlott_tracker.py auto          # update + verify + report
  python vietlott_tracker.py watch -i 1800 # theo doi lien tuc
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

CSV = "vietlott_mega645_full_history.csv"
PRED = "vietlott_predictions.json"
HTML = "vietlott_dashboard.html"
SOURCE = "https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
C = comb(45, 6)
P1 = 6 * 39 / C
P2 = comb(6, 4) * comb(39, 2) / C
P3 = comb(6, 3) * comb(39, 3) / C
FIXED_EV = P1 * 10_000_000 + P2 * 300_000 + P3 * 30_000
TICKET = 10_000
CALIB = 0.89
DRAW_WEEKDAYS = {2, 4, 6}
DRAW_ICT = (18, 5)
ICT = timezone(timedelta(hours=7))
FIELDS = ["draw_id", "draw_date", "n1", "n2", "n3", "n4", "n5", "n6",
          "jackpot_vnd", "jackpot_winners", "giai_nhat_winners",
          "giai_nhi_winners", "giai_ba_winners"]
BLOCK = '<div class="boxkqxsdientoan">'
BAR = "=" * 74


def fetch(url=SOURCE, tries=3):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9",
    })
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + 2 * i)
    raise RuntimeError("khong tai duoc %s: %s" % (url, last))


def parse_page(html):
    out = []
    for b in html.split(BLOCK)[1:]:
        m_id = re.search(r"Kỳ vé:\s*<span[^>]*>#?(\d+)<", b)
        m_dt = re.search(r"quay th\w*\s+(\d{2}/\d{2}/\d{4})", b)
        nums = re.findall(r'class="finnish\d bool">(\d{2})<', b)
        if not (m_id and m_dt) or len(nums) != 6:
            continue

        def cnt(key):
            m = re.search(r'id="DT6X45_S_%s">\s*([\d,]+)' % key, b)
            return int(m.group(1).replace(",", "")) if m else 0

        mj = re.search(r'id="DT6X45_G_JACKPOT">\s*([\d,]+)', b)
        d = datetime.strptime(m_dt.group(1), "%d/%m/%Y").date()
        out.append({
            "draw_id": m_id.group(1).zfill(5), "draw_date": d.isoformat(),
            "nums": tuple(sorted(int(x) for x in nums)),
            "jackpot": int(mj.group(1).replace(",", "")) if mj else 0,
            "w_jackpot": cnt("JACKPOT"), "w_g1": cnt("G1"),
            "w_g2": cnt("G2"), "w_g3": cnt("G3"),
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
                    "jackpot": int(float(r["jackpot_vnd"])),
                    "w_jackpot": int(float(r["jackpot_winners"])),
                    "w_g1": int(float(r["giai_nhat_winners"])),
                    "w_g2": int(float(r["giai_nhi_winners"])),
                    "w_g3": int(float(r["giai_ba_winners"])),
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
                 "jackpot_vnd": r["jackpot"], "jackpot_winners": r["w_jackpot"],
                 "giai_nhat_winners": r["w_g1"], "giai_nhi_winners": r["w_g2"],
                 "giai_ba_winners": r["w_g3"]}
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


def draw_datetime(d):
    return datetime(d.year, d.month, d.day, DRAW_ICT[0], DRAW_ICT[1], tzinfo=ICT)


def next_draw(last_date):
    now = datetime.now(ICT)
    d = last_date + timedelta(days=1)
    while d.weekday() not in DRAW_WEEKDAYS:
        d += timedelta(days=1)
    while draw_datetime(d) <= now:
        d += timedelta(days=1)
        while d.weekday() not in DRAW_WEEKDAYS:
            d += timedelta(days=1)
    return draw_datetime(d)


def tickets_from_g3(g3):
    return g3 / P3


def jackpot_ev(jackpot, tickets):
    lam = max(tickets / C * CALIB, 1e-12)
    share = (1 - math.exp(-lam)) / lam
    return FIXED_EV + 0.9 * jackpot / C * share, lam, share


def breakeven_jackpot(tickets):
    lam = max(tickets / C * CALIB, 1e-12)
    share = (1 - math.exp(-lam)) / lam
    return (TICKET - FIXED_EV) * C / (0.9 * share)


def ev_verdict(ev):
    if ev >= TICKET:
        return "DUONG EV (co loi the toan hoc)"
    if ev >= 0.9 * TICKET:
        return "gan hoa von"
    return "am EV"


def top6(scores):
    return sorted(sorted(range(1, 46), key=lambda n: (-scores.get(n, 0), n))[:6])


def m_random(history, idx=0):
    return sorted(random.Random(7000 + idx).sample(range(1, 46), 6))


def m_hot(window=None):
    def f(history, idx=0):
        h = history[-window:] if window else history
        return top6(Counter(n for d in h for n in d["nums"]))
    return f


def m_cold(window=100):
    def f(history, idx=0):
        c = Counter(n for d in history[-window:] for n in d["nums"])
        return top6({n: -c.get(n, 0) for n in range(1, 46)})
    return f


def m_markov(history, idx=0):
    tr, ct = defaultdict(int), defaultdict(int)
    for a, b in zip(history, history[1:]):
        sb = set(b["nums"])
        for n in set(a["nums"]):
            ct[n] += 1
            if n in sb:
                tr[n] += 1
    return top6({n: tr[n] / ct[n] for n in ct if ct[n] > 10})


def m_overdue(history, idx=0):
    last = {}
    for i, d in enumerate(history):
        for n in d["nums"]:
            last[n] = i
    return top6({n: len(history) - last.get(n, -1) for n in range(1, 46)})


def m_decay(history, idx=0):
    sc = defaultdict(float)
    for k, d in enumerate(reversed(history)):
        for n in d["nums"]:
            sc[n] += 0.997 ** k
    return top6(sc)


def m_balanced(history, idx=0, samples=12000):
    freq = Counter(n for d in history for n in d["nums"])
    mean = len(history) * 6 / 45
    sdd = max(math.sqrt(mean * (1 - 6 / 45)), 1e-9)
    last = {}
    for i, d in enumerate(history):
        for n in d["nums"]:
            last[n] = i
    prev = set(history[-1]["nums"]) if history else set()

    def score(c):
        s, sm = set(c), sum(c)
        odd = sum(1 for x in c if x % 2)
        low = sum(1 for x in c if x <= 22)
        cons = sum(1 for x in c if x + 1 in s)
        span = max(c) - min(c)
        pen = (((sm - 138) / 29.0) ** 2 * 3.0 + abs(odd - 3) * 0.55
               + abs(low - 3) * 0.55 + max(0, cons - 1) * 0.85
               + ((span - 32) / 9.0) ** 2 * 0.6 + len(s & prev) * 0.35)
        z = sum((freq[n] - mean) / sdd for n in c) / 6.0
        od = sum(len(history) - 1 - last.get(n, -1) for n in c) / 6.0
        return pen - 0.9 * z - 0.006 * od

    rng = random.Random(9000 + idx)
    best, bs = None, None
    for _ in range(samples):
        c = tuple(sorted(rng.sample(range(1, 46), 6)))
        v = score(c)
        if bs is None or v < bs:
            best, bs = c, v
    return list(best)


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


def fmt(t):
    return "-".join("%02d" % x for x in t)


def draw_iv(history, idx):
    hist = history[:idx]
    return [{"model": name, "ticket": sorted(fn(hist, idx))} for name, fn in MODELS]


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
    nd = next_draw(date.fromisoformat(last["draw_date"]))
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
                     "late": late,
                     "created_at": datetime.now(ICT).isoformat(timespec="seconds")})
        added += 1
    if added:
        save_pred(rows)
    return added


def cmd_update(quiet=False):
    history = load_history()
    fresh = parse_page(fetch())
    if not fresh:
        print("Khong parse duoc du lieu tu nguon.")
        return history, []
    history, added = merge(history, fresh)
    record_next(history)
    if not quiet:
        if added:
            print("Da cap nhat %d ky moi:" % len(added))
            for r in added:
                print("  #%s %s  %s  jackpot %.2f ty  winners %d"
                      % (r["draw_id"], r["draw_date"], fmt(r["nums"]),
                         r["jackpot"] / 1e9, r["w_jackpot"]))
        else:
            print("Khong co ky moi (%d ky, moi nhat #%s %s)."
                  % (len(history), history[-1]["draw_id"], history[-1]["draw_date"]))
    return history, added


def cmd_report(history):
    if not history:
        print("Chua co du lieu. Chay: update")
        return
    last = history[-1]
    nd = next_draw(date.fromisoformat(last["draw_date"]))
    tk = tickets_from_g3(last["w_g3"])
    tk3 = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    ev, lam, _ = jackpot_ev(last["jackpot"], tk3)
    be = breakeven_jackpot(tk3)

    print(BAR)
    print("VIETLOTT MEGA 6/45 - TRANG THAI")
    print(BAR)
    print("Du lieu      : %d ky (%s -> %s)" % (len(history), history[0]["draw_date"], last["draw_date"]))
    print("Ky moi nhat  : #%s  %s  %s" % (last["draw_id"], last["draw_date"], fmt(last["nums"])))
    print("Jackpot ky do: %.3f ty (nguoi trung: %d)" % (last["jackpot"] / 1e9, last["w_jackpot"]))
    print("Ky ke tiep   : %s 18:05 ICT  (con %s)"
          % (nd.strftime("%Y-%m-%d"), nd - datetime.now(ICT)))
    print("")
    print("UOC TINH VE BAN RA")
    print("  ky vua roi : giai ba %d -> %.2f trieu ve" % (last["w_g3"], tk / 1e6))
    print("  TB 3 ky    : %.2f trieu ve" % (tk3 / 1e6))
    print("  lambda     : %.3f nguoi trung jackpot ky vong" % lam)
    print("  EV         : %.0f d/ve = co dinh %.0f + jackpot %.0f  -> %s"
          % (ev, FIXED_EV, ev - FIXED_EV, ev_verdict(ev)))
    print("  hoa von khi J >= %.1f ty" % (be / 1e9))
    print("")
    print("DU DOAN KY #%s (%s)" % (str(int(last["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d")))
    preds = draw_iv(history, len(history))
    for r in preds:
        print("  %-9s %s" % (r["model"], fmt(r["ticket"])))
    cons = Counter(n for r in preds for n in r["ticket"])
    print("  %-9s %s   <- dong thuan" % ("consensus", fmt(sorted(cons, key=lambda n: -cons[n])[:6])))
    print("")
    print("  Khong model nao co loi the - xem: verify / audit.")


def cmd_predict(history):
    if not history:
        print("Chua co du lieu.")
        return
    nd = next_draw(date.fromisoformat(history[-1]["draw_date"]))
    print("Ky #%s  %s" % (str(int(history[-1]["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d")))
    for r in draw_iv(history, len(history)):
        print("  %-9s %s" % (r["model"], fmt(r["ticket"])))


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
        for name, fn in MODELS:
            if (d, name) in have:
                continue
            rows.append({"draw_id": history[idx]["draw_id"], "draw_date": d,
                         "model": name, "ticket": sorted(fn(history[:idx], idx)),
                         "late": False, "created_at": "backfill"})
            added += 1
    save_pred(rows)
    print("Da tao %d du doan lich su tren %d ky." % (added, len(history) - start))


def binom_p(k, n, p):
    if n == 0:
        return 1.0
    mu, sdd = n * p, math.sqrt(n * p * (1 - p))
    return 0.5 * math.erfc(((k - mu) / sdd if sdd else 0) / math.sqrt(2))


def verify_stats(history):
    preds = load_pred()
    bydate = {r["draw_date"]: r for r in history}
    agg = defaultdict(lambda: [0, 0, 0])
    for p in preds:
        if p.get("late"):
            continue
        d = bydate.get(p["draw_date"])
        if not d:
            continue
        m = agg[p["model"]]
        m[0] += len(set(p["ticket"]) & set(d["nums"]))
        m[1] += 6
        m[2] += 1
    rows = []
    for name, (hits, picks, n) in agg.items():
        if not picks:
            continue
        sdd = math.sqrt(picks * (6 / 45) * (1 - 6 / 45))
        rows.append({"model": name, "draws": n, "hits": hits, "picks": picks,
                     "rate": hits / picks,
                     "lo": (hits - 1.96 * sdd) / picks,
                     "hi": (hits + 1.96 * sdd) / picks,
                     "p": binom_p(hits, picks, 6 / 45)})
    rows.sort(key=lambda r: -r["rate"])
    return rows


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
    print("%-10s %5s %6s %8s %-18s %s" % ("model", "ky", "trung", "ty le", "CI95", "p (H0 13.33%)"))
    for r in rows:
        flag = " <-- lech" if r["p"] < 0.05 else ""
        print("%-10s %5d %6d %7.2f%% [%5.2f%%,%5.2f%%] %.3f%s"
              % (r["model"], r["draws"], r["hits"], 100 * r["rate"],
                 100 * r["lo"], 100 * r["hi"], r["p"], flag))
    tot_h = sum(r["hits"] for r in rows)
    tot_p = sum(r["picks"] for r in rows)
    print("")
    print("Tong: %d lan chon / %d trung = %.2f%% (ky vong 13.33%%)"
          % (tot_p, tot_h, 100 * tot_h / tot_p))
    print("Cho cham (ky toi): %d" % pending)
    print("Ket luan: chi co loi the khi |rate-13.33%| vuot ~2 do lech chuan.")


def cmd_audit(history):
    if len(history) < 100:
        print("Can it nhat 100 ky.")
        return
    n = len(history)
    ds = [r["nums"] for r in history]
    freq = Counter(x for d in ds for x in d)
    obs = [freq.get(i, 0) for i in range(1, 46)]
    exp = n * 6 / 45
    chi2 = sum((o - exp) ** 2 / exp for o in obs)
    sums = [sum(d) for d in ds]
    rep = Counter(len(set(a) & set(b)) for a, b in zip(ds, ds[1:]))
    print(BAR)
    print("KIEM DINH DU LIEU (%d ky, %s -> %s)" % (n, history[0]["draw_date"], history[-1]["draw_date"]))
    print(BAR)
    print("1) 45 so deu? chi2=%.2f df=44 p=%.4f -> %s"
          % (chi2, 1 - chi2_cdf(chi2, 44),
             "deu/ngau nhien" if 1 - chi2_cdf(chi2, 44) > 0.05 else "lech"))
    print("   min=%d max=%d TB=%.2f" % (min(obs), max(obs), exp))
    print("2) tong 6 so: TB %.2f (lt 138), sd %.2f (lt 29.95)" % (sum(sums) / n, sd(sums)))
    print("3) trung ky truoc: TB %.3f (lt 0.800) | %s"
          % (sum(len(set(a) & set(b)) for a, b in zip(ds, ds[1:])) / (n - 1),
             dict(sorted(rep.items()))))
    print("4) ACF tong: lag1=%.3f lag2=%.3f lag3=%.3f lag5=%.3f"
          % (corr(sums[:-1], sums[1:]), corr(sums[:-2], sums[2:]),
             corr(sums[:-3], sums[3:]), corr(sums[:-5], sums[5:])))
    jps = [r["jackpot"] for r in history]
    print("5) jackpot: min %.1f ty, TB %.1f ty, max %.1f ty, ACF1 %.3f"
          % (min(jps) / 1e9, sum(jps) / n / 1e9, max(jps) / 1e9,
             corr(jps[:-1], jps[1:])))
    print("")
    print("KET LUAN: khong phep thu nao bac bo ngau nhien doc lap.")
    print("Khong co cong thuc cho 6 so; chi co cong thuc cho giai thuong:")
    print("  T  = giai_ba / %.6f" % P3)
    print("  J' = J + 2.836e6 * G2  (khi khong co nguoi trung)")
    print("  EV = %.0f + 0.9*J/C*(1-e^-lambda)/lambda,  lambda = %.2f*T/C" % (FIXED_EV, CALIB))


def cmd_check(history, ticket, day=None):
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
    if len(t) != 6 or min(t) < 1 or max(t) > 45:
        print("Ve khong hop le: can 6 so khac nhau trong 1..45")
        return
    match = len(set(t) & set(row["nums"]))
    table = {6: (row["jackpot"], "JACKPOT"), 5: (10_000_000, "Giai nhat"),
             4: (300_000, "Giai nhi"), 3: (30_000, "Giai ba")}
    prize, name = table.get(match, (0, "Khong trung"))
    print("Ky #%s %s  ket qua %s" % (row["draw_id"], row["draw_date"], fmt(row["nums"])))
    print("Ve       %s" % fmt(t))
    print("Trung    %d/6  ->  %s%s" % (match, name, ("  %s d" % format(prize, ",")) if prize else ""))
    if prize:
        print("Lai/lo   %s d (ve 10.000 d)" % format(prize - TICKET, ","))


def cmd_forecast(history):
    if not history:
        print("Chua co du lieu.")
        return
    tk = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    print(BAR)
    print("EV THEO MUC JACKPOT (gia dinh %.2f trieu ve, PIT 10%%)" % (tk / 1e6))
    print(BAR)
    print("%-10s %-10s %-11s %-10s %s" % ("jackpot", "lambda", "EV/ve", "so 10k", "ket luan"))
    for j in [10e9, 20e9, 30e9, 50e9, 80e9, 100e9, 120e9, 150e9, 180e9, 220e9]:
        ev, lam, _ = jackpot_ev(j, tk)
        print("%-10s %-10.3f %-11.0f %-10s %s"
              % ("%.0f ty" % (j / 1e9), lam, ev, "%+.0f%%" % (100 * (ev / TICKET - 1)), ev_verdict(ev)))
    print("")
    print("Hoa von: J >= %.1f ty voi %.2f trieu ve." % (breakeven_jackpot(tk) / 1e9, tk / 1e6))
    print("Thuc te: J >= 100 ty chiem %.1f%% so ky; >= 150 ty chiem %.1f%%."
          % (100 * sum(1 for r in history if r["jackpot"] >= 100e9) / len(history),
             100 * sum(1 for r in history if r["jackpot"] >= 150e9) / len(history)))


def svg_bar(values, labels, w=880, h=260, color="#4ade80", hires=None, lo=None):
    lo_v = lo if lo is not None else min(values)
    rng = max(max(values) - lo_v, 1)
    n = len(values)
    bw = w / n
    parts = []
    for i, v in enumerate(values):
        bh = (v - lo_v) / rng * (h - 40)
        c = (hires or {}).get(i, color)
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="2"/>'
                     % (i * bw + 2, h - 24 - bh, bw - 4, bh, c))
        parts.append('<text x="%.1f" y="%.1f" fill="#94a3b8" font-size="9" '
                     'text-anchor="middle">%s</text>' % (i * bw + bw / 2, h - 8, labels[i]))
    return ('<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg">%s</svg>'
            % (w, h, "".join(parts)))


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
--green:#4ade80;--red:#f87171;--blue:#38bdf8;--gold:#fbbf24}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}
h1 span{color:var(--gold)}
.sub{color:var(--dim);margin-bottom:20px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:18px}
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
.balls{display:flex;gap:8px;flex-wrap:wrap}
.ball{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;
font-weight:600;background:#1c2f4d;border:1px solid #2c4570}
.ball.j{background:#3b2a05;border-color:#7c5a12;color:var(--gold)}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;
border:1px solid var(--line);color:var(--dim)}
.tag.ok{color:var(--green);border-color:#14532d;background:#052e16}
.tag.bad{color:var(--red);border-color:#7f1d1d;background:#2b0b0b}
.tag.warn{color:var(--gold);border-color:#78350f;background:#2a1a05}
.muted{color:var(--dim);font-size:12px}
.row{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid var(--line)}
.row:last-child{border:0}
code{background:#0a1526;padding:1px 6px;border-radius:5px;font-size:12px;color:#a5d6ff}
"""


def cmd_dashboard(history):
    if not history:
        print("Chua co du lieu.")
        return
    last = history[-1]
    nd = next_draw(date.fromisoformat(last["draw_date"]))
    tk3 = sum(tickets_from_g3(r["w_g3"]) for r in history[-3:]) / 3.0
    ev, lam, _ = jackpot_ev(last["jackpot"], tk3)
    be = breakeven_jackpot(tk3)
    preds = draw_iv(history, len(history))
    vrows = verify_stats(history)
    freq = Counter(n for r in history for n in r["nums"])
    sums = [sum(r["nums"]) for r in history]

    bins = [0] * 13
    for s in sums:
        bins[min(12, max(0, (s - 45) // 15))] += 1
    labels = ["%d" % (45 + 15 * i) for i in range(13)]

    hires = {}
    for n in sorted(freq, key=lambda n: -freq[n])[:5]:
        hires[n - 1] = "#fbbf24"
    for n in sorted(freq, key=lambda n: freq[n])[:5]:
        hires[n - 1] = "#64748b"

    jp_series = [r["jackpot"] / 1e9 for r in history[-400:]]

    def tag(ok, txt):
        return '<span class="tag %s">%s</span>' % ("ok" if ok else "bad", txt)

    ev_cls = "ok" if ev >= TICKET else ("warn" if ev >= 0.9 * TICKET else "bad")
    rows_draws = "".join(
        "<tr><td>#%s</td><td>%s</td><td class='muted'>%s</td>"
        "<td class='num'>%.2f ty</td><td class='num'>%d</td><td class='num'>%d</td>"
        "<td class='num'>%.2f tr</td></tr>"
        % (r["draw_id"], r["draw_date"], fmt(r["nums"]), r["jackpot"] / 1e9,
           r["w_jackpot"], r["w_g3"], tickets_from_g3(r["w_g3"]) / 1e6)
        for r in history[-12:][::-1])
    rows_pred = "".join(
        "<tr><td>%s</td><td class='muted'>%s</td></tr>" % (r["model"], fmt(r["ticket"]))
        for r in preds)
    rows_ver = "".join(
        "<tr><td>%s</td><td class='num'>%d</td><td class='num'>%d</td>"
        "<td class='num'>%.2f%%</td><td class='num muted'>[%.2f%%, %.2f%%]</td>"
        "<td>%s</td></tr>"
        % (r["model"], r["draws"], r["hits"], 100 * r["rate"],
           100 * r["lo"], 100 * r["hi"], tag(r["p"] >= 0.05, "p=%.3f" % r["p"]))
        for r in vrows)
    cons = Counter(n for r in preds for n in r["ticket"])
    cons_t = sorted(cons, key=lambda n: -cons[n])[:6]

    html = (
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Vietlott Mega 6/45 - Tracker</title><style>" + CSS +
        "</style></head><body><div class='wrap'>"
        "<h1>Vietlott <span>Mega 6/45</span> - Tracker</h1>"
        "<div class='sub'>Cap nhat %s (ICT) &middot; %d ky &middot; %s &rarr; %s "
        "&middot; nguon minhngoc.net.vn</div>"
        % (datetime.now(ICT).strftime("%Y-%m-%d %H:%M"), len(history),
           history[0]["draw_date"], last["draw_date"]) +
        "<div class='grid'>"
        "<div class='card'><h3>Ky moi nhat</h3><div class='kpi'>#%s</div>"
        "<div class='muted'>%s</div><div class='balls' style='margin-top:10px'>%s</div></div>"
        "<div class='card'><h3>Jackpot hien tai</h3>"
        "<div class='kpi'>%.2f <small>ty d</small></div>"
        "<div class='muted'>%d nguoi trung o ky vua roi</div></div>"
        "<div class='card'><h3>Ve ban ra (TB 3 ky)</h3>"
        "<div class='kpi'>%.2f <small>trieu ve</small></div>"
        "<div class='muted'>lambda = %.3f</div></div>"
        "<div class='card'><h3>EV moi ve</h3><div class='kpi'>%s <small>d</small></div>"
        "<div class='muted'>hoa von khi J &ge; %.1f ty &middot; "
        "<span class='tag %s'>%s</span></div></div></div>"
        % (last["draw_id"], last["draw_date"],
           "".join("<div class='ball'>%02d</div>" % x for x in last["nums"]),
           last["jackpot"] / 1e9, last["w_jackpot"], tk3 / 1e6, lam,
           format(round(ev), ","), be / 1e9, ev_cls, ev_verdict(ev)) +
        "<div class='panel'><h3>Du doan ky #%s - %s 18:05 ICT</h3>"
        "<div class='balls' style='margin-bottom:14px'>%s</div>"
        "<table><thead><tr><th>Model</th><th>Ve</th></tr></thead><tbody>%s</tbody></table>"
        "<div class='muted' style='margin-top:10px'>Dong thuan: %s</div></div>"
        % (str(int(last["draw_id"]) + 1).zfill(5), nd.strftime("%Y-%m-%d"),
           "".join("<div class='ball j'>%02d</div>" % x for x in cons_t),
           rows_pred, fmt(sorted(cons_t))) +
        "<div class='panel'><h3>Tu kiem chung (walk-forward)</h3>"
        "<table><thead><tr><th>Model</th><th class='num'>Ky</th><th class='num'>Trung</th>"
        "<th class='num'>Ty le</th><th class='num'>CI95</th><th>p (H0 13.33%%)</th>"
        "</tr></thead><tbody>%s</tbody></table>"
        "<div class='muted' style='margin-top:10px'>Ky vong ngau nhien 13.33%%. "
        "p &gt; 0.05 = khong co loi the.</div></div>" % rows_ver +
        "<div class='grid' style='grid-template-columns:1fr 1fr'>"
        "<div class='panel'><h3>Tan suat 45 so (vang=nong, xam=lanh)</h3>%s</div>"
        "<div class='panel'><h3>Phan bo tong 6 so</h3>%s</div></div>"
        % (svg_bar([freq.get(i, 0) for i in range(1, 46)],
                   [str(i) for i in range(1, 46)], hires=hires),
           svg_bar(bins, labels, color="#38bdf8", lo=0)) +
        "<div class='panel'><h3>Jackpot 400 ky gan nhat (ty d)</h3>%s</div>"
        % svg_line(jp_series) +
        "<div class='panel'><h3>12 ky gan nhat</h3>"
        "<table><thead><tr><th>Ky</th><th>Ngay</th><th>Ket qua</th>"
        "<th class='num'>Jackpot</th><th class='num'>Trung</th>"
        "<th class='num'>Giai ba</th><th class='num'>Ve uoc</th></tr></thead>"
        "<tbody>%s</tbody></table></div>" % rows_draws +
        "<div class='panel'><h3>Cong thuc da kiem chung</h3>"
        "<div class='row'><span>Ve ban ra</span><code>T = giai_ba / %.6f</code></div>"
        "<div class='row'><span>Rollover</span><code>J' = J + 2.836e6 * G2</code></div>"
        "<div class='row'><span>EV</span><code>%.0f + 0.9*J/C*(1-e^-lambda)/lambda</code></div>"
        "<div class='row'><span>Xac suat trung</span><code>1 / 8.145.060</code></div>"
        "<div class='muted' style='margin-top:10px'>6 so khong co quy luat: "
        "chi2 p=0.97, ACF ~0, backtest 250 ky moi model ~13.3%%.</div></div>"
        "</div></body></html>" % (P3, FIXED_EV))
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("Da xuat %s (%d KB)." % (HTML, os.path.getsize(HTML) // 1024))


def corr(a, b):
    n = len(a)
    if n < 2:
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
    return 1 - gammainc_upper(a, xx)


def gammainc_upper(a, x):
    b, c = x + 1 - a, 1e300
    d = 1.0 / (x + 1 - a)
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
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def cmd_watch(history, interval):
    print("Theo doi moi %d giay. Ctrl+C de dung." % interval)
    while True:
        try:
            history, added = cmd_update(quiet=True)
            if added:
                print("\a[KY MOI] " + ", ".join(
                    "#%s %s %s" % (r["draw_id"], r["draw_date"], fmt(r["nums"])) for r in added))
                cmd_report(history)
            else:
                print("[%s] chua co ky moi (moi nhat #%s)"
                      % (datetime.now(ICT).strftime("%Y-%m-%d %H:%M"), history[-1]["draw_id"]))
        except Exception as e:
            print("Loi: %s" % e)
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="Vietlott Mega 6/45 tracker")
    ap.add_argument("command", nargs="?", default="report",
                    choices=["update", "report", "watch", "predict", "seed", "verify",
                             "audit", "check", "forecast", "dashboard", "auto"])
    ap.add_argument("-n", "--num", type=int, default=250)
    ap.add_argument("-i", "--interval", type=int, default=1800)
    ap.add_argument("-t", "--ticket", type=str, default="")
    ap.add_argument("-d", "--date", type=str, default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.command == "check":
        if not args.ticket:
            print("Dung: check -t 1,2,3,4,5,6 [-d YYYY-MM-DD]")
            return
        cmd_check(load_history(),
                  [int(x) for x in args.ticket.replace(" ", "").split(",") if x],
                  args.date or None)
        return

    history = load_history()
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
