#!/usr/bin/env python3
import json
import math
import os
import statistics
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.getenv("FURNACE_DISPLAY_HOST", "127.0.0.1")
PORT = int(os.getenv("FURNACE_DISPLAY_PORT", "8787"))
TOKEN = os.getenv("FURNACE_DISPLAY_TOKEN", "")
VM_URL = os.getenv(
    "FURNACE_VM_URL",
    "http://127.0.0.1:8428/api/v1/query?query=furnace_temp",
)
VM_API_BASE = os.getenv("FURNACE_VM_API_BASE", "http://127.0.0.1:8428/api/v1")
STALE_AFTER_SEC = int(os.getenv("FURNACE_STALE_AFTER_SEC", "300"))
EVENT_LOG = os.getenv("FURNACE_TUNING_EVENT_LOG", "/var/lib/furnace-display/tuning_events.jsonl")
TUNE_URL = os.getenv("FURNACE_TUNE_URL", "https://furnace.empyreanbuilders.com/tune")

NORMAL_LOW_F = 2320.0
NORMAL_HIGH_F = 2350.0
TARGET_F = 2335.0
TOO_COLD_F = 2000.0
OVERHEAT_F = 2400.0


def c_to_f(temp_c):
    return temp_c * 9.0 / 5.0 + 32.0


def classify(temp_c, age_sec):
    if age_sec is not None and age_sec > STALE_AFTER_SEC:
        return "stale"
    if temp_c is None:
        return "no_data"
    if temp_c > 1316:
        return "overheat"
    if temp_c < 1093:
        return "too_cold"
    if temp_c < 1204:
        return "standby"
    if temp_c < 1271:
        return "charging_recovery"
    if temp_c <= 1288:
        return "normal"
    return "high"


def vm_get(path, params):
    url = f"{VM_API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "furnace-display/0.0.1"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_temp():
    req = urllib.request.Request(VM_URL, headers={"User-Agent": "furnace-display/0.0.1"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    results = payload.get("data", {}).get("result", [])
    if not results:
        return {
            "ok": False,
            "error": "no furnace_temp result",
            "status": "no_data",
            "source": "furnace_temp",
        }

    ts_raw, value_raw = results[0]["value"]
    temp_c = float(value_raw)
    sample_ts = float(ts_raw)
    now = time.time()
    age_sec = max(0.0, now - sample_ts)
    temp_f = c_to_f(temp_c)

    tune = {}
    try:
        tune = build_tune_advisor(include_series=False).get("advisor", {})
    except Exception:
        tune = {}

    return {
        "ok": True,
        "c": round(temp_c, 2),
        "f": round(temp_f, 1),
        "status": classify(temp_c, age_sec),
        "age_sec": round(age_sec, 1),
        "sample_ts": sample_ts,
        "server_ts": now,
        "source": "furnace_temp",
        "tune_status": tune.get("state", "unknown"),
        "tune_severity": tune.get("severity", 0),
        "tune_label": tune.get("label", ""),
    }


def fetch_current_metric(metric):
    payload = vm_get("/query", {"query": metric})
    results = payload.get("data", {}).get("result", [])
    if not results:
        return None
    ts_raw, value_raw = results[0]["value"]
    return {"ts": float(ts_raw), "value": float(value_raw), "age_sec": max(0.0, time.time() - float(ts_raw))}


def fetch_series(metric, window_sec=10800, step_sec=60):
    now = time.time()
    payload = vm_get(
        "/query_range",
        {
            "query": metric,
            "start": f"{now - window_sec:.3f}",
            "end": f"{now:.3f}",
            "step": f"{step_sec}s",
        },
    )
    results = payload.get("data", {}).get("result", [])
    if not results:
        return []

    points = []
    for ts_raw, value_raw in results[0].get("values", []):
        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            points.append((float(ts_raw), value))
    return points


def convert_temp_series(points):
    return [(ts, c_to_f(value)) for ts, value in points]


def recent(points, seconds):
    if not points:
        return []
    cutoff = points[-1][0] - seconds
    return [(ts, value) for ts, value in points if ts >= cutoff]


def linear_slope_per_hour(points):
    if len(points) < 2:
        return None

    xs = [ts for ts, _ in points]
    ys = [value for _, value in points]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return None
    slope_per_sec = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    return slope_per_sec * 3600.0


def safe_mean(points):
    if not points:
        return None
    return statistics.fmean(value for _, value in points)


def safe_stdev(points):
    if len(points) < 2:
        return None
    return statistics.pstdev(value for _, value in points)


def latest_value(points):
    return points[-1][1] if points else None


def value_delta(points, seconds):
    window = recent(points, seconds)
    if len(window) < 2:
        return None
    return window[-1][1] - window[0][1]


def oscillation_score(temp_f_series):
    window = recent(temp_f_series, 7200)
    if len(window) < 20:
        return 0
    values = [value for _, value in window]
    amplitude = max(values) - min(values)
    midpoint = statistics.fmean(values)
    last_sign = 0
    flips = 0
    for value in values:
        if value > midpoint + 4:
            sign = 1
        elif value < midpoint - 4:
            sign = -1
        else:
            continue
        if last_sign and sign != last_sign:
            flips += 1
        last_sign = sign
    if amplitude > 25 and flips >= 3:
        return min(35, 10 + flips * 5)
    return 0


def fmt_num(value, digits=1, suffix=""):
    if value is None or not math.isfinite(value):
        return "--"
    return f"{value:.{digits}f}{suffix}"


def build_tune_advisor(include_series=True):
    temp_c_series = fetch_series("furnace_temp", 10800, 60)
    temp_f_series = convert_temp_series(temp_c_series)
    control_series = fetch_series("control_percent", 7200, 60)
    flame_series = fetch_series("flame_rms", 3600, 30)
    inlet_series = fetch_series("pressure_sensor2_psi", 3600, 60)
    outlet_series = fetch_series("pressure_sensor1_psi", 3600, 60)
    recup_top_series = fetch_series("recuperator_top", 3600, 60)
    recup_bottom_series = fetch_series("recuperator_bottom", 3600, 60)

    now = time.time()
    temp_f = latest_value(temp_f_series)
    temp_c = latest_value(temp_c_series)
    sample_ts = temp_f_series[-1][0] if temp_f_series else None
    age_sec = max(0.0, now - sample_ts) if sample_ts else None

    if temp_f is None:
        return {
            "ok": False,
            "server_ts": now,
            "advisor": {
                "state": "offline",
                "severity": 80,
                "label": "no furnace data",
                "diagnosis": "No furnace temperature data is available.",
                "action": "Check sensor pipeline before tuning.",
                "confidence": 0.0,
            },
        }

    slope_15 = linear_slope_per_hour(recent(temp_f_series, 900))
    slope_60 = linear_slope_per_hour(recent(temp_f_series, 3600))
    temp_std_60 = safe_stdev(recent(temp_f_series, 3600))
    control = latest_value(control_series)
    control_delta_10 = value_delta(control_series, 600)
    flame = latest_value(flame_series)
    flame_std_30 = safe_stdev(recent(flame_series, 1800))
    inlet = latest_value(inlet_series)
    outlet = latest_value(outlet_series)
    recup_top = latest_value(recup_top_series)
    recup_bottom = latest_value(recup_bottom_series)
    osc = oscillation_score(temp_f_series)

    distance_from_band = 0.0
    if temp_f < NORMAL_LOW_F:
        distance_from_band = NORMAL_LOW_F - temp_f
    elif temp_f > NORMAL_HIGH_F:
        distance_from_band = temp_f - NORMAL_HIGH_F

    severity = min(100, int(distance_from_band * 1.7 + abs(slope_60 or 0) * 0.25 + osc))
    state = "optimal"
    label = "holding band"
    diagnosis = "Furnace is inside the normal melt band with no strong tuning signal."
    action = "Hold. Do not tune unless you see a separate combustion symptom."
    confidence = 0.45

    temp_values_3h = [value for _, value in temp_f_series]
    recent_min = min(temp_values_3h) if temp_values_3h else temp_f
    charge_like = temp_f < NORMAL_LOW_F and slope_15 is not None and slope_15 > 8 and recent_min < temp_f - 25
    control_high = control is not None and control >= 70
    control_low = control is not None and control <= 35

    if age_sec is not None and age_sec > STALE_AFTER_SEC:
        state = "offline"
        severity = 75
        label = "telemetry stale"
        diagnosis = f"Last furnace sample is {age_sec:.0f}s old."
        action = "Do not tune from stale data. Fix telemetry first."
        confidence = 0.85
    elif temp_f >= OVERHEAT_F:
        state = "unsafe"
        severity = 95
        label = "overheat"
        diagnosis = "Temperature is above the configured overheat threshold."
        action = "Reduce heat demand/fuel and verify the Partlow, Modutrol, and gas train immediately."
        confidence = 0.9
    elif temp_f <= TOO_COLD_F:
        state = "unsafe"
        severity = 90
        label = "too cold"
        diagnosis = "Temperature is below the configured furnace-failing threshold."
        action = "Verify flame, fuel supply, air train, and sensor health before PID tuning."
        confidence = 0.9
    elif osc:
        state = "intervene"
        severity = max(severity, 55 + osc)
        label = "hunting"
        diagnosis = "Temperature is cycling around its recent midpoint."
        action = "PID is the first suspect: wider proportional band or less reset is safer than adding fuel."
        confidence = 0.62
    elif temp_f > NORMAL_HIGH_F:
        state = "drift" if severity < 55 else "intervene"
        label = "above band"
        if slope_15 is not None and slope_15 > 10:
            diagnosis = "Temperature is above the melt band and still rising."
            action = "Do not add fuel. Wait for lag to reveal the peak; if sustained, reduce fuel trim or soften controller action."
        elif control_low:
            diagnosis = "Temperature is high while controller output is modest."
            action = "This looks like stored heat or rich trim, not a need for more PID gain. Hold or reduce fuel only if it stays high."
        else:
            diagnosis = "Temperature is above normal band without a strong oscillation signature."
            action = "Hold adjustments until trend confirms whether it is settling or continuing upward."
        confidence = 0.58
    elif temp_f < NORMAL_LOW_F:
        if charge_like:
            state = "watch"
            severity = max(25, min(severity, 45))
            label = "recovery"
            diagnosis = "This looks like a charge or recovery dip: low temperature with positive recovery slope."
            action = "Wait. Judge fuel/PID only if recovery slope stalls after the normal lag window."
            confidence = 0.55
        elif control_high and (slope_60 is None or slope_60 < 8):
            state = "intervene"
            severity = max(severity, 65)
            label = "fuel-air limited"
            diagnosis = "Controller appears to be asking for heat, but recovery is weak."
            action = "Combustion trim is more likely than PID: consider a small fuel-side adjustment, then wait before judging."
            confidence = 0.64
        elif not control_high and (slope_60 is None or slope_60 < 8):
            state = "drift"
            severity = max(severity, 45)
            label = "pid soft"
            diagnosis = "Temperature is below band, but output does not look pinned high."
            action = "PID may be too soft: proportional band/reset review is more plausible than blindly adding fuel."
            confidence = 0.52
        else:
            state = "watch"
            label = "recovering"
            diagnosis = "Temperature is below band, but the trend is moving in the right direction."
            action = "Wait through the furnace lag before touching fuel or PID."
            confidence = 0.55
    elif abs(slope_60 or 0) > 18:
        state = "watch"
        severity = max(severity, 25)
        label = "moving"
        diagnosis = "Temperature is inside band but moving faster than a stable hold."
        action = "Watch the next lag window. Avoid stacking adjustments."
        confidence = 0.5

    if state == "optimal" and temp_std_60 is not None and temp_std_60 > 7:
        state = "watch"
        severity = max(severity, 24)
        label = "noisy hold"
        diagnosis = "Temperature is in band, but the last hour is noisier than expected."
        action = "Watch flame stability and control movement before changing settings."
        confidence = 0.48

    if state in {"optimal", "watch"}:
        severity = min(severity, 49)
    elif state == "drift":
        severity = max(35, min(severity, 74))
    elif state == "intervene":
        severity = max(55, min(severity, 89))

    change_detected = False
    change_reason = ""
    if control_delta_10 is not None and abs(control_delta_10) >= 8:
        change_detected = True
        change_reason = f"control output moved {control_delta_10:+.1f}% in 10m"
    elif slope_15 is not None and slope_60 is not None and abs(slope_15 - slope_60) >= 35:
        change_detected = True
        change_reason = "temperature slope changed sharply"

    evidence = [
        {"label": "temp", "value": fmt_num(temp_f, 1, " F")},
        {"label": "15m slope", "value": fmt_num(slope_15, 1, " F/hr")},
        {"label": "60m slope", "value": fmt_num(slope_60, 1, " F/hr")},
        {"label": "control", "value": fmt_num(control, 1, "%")},
        {"label": "flame rms", "value": fmt_num(flame, 5)},
        {"label": "inlet psi", "value": fmt_num(inlet, 3)},
        {"label": "outlet psi", "value": fmt_num(outlet, 3)},
        {"label": "recup top", "value": fmt_num(recup_top, 1, " F")},
        {"label": "recup bottom", "value": fmt_num(recup_bottom, 1, " F")},
    ]

    body = {
        "ok": True,
        "server_ts": now,
        "public_url": TUNE_URL,
        "current": {
            "temp_f": round(temp_f, 1),
            "temp_c": round(temp_c, 2) if temp_c is not None else None,
            "age_sec": round(age_sec, 1) if age_sec is not None else None,
            "status": classify(temp_c, age_sec),
            "control_percent": round(control, 2) if control is not None else None,
            "flame_rms": flame,
            "inlet_psi": inlet,
            "outlet_psi": outlet,
            "recup_top_f": recup_top,
            "recup_bottom_f": recup_bottom,
        },
        "advisor": {
            "state": state,
            "severity": severity,
            "label": label,
            "diagnosis": diagnosis,
            "action": action,
            "confidence": round(confidence, 2),
            "change_detected": change_detected,
            "change_reason": change_reason,
        },
        "trends": {
            "slope_15_f_per_hr": round(slope_15, 2) if slope_15 is not None else None,
            "slope_60_f_per_hr": round(slope_60, 2) if slope_60 is not None else None,
            "temp_std_60": round(temp_std_60, 2) if temp_std_60 is not None else None,
            "control_delta_10": round(control_delta_10, 2) if control_delta_10 is not None else None,
            "flame_std_30": flame_std_30,
            "oscillation_score": osc,
        },
        "evidence": evidence,
    }

    if include_series:
        body["series"] = {
            "temp_f": [[round(ts), round(value, 1)] for ts, value in temp_f_series[-180:]],
            "control_percent": [[round(ts), round(value, 1)] for ts, value in control_series[-120:]],
        }

    return body


def append_event(record):
    os.makedirs(os.path.dirname(EVENT_LOG), exist_ok=True)
    with open(EVENT_LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


TUNE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lyon's Pyre Tune</title>
<style>
:root{--bg:#070910;--panel:rgba(17,26,38,.62);--line:rgba(122,226,255,.38);--cyan:#72e5ff;--amber:#ffbd5a;--red:#ff5268;--green:#54e08a;--text:#f3f8ff;--muted:#8fa4ba}
*{box-sizing:border-box} body{margin:0;min-height:100vh;background:radial-gradient(circle at 18% 8%,rgba(41,177,255,.34),transparent 34%),radial-gradient(circle at 88% 22%,rgba(255,162,53,.25),transparent 30%),linear-gradient(140deg,#070910,#111620 48%,#1c1209);color:var(--text);font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
body:before{content:"";position:fixed;inset:0;background:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.028) 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.75),transparent);pointer-events:none}
main{width:min(1100px,100%);margin:auto;padding:22px;position:relative}
.top{display:flex;gap:16px;align-items:flex-start;justify-content:space-between;margin-bottom:18px}.kicker{letter-spacing:.26em;color:var(--cyan);font-weight:800;font-size:12px}.title{font-size:clamp(34px,8vw,70px);line-height:.92;font-weight:900;margin:6px 0 0;text-shadow:0 0 28px rgba(114,229,255,.25)}.url{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}.card{border:1px solid var(--line);background:var(--panel);box-shadow:0 20px 80px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.12);backdrop-filter:blur(16px);border-radius:28px;padding:20px;overflow:hidden}.hero{min-height:282px;position:relative}.temp{font-size:clamp(66px,16vw,138px);line-height:.85;font-weight:950;letter-spacing:-.08em;margin:22px 0 8px;color:var(--amber);text-shadow:0 0 42px rgba(255,189,90,.34)}.state{display:inline-flex;gap:8px;align-items:center;border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:9px 13px;background:rgba(255,255,255,.08);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.dot{width:12px;height:12px;border-radius:99px;background:var(--green);box-shadow:0 0 18px currentColor}.state.watch .dot{background:var(--cyan)}.state.drift .dot{background:var(--amber)}.state.intervene .dot,.state.unsafe .dot,.state.offline .dot{background:var(--red)}
.meter{height:12px;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden;margin-top:18px}.bar{height:100%;width:0;background:linear-gradient(90deg,var(--green),var(--amber),var(--red));box-shadow:0 0 22px rgba(255,189,90,.45)}
h2{margin:0 0 12px;font-size:13px;color:var(--muted);letter-spacing:.2em;text-transform:uppercase}.diagnosis{font-size:22px;line-height:1.18;margin:0 0 14px}.action{font-size:18px;line-height:1.32;color:#d8ecff;margin:0}.evidence{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.pill{border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:11px;background:rgba(255,255,255,.055)}.pill b{display:block;font-size:12px;color:var(--muted);font-weight:700}.pill span{font-size:18px;font-weight:850}
svg{width:100%;height:150px;display:block;margin-top:14px}.trace{fill:none;stroke:var(--amber);stroke-width:3;filter:drop-shadow(0 0 8px rgba(255,189,90,.55))}.axis{stroke:rgba(255,255,255,.1);stroke-width:1}.prompt{display:none;margin-top:16px}.prompt.show{display:block}.buttons{display:flex;flex-wrap:wrap;gap:9px;margin-top:12px}button{border:1px solid rgba(114,229,255,.42);background:rgba(12,36,54,.78);color:#e8fbff;border-radius:999px;padding:11px 14px;font-weight:850;cursor:pointer}button.alt{border-color:rgba(255,255,255,.18);background:rgba(255,255,255,.08);color:#d8dee9}.small{color:var(--muted);font-size:13px;line-height:1.4}.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#0e1824;border:1px solid var(--line);border-radius:999px;padding:12px 16px;opacity:0;transition:.2s}.toast.show{opacity:1}
@media(max-width:820px){main{padding:16px}.top{display:block}.grid{grid-template-columns:1fr}.evidence{grid-template-columns:repeat(2,1fr)}.card{border-radius:22px;padding:16px}}
</style>
</head>
<body>
<main>
  <section class="top">
    <div><div class="kicker">LYON'S PYRE</div><div class="title">Tuning Advisor</div></div>
    <div class="url" id="url"></div>
  </section>
  <section class="grid">
    <article class="card hero">
      <h2>Current Furnace</h2>
      <div class="temp" id="temp">-- F</div>
      <div class="state watch" id="state"><i class="dot"></i><span>loading</span></div>
      <div class="meter"><div class="bar" id="bar"></div></div>
      <svg id="chart" viewBox="0 0 600 150" preserveAspectRatio="none"></svg>
    </article>
    <article class="card">
      <h2>Advisor</h2>
      <p class="diagnosis" id="diagnosis">Reading the furnace...</p>
      <p class="action" id="action"></p>
      <div class="prompt" id="prompt">
        <h2 id="promptTitle">Adjustment Detected</h2>
        <p class="small" id="promptText">If you changed something, two taps will teach the advisor what happened.</p>
        <div class="buttons" id="buttons"></div>
      </div>
    </article>
  </section>
  <section class="card" style="margin-top:16px">
    <h2>Evidence</h2>
    <div class="evidence" id="evidence"></div>
  </section>
</main>
<div class="toast" id="toast">saved</div>
<script>
const stage2 = {
  fuel:["opened 1/16","opened 1/8","opened 1/4","closed 1/16","closed 1/8","closed 1/4","unknown"],
  pid:["PB narrower","PB wider","reset increased","reset reduced","rate changed","setpoint changed","unknown"],
  proportionator:["richer","leaner","small move","large move","unknown"],
  impulse:["more signal","less signal","small move","large move","unknown"],
  charge:["charged glass","door/open working","intentional setback","unknown"],
  other:["helped","hurt","not sure","ignore"]
};
let selectedKind = null;
function cls(state){return "state " + (state || "watch")}
function showToast(text){const t=document.getElementById("toast");t.textContent=text;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),1600)}
function buttons(items, cb){const box=document.getElementById("buttons");box.innerHTML="";items.forEach(([id,label,alt])=>{const b=document.createElement("button");b.textContent=label;b.className=alt?"alt":"";b.onclick=()=>cb(id,label);box.appendChild(b)})}
function stageOne(reason){
  selectedKind=null;
  document.getElementById("prompt").classList.add("show");
  document.getElementById("promptTitle").textContent=reason?"Possible change detected":"Log an adjustment";
  document.getElementById("promptText").textContent=reason || "What did you change?";
  buttons([["fuel","Fuel needle"],["pid","PID"],["proportionator","Proportionator"],["impulse","Impulse valve"],["charge","Charge/Door"],["other","Other/Ignore",true]], (id)=>{
    selectedKind=id;
    document.getElementById("promptTitle").textContent="How did it change?";
    document.getElementById("promptText").textContent=id;
    buttons(stage2[id].map(x=>[x,x,x==="unknown" || x==="ignore"]), (detail)=>postEvent(id,detail));
  });
}
async function postEvent(kind, detail){
  await fetch("/event",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kind,detail,client_ts:Date.now()/1000})});
  showToast("adjustment saved");
  stageOne("");
}
function draw(points){
  const svg=document.getElementById("chart"); svg.innerHTML="";
  if(!points || points.length<2) return;
  const w=600,h=150,p=10;
  const xs=points.map(x=>x[0]), ys=points.map(x=>x[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys)-5, maxY=Math.max(...ys)+5;
  for(let i=1;i<4;i++){const y=i*h/4; const l=document.createElementNS("http://www.w3.org/2000/svg","line"); l.setAttribute("x1",0);l.setAttribute("x2",w);l.setAttribute("y1",y);l.setAttribute("y2",y);l.setAttribute("class","axis");svg.appendChild(l)}
  const d=points.map(([x,y],i)=>`${i?"L":"M"} ${p+(x-minX)/(maxX-minX||1)*(w-p*2)} ${h-p-(y-minY)/(maxY-minY||1)*(h-p*2)}`).join(" ");
  const path=document.createElementNS("http://www.w3.org/2000/svg","path"); path.setAttribute("d",d); path.setAttribute("class","trace"); svg.appendChild(path);
}
function render(d){
  document.getElementById("url").textContent=d.public_url || location.href;
  document.getElementById("temp").textContent=d.current ? `${d.current.temp_f.toFixed(1)} F` : "-- F";
  const a=d.advisor || {};
  const state=document.getElementById("state"); state.className=cls(a.state); state.querySelector("span").textContent=`${a.state || "unknown"} / ${a.label || ""}`;
  document.getElementById("bar").style.width=`${Math.min(100,Math.max(0,a.severity||0))}%`;
  document.getElementById("diagnosis").textContent=a.diagnosis || "No diagnosis yet.";
  document.getElementById("action").textContent=a.action || "";
  const ev=document.getElementById("evidence"); ev.innerHTML="";
  (d.evidence||[]).forEach(x=>{const p=document.createElement("div");p.className="pill";p.innerHTML=`<b>${x.label}</b><span>${x.value}</span>`;ev.appendChild(p)});
  draw(d.series && d.series.temp_f);
  if(a.change_detected) stageOne(a.change_reason);
}
async function refresh(){try{const r=await fetch("/tune.json",{cache:"no-store"}); render(await r.json())}catch(e){document.getElementById("diagnosis").textContent="Dashboard cannot reach advisor."}}
document.addEventListener("keydown",e=>{if(e.key==="l")stageOne("")});
document.querySelector(".hero").addEventListener("dblclick",()=>stageOne(""));
stageOne("");
refresh();
setInterval(refresh,5000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "FurnaceDisplay/0.0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, body):
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if not TOKEN:
            return False
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {TOKEN}"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_json(200, {"ok": True})
            return

        if parsed.path in {"/", "/tune"}:
            self.send_html(200, TUNE_HTML)
            return

        if parsed.path == "/tune.json":
            try:
                self.send_json(200, build_tune_advisor(include_series=True))
            except Exception as exc:
                self.send_json(502, {"ok": False, "error": str(exc), "status": "advisor_error"})
            return

        if parsed.path != "/temp":
            self.send_json(404, {"ok": False, "error": "not found"})
            return

        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            self.send_json(200, fetch_temp())
        except Exception as exc:
            self.send_json(502, {"ok": False, "error": str(exc), "status": "upstream_error"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/event":
            self.send_json(404, {"ok": False, "error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 4096:
            self.send_json(413, {"ok": False, "error": "invalid payload size"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            record = {
                "server_ts": time.time(),
                "remote": self.client_address[0],
                "kind": str(payload.get("kind", ""))[:40],
                "detail": str(payload.get("detail", ""))[:80],
                "client_ts": payload.get("client_ts"),
            }
            append_event(record)
            self.send_json(200, {"ok": True, "event": record})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})


def main():
    if not TOKEN:
        raise SystemExit("FURNACE_DISPLAY_TOKEN is required")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
