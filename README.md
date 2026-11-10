# Vietlott Mega 6/45 - Tracker + Du doan + Tu kiem chung

Cong cu theo doi ky quay, sinh du doan bang 9 model, va **tu cham diem chinh no**
bang walk-forward (chi dung du lieu truoc moi ky).

## Cai dat

Chi can Python 3.8+ (dung thu vien chuan, khong can pip install).

```
python vietlott_tracker.py update      # lay ket qua moi tu minhngoc.net.vn
python vietlott_tracker.py report      # trang thai + du doan + EV
python vietlott_tracker.py dashboard   # xuat vietlott_dashboard.html
```

## Lenh

| Lenh | Tac dung |
|---|---|
| `update` | Tai trang ket qua, ghi ky moi vao CSV, ghi du doan ky toi (co cot `late`) |
| `report` | Ky moi nhat, ve ban ra, jackpot, EV, 9 ve du doan + consensus |
| `predict` | Chi in ve du doan tung model cho ky toi |
| `seed -n 250` | Tao du doan lich su walk-forward de backtest |
| `verify` | Cham diem du doan: ty le trung, CI95, p-value so voi 13.33% |
| `audit` | Kiem dinh thong ke: chi2 deu, tong, trung ky truoc, ACF, jackpot |
| `check -t 1,2,3,4,5,6 [-d YYYY-MM-DD]` | Do ve |
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
model         ky  trung    ty le CI95               p (H0 13.33%)
cold_100     250    209   13.93% [12.21%,15.65%] 0.247
markov       250    207   13.80% [12.08%,15.52%] 0.297
overdue      250    203   13.53% [11.81%,15.25%] 0.410
random       250    200   13.33% [11.61%,15.05%] 0.500
hot_all      250    199   13.27% [11.55%,14.99%] 0.530
hot_100      250    199   13.27% [11.55%,14.99%] 0.530
decay        250    198   13.20% [11.48%,14.92%] 0.560
hot_30       250    189   12.60% [10.88%,14.32%] 0.798
balanced     250    186   12.40% [10.68%,14.12%] 0.856
```

**Khong model nao co loi the.** Ky vong ngau nhien la 6/45 = 13.33%;
moi model nam trong khoang nhieu thong ke.

## Phan co cong thuc that

```
Ve ban ra     T  = giai_ba / 0.0224410
Rollover      J1 = J0 + 2.836e6 * G2        (khi khong co nguoi trung, R2=0.984)
EV            EV = 1.370 + 0.9*J/C*(1-e^-lambda)/lambda
              lambda = 0.89 * T / C,   C = 8.145.060
```

Vi du 10/11/2026: T = 0.87 trieu ve -> hoa von khi J >= 81.9 ty.
Jackpot >= 100 ty moi co EV duong, va chi xay ra 1.6% so ky.

## File

| File | Noi dung |
|---|---|
| `vietlott_mega645_full_history.csv` | 1.586 ky (20/07/2016 -> 08/11/2026) |
| `vietlott_predictions.json` | Du doan da luu (co `late` de loai khoi cham diem) |
| `vietlott_dashboard.html` | Dashboard tu chua |
| `vietlott_analyze.py` | Script kiem dinh thong ke goc (scipy) |
| `vietlott_tracker.py` | Cong cu chinh |

## Nguon du lieu

`https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html`
(vietlott.vn tra 403 voi request khong phai trinh duyet).