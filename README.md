# Vietlott tracker - Mega 6/45 + Power 6/55

[![Update results and deploy dashboard](https://github.com/vammm121/vietlott-tracker/actions/workflows/update.yml/badge.svg)](https://github.com/vammm121/vietlott-tracker/actions/workflows/update.yml)

| Game | Dashboard | Du lieu |
|---|---|---|
| Mega 6/45 | https://vammm121.github.io/vietlott-tracker/ | [data.csv](https://vammm121.github.io/vietlott-tracker/data.csv) |
| Power 6/55 | https://vammm121.github.io/vietlott-tracker/power/ | [power/data.csv](https://vammm121.github.io/vietlott-tracker/power/data.csv) |

Hai cong cu doc lap (chi dung thu vien chuan Python; rieng `vietlott_analyze.py`
can `numpy` + `scipy`): theo doi ky quay, sinh du doan
bang 9 model, va **tu cham diem chinh no** bang walk-forward (chi dung du lieu truoc moi ky).

## Hai game

| | Mega 6/45 | Power 6/55 |
|---|---|---|
| So chon | 6 / 45 | 6 / 55 + 1 so dac biet |
| To hop | 8.145.060 | 28.989.675 |
| Giai | JP 6/6, N1 5/6, N2 4/6, N3 3/6 | JP1 6/6, JP2 5/6+DB, N1 5/6, N2 4/6, N3 3/6 |
| EV co dinh | 1.370d (13,7%) | 1.345d (13,5%) |
| Script | `vietlott_tracker.py` | `vietlott_power655.py` |
| Du lieu | 1.586 ky (2016-07-20) | 1.421 ky (2017-08-01) |
| Lich quay | T4 / T6 / CN | T3 / T5 / T7 |

## Tu dong hoa tren GitHub

Actions chay moi ngay quay cua ca hai game (11:20 UTC = 18:20 VN), tai ket qua, cham diem,
commit du lieu va deploy Pages. Xem `.github/workflows/update.yml`.

## Cai dat

Chi can Python 3.8+ (dung thu vien chuan, khong can pip install).

```
# Mega 6/45
python vietlott_tracker.py update | report | dashboard

# Power 6/55 (lan dau chay backfill de tai lich su)
python vietlott_power655.py backfill
python vietlott_power655.py update | report | dashboard
```

## Lenh (giong nhau cho ca hai script)

| Lenh | Tac dung |
|---|---|
| `update` | Tai trang ket qua, ghi ky moi vao CSV, ghi du doan ky toi (co cot `late`) |
| `report` | Ky moi nhat, ve ban ra, jackpot, EV, 9 ve du doan + consensus |
| `predict` | Chi in ve du doan tung model cho ky toi |
| `seed -n 250` | Tao du doan lich su walk-forward de backtest |
| `verify` | Cham diem du doan: ty le trung, CI95, p-value so voi 13.33% |
| `audit` | Kiem dinh thong ke: chi2 deu, tong, trung ky truoc, ACF, jackpot |
| `check -t 1,2,3,4,5,6 [-d YYYY-MM-DD]` | Do ve (Power: them `-b SO_DAC_BIET`) |
| `backfill` | Tai toan bo lich su (Power 6/55, resume-safe) |
| `forecast` | Bang EV theo muc jackpot + diem hoa von |
| `dashboard` | Xuat HTML dashboard (SVG, khong can internet) |
| `auto` | update + verify + report (dung cho Task Scheduler) |
| `watch -i 1800` | Vong lap theo doi moi 30 phut, keu chuong khi co ky moi |

## Tu dong hoa

```
.\setup_schedule.ps1             # xem truoc
.\setup_schedule.ps1 -Register   # dang ky Task Scheduler (18:10 Thu 4/6/CN)
```

## 9 model

`random`, `hot_all`, `hot_100`, `hot_30`, `cold_100`, `markov`, `overdue`, `decay`, `balanced`

- `markov`: P(so xuat hien ky toi | co mat ky nay)
- `decay`: tan suat co trong so mu 0.997 (uu tien gan day)
- `overdue`: so lau chua ra nhat
- `balanced`: mau "dep" (tong ~138, 3 le/3 chan, 3 nho, <=1 cap lien tiep, span ~32)
  ket hop tilt nhe theo tan suat + do tre

## Ket qua tu kiem chung (250 ky gan nhat, 13.500 lan chon)

```
model         ky  trung    ty le CI95               p p_Holm
cold_100     250    209   13.93% [12.21%,15.65%] 0.247 1.000
markov       250    207   13.80% [12.08%,15.52%] 0.297 1.000
overdue      250    203   13.53% [11.81%,15.25%] 0.410 1.000
random       250    200   13.33% [11.61%,15.05%] 0.500 1.000
hot_all      250    199   13.27% [11.55%,14.99%] 0.530 1.000
hot_100      250    199   13.27% [11.55%,14.99%] 0.530 1.000
decay        250    198   13.20% [11.48%,14.92%] 0.560 1.000
hot_30       250    189   12.60% [10.88%,14.32%] 0.798 1.000
balanced     250    186   12.40% [10.68%,14.12%] 0.856 1.000
```

**Khong model nao co loi the.** Ky vong ngau nhien la 6/45 = 13.33%;
moi model nam trong khoang nhieu thong ke.

## Power 6/55 - tu kiem chung (250 ky gan nhat)

```
model         ky  trung    ty le CI95                    p p_Holm
markov       250    190   12.67% [11.09%,14.24%] 0.015 0.131 (mat y nghia sau Holm)
random       250    181   12.07% [10.49%,13.64%] 0.075 0.602
balanced     250    178   11.87% [10.29%,13.44%] 0.117 0.820
hot_30       250    177   11.80% [10.22%,13.38%] 0.134 0.820
hot_all      250    174   11.60% [10.02%,13.18%] 0.195 0.977
overdue      250    164   10.93% [ 9.36%,12.51%] 0.488 1.000
cold_100     250    162   10.80% [ 9.22%,12.38%] 0.554 1.000
decay        250    157   10.47% [ 8.89%,12.04%] 0.709 1.000
hot_100      250    150   10.00% [ 8.42%,11.58%] 0.871 1.000

6 so: 1533/13500 = 11.36% (ky vong 10.91%)
```

`markov` co p=0.015 nhung **p_Holm = 0.131** -> chi la false positive do so sanh 9 model.
So dac biet: khong model nao vuot (overdue 3.60% vs 1.82%, p_Holm=0.157).

## Phan co cong thuc that

**Mega 6/45** (C = 8.145.060)
```
Ve ban ra   T  = giai_ba / 0.0224410
Rollover    J1 = J0 + 2.836e6 * G2        (khi khong co nguoi trung, R2=0.984)
EV          EV = 1.370 + 0.9*J/C*(1-e^-lambda)/lambda
            lambda = 0.89 * T / C
```

**Power 6/55** (C = 28.989.675)
```
Ve ban ra   T     = giai_ba / 0.0127112
lambda JP1  lam1  = 0.89 * T / C
lambda JP2  lam2  = 6 * lam1   (thuc te hoi thap hon vi nguoi choi chon so DB kem)
EV          EV    = 1.345 + 0.9*J1/C*s(lam1) + 0.9*6*J2/C*s(lam2)
```

Power 07/11/2026: 1,56 trieu ve -> hoa von khi **J1 >= 254 ty** (tinh ca JP2;
J1 trung binh 83 ty, p99 = 318 ty).
Mega hoa von ~82 ty (J trung binh ~30 ty, >= 100 ty chi 1,6% so ky).

## File

| File | Noi dung |
|---|---|
| `vietlott_mega645_full_history.csv` | Mega: 1.586 ky (20/07/2016 -> 08/11/2026) |
| `vietlott_predictions.json` | Mega: du doan da luu (co `late` de loai khoi cham diem) |
| `vietlott_dashboard.html` | Mega: dashboard tu chua |
| `vietlott_tracker.py` | Mega: cong cu chinh |
| `vietlott_analyze.py` | Mega: kiem dinh thong ke goc (scipy) |
| `vietlott_power655_full_history.csv` | Power: 1.421 ky (01/08/2017 -> 07/11/2026) |
| `vietlott_power655_predictions.json` | Power: du doan da luu |
| `vietlott_power655_dashboard.html` | Power: dashboard tu chua |
| `vietlott_power655.py` | Power: cong cu chinh (co `backfill`) |

## Nguon du lieu

```
mega : https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html
power: https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/power-6x55.html
```

(vietlott.vn tra 403 voi request khong phai trinh duyet.)

Power 6/55 chi hien 10 ky/trang nen `backfill` di nguoc theo ngay: 142 trang de lay
1421 ky. Chay lai duoc (resume) — chi tai ky con thieu.