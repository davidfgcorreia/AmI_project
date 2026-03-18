# IRE Calibration Procedure

## Install dependencies
```
cd calibration
pip install -r requirements.txt
```

---

## Step 1 — Distance calibration (one per ESP32)

**Goal:** find the true RSSI-to-distance curve for each radio.

**Setup:**
- Start the backend (`uvicorn app.main:app --reload`)
- Start the simulator or have the phone advertising BLE
- Note your session ID (shown in the frontend header)
- Use a tape measure; stand in a clear corridor or the middle of the room

**Run for each gateway:**
```
python calibrate.py distance --gateway esp32_A --session YOUR_SESSION_ID
python calibrate.py distance --gateway esp32_B --session YOUR_SESSION_ID
python calibrate.py distance --gateway esp32_C --session YOUR_SESSION_ID
```

The script will prompt you to stand at 0.5 m, 1 m, 1.5 m, 2 m, 3 m, 4 m, 5 m
from that ESP32.  At each distance **stand still for 20 seconds**.

**Tips:**
- Hold the phone at chest height, facing the ESP32
- Repeat the measurement with your body rotated 90° and average — body
  absorption changes RSSI by 3-6 dBm
- Do **not** move around or wave the phone during recording

---

## Step 2 — Analyse distance data → get new config values

```
python analyse.py distance
```

This prints a table of measured RSSI at each distance and then a box
with the exact values to paste into `backend/app/core/config.py`.

---

## Step 3 — Update config and restart backend

Open `backend/app/core/config.py` and replace:
```python
BLE_TX_POWER         = -70
BLE_FAR_DBM_PER_M    = 5.0
BLE_NEAR_RSSI        = -70.0
BLE_NEAR_DIST_AT_REF = 0.5
```
with the values printed by `analyse.py distance`.

Restart the backend.

---

## Step 4 — Position accuracy survey

**Goal:** walk the room on a grid and measure how accurate the trilateration is.

**Setup:**
- Mark 10-15 points on the floor with tape every ~1-2 m
- Measure each point's (x, y) from the bottom-left corner of the room
- Have the backend running with all 3 ESP32s active

```
python calibrate.py survey --session YOUR_SESSION_ID
```

At each point:
1. Enter the real coordinates: e.g. `3.5 2.0`
2. Stand still — the script records for ~10 seconds
3. Move to the next point

Type `done` when finished.

---

## Step 5 — Analyse survey results

```
python analyse.py survey           # table + ASCII heatmap
python analyse.py survey --plot    # adds a matplotlib scatter plot
```

The heatmap shows which areas of the room have good/poor coverage.
If a corner is consistently bad, it usually means that corner has
no line-of-sight to at least one ESP32 — the fix is to move that
ESP32 closer to that corner, or add a reflector.

---

## Iterating

If mean error > 1.5 m after tuning:

1. **Check collinearity** — the 3 ESP32s must not be on a straight line.
   Triangle area = 0.5 |det([B-A, C-A])| should be > 10 m².
2. **Check TX power offset** — each ESP32 board has a slightly different
   output. If one gateway's curve is shifted by >3 dBm compared to
   others, add a per-gateway offset in `config.py`.
3. **Reduce EMA alpha** — if the position jitters but is correct on
   average, lower `POS_ALPHA` in `routers/tracking.py` (e.g. 0.3).
4. **Increase EMA alpha** — if the position lags behind movement,
   raise it (e.g. 0.8).
