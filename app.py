import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import time
import sqlite3
from datetime import datetime

# ==========================================
# 1. 页面配置 + CSS
# ==========================================
st.set_page_config(page_title="PyrLac Glow · Demo", page_icon="🧬", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    .formula-banner {
        background: linear-gradient(90deg, #433262 0%, #6A3AB2 100%);
        color: white; padding: 14px; border-radius: 10px;
        text-align: center; font-size: 18px; font-weight: 700;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(106,58,178,0.3);
    }
    .maintenance-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffe8a1 100%);
        color: #856404; border-left: 6px solid #ffc107;
        padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;
        font-weight: 600; font-size: 14px;
    }
    .diagnosis-card {
        padding: 20px; border-radius: 12px; margin-bottom: 15px;
        background-color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border-left: 8px solid #ccc;
    }
    .card-title { font-size: 20px; font-weight: 800; color: #333; margin-bottom: 10px; }
    .card-data { font-size: 15px; color: #555; margin-bottom: 5px; }
    .card-sub { font-size: 12px; color: #888; margin-top: 8px; line-height: 1.4; }
    .card-note { font-size: 11px; color: #999; margin-top: 4px; font-style: italic; }
    .card-badge {
        display: inline-block; padding: 6px 12px; border-radius: 20px;
        font-size: 14px; font-weight: 700; color: white; margin-top: 10px;
    }
    .bg-normal { background-color: #28a745; }
    .bg-lac { background-color: #D97706; }
    .bg-pdhc { background-color: #6f42c1; }
    .bg-cancer { background-color: #dc3545; }
    .bg-borderline { background-color: #6c757d; }
    .bg-invalid { background-color: #adb5bd; }
    .border-normal { border-left-color: #28a745; }
    .border-lac { border-left-color: #D97706; }
    .border-pdhc { border-left-color: #6f42c1; }
    .border-cancer { border-left-color: #dc3545; }
    .border-borderline { border-left-color: #6c757d; }
    .border-invalid { border-left-color: #adb5bd; }
    .live-banner {
        background: linear-gradient(90deg, #1f2937 0%, #374151 100%);
        color: #10b981; padding: 10px 16px; border-radius: 8px;
        font-family: 'SF Mono', Menlo, Consolas, monospace;
        font-size: 13px; margin-bottom: 16px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .live-dot {
        display: inline-block; width: 8px; height: 8px;
        background: #10b981; border-radius: 50%;
        margin-right: 8px; animation: pulse 1.2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow · Interactive Demo")
st.markdown('<div class="formula-banner">Ratiometric Signal (Ratio) = ADC (485 nm) / ADC (420 nm)</div>', unsafe_allow_html=True)

# ==========================================
# 2. SQLite
# ==========================================
@st.cache_resource
def get_db():
    conn = sqlite3.connect('pyrlac.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS calibration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, probe TEXT, slope REAL, intercept REAL, r2 REAL, batch TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS his_sync (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, batch_id TEXT, n_records INTEGER)''')
    conn.commit()
    return conn

db = get_db()


def save_calibration(probe, slope, intercept, r2):
    db.execute(
        "INSERT INTO calibration (ts, probe, slope, intercept, r2, batch) VALUES (?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec='seconds'), probe, slope, intercept, r2, ""))
    db.commit()


def get_last_calibration(probe):
    cur = db.execute(
        "SELECT ts, slope, intercept, r2 FROM calibration WHERE probe=? ORDER BY id DESC LIMIT 1",
        (probe,))
    return cur.fetchone()


def log_his_sync(batch_id, n_records):
    db.execute(
        "INSERT INTO his_sync (ts, batch_id, n_records) VALUES (?,?,?)",
        (datetime.now().isoformat(timespec='seconds'), batch_id, n_records))
    db.commit()

# ==========================================
# 3. 演示帧序列
# ==========================================
DEMO_FRAMES = [
    {'label': '🟢 Baseline · Normal',
     'lac_420': 100.0, 'lac_485': 140.0, 'pyr_420': 100.0, 'pyr_485': 150.0,
     'note': 'Sample loaded · both markers within reference range.'},
    {'label': '🟡 Isolated Lactate Rise',
     'lac_420': 100.0, 'lac_485': 800.0, 'pyr_420': 100.0, 'pyr_485': 150.0,
     'note': 'Lactate signal rising sharply — suspect hypoperfusion / sepsis.'},
    {'label': '🟢 Recovery · Normal',
     'lac_420': 100.0, 'lac_485': 140.0, 'pyr_420': 100.0, 'pyr_485': 150.0,
     'note': 'Lactate signal normalized · continuing routine check.'},
    {'label': '🟣 Isolated Pyruvate Rise',
     'lac_420': 100.0, 'lac_485': 140.0, 'pyr_420': 100.0, 'pyr_485': 500.0,
     'note': 'Pyruvate signal elevated — suspect PDHC / vitamin B1 deficiency.'},
    {'label': '🔴 Dual Elevation · Warburg',
     'lac_420': 100.0, 'lac_485': 800.0, 'pyr_420': 100.0, 'pyr_485': 500.0,
     'note': 'Both markers elevated — flag High Cancer Risk (Warburg effect).'},
    {'label': '🟢 Reset · Back to Baseline',
     'lac_420': 100.0, 'lac_485': 140.0, 'pyr_420': 100.0, 'pyr_485': 150.0,
     'note': 'Demo complete · diagnostic sequence finished.'},
]

PRESETS = [
    ('🟢 Normal',           100.0, 140.0, 100.0, 150.0),
    ('🟡 High Lactate',     100.0, 800.0, 100.0, 150.0),
    ('🟣 High Pyruvate',    100.0, 140.0, 100.0, 500.0),
    ('🔴 High Cancer Risk', 100.0, 800.0, 100.0, 500.0),
]

# ==========================================
# 4. 初始化 widget keys + pending 应用
# ==========================================
DEFAULTS = {
    'm_lac_420': 100.0, 'm_lac_485': 140.0,
    'm_pyr_420': 100.0, 'm_pyr_485': 150.0,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# ★ 必须在 widget 渲染前应用 pending
for k in ['m_lac_420', 'm_lac_485', 'm_pyr_420', 'm_pyr_485']:
    pk = f'_pending_{k}'
    if pk in st.session_state:
        st.session_state[k] = st.session_state.pop(pk)

# ==========================================
# 5. 分类函数
# ==========================================
def classify(c_lac, c_pyr, th):
    lac_border = th['lac_lo'] <= c_lac <= th['lac_hi']
    pyr_border = th['pyr_lo'] <= c_pyr <= th['pyr_hi']
    if lac_border or pyr_border:
        parts = []
        if lac_border: parts.append("Lactate near threshold")
        if pyr_border: parts.append("Pyruvate near threshold")
        return {'status': "Borderline", 'sub': " · ".join(parts) + " — retest recommended",
                'badge_cls': 'bg-borderline', 'border_cls': 'border-borderline',
                'lac_flag': 'border' if lac_border else 'normal',
                'pyr_flag': 'border' if pyr_border else 'normal',
                'rec': "One or both markers fall within the borderline zone. "
                       "Retest is recommended before clinical interpretation."}
    lac_high = c_lac > th['lac_hi']
    pyr_high = c_pyr > th['pyr_hi']
    if lac_high and pyr_high:
        return {'status': "High Cancer Risk",
                'sub': "Dual elevation — metabolic reprogramming / Warburg effect",
                'badge_cls': 'bg-cancer', 'border_cls': 'border-cancer',
                'lac_flag': 'high', 'pyr_flag': 'high',
                'rec': "Both lactate and pyruvate are markedly elevated. This pattern is "
                       "consistent with enhanced aerobic glycolysis (Warburg effect) and has "
                       "been associated with malignancy and poor prognosis. However, severe "
                       "sepsis or other critical illness can also produce dual elevation. "
                       "Prompt clinical evaluation is strongly advised."}
    if lac_high:
        return {'status': "High Lactate",
                'sub': "Possible: shock, sepsis, liver failure, metformin, malignancy",
                'badge_cls': 'bg-lac', 'border_cls': 'border-lac',
                'lac_flag': 'high', 'pyr_flag': 'normal',
                'rec': "Isolated lactate elevation is non-specific. Consider: (A) tissue "
                       "hypoperfusion — shock, heart failure, severe anemia, ischemia; "
                       "(B) non-hypoxic metabolic causes — sepsis, liver failure, diabetic "
                       "ketoacidosis, seizures; (C) drugs/toxins — metformin, linezolid, "
                       "propofol, cyanide, alcohol; (D) malignancy (Warburg effect); "
                       "(E) inherited mitochondrial disorders. Clinical correlation and "
                       "repeat testing are required."}
    if pyr_high:
        return {'status': "High Pyruvate",
                'sub': "Possible: PDHC deficiency, vitamin B1 deficiency, pyruvate carboxylase deficiency",
                'badge_cls': 'bg-pdhc', 'border_cls': 'border-pdhc',
                'lac_flag': 'normal', 'pyr_flag': 'high',
                'rec': "Isolated pyruvate elevation suggests impaired pyruvate utilization. "
                       "Primary considerations include: (1) pyruvate dehydrogenase complex "
                       "(PDHC) deficiency — confirmed by enzyme assay or DNA testing; "
                       "(2) vitamin B1 (thiamine) deficiency — a reversible cause, especially "
                       "in malnutrition or alcohol dependence; (3) pyruvate carboxylase "
                       "deficiency and other inherited pyruvate oxidation disorders. "
                       "Recommend PDHC functional assessment and thiamine screening."}
    return {'status': "Normal", 'sub': "No obvious metabolic abnormality",
            'badge_cls': 'bg-normal', 'border_cls': 'border-normal',
            'lac_flag': 'normal', 'pyr_flag': 'normal',
            'rec': "No significant metabolic risk detected. Continue routine checkups."}


def fig17_steps(current: int):
    steps = ["1. Sample Input", "2. Probe Mode", "3. Scan & Calculate",
             "4. Joint Diagnosis", "5. HIS/LIS Sync"]
    html = '<div style="display:flex;gap:6px;margin-bottom:18px;">'
    for i, s in enumerate(steps, 1):
        if i < current:
            bg, fg, mark = "#28a745", "#fff", "✓"
        elif i == current:
            bg, fg, mark = "#6A3AB2", "#fff", str(i)
        else:
            bg, fg, mark = "#e9ecef", "#888", str(i)
        html += (f'<div style="flex:1;background:{bg};color:{fg};padding:8px 10px;'
                 f'border-radius:6px;text-align:center;font-size:12px;font-weight:600;">'
                 f'{mark}&nbsp;{s}</div>')
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 6. 侧边栏
# ==========================================
with st.sidebar:
    st.image("https://static.igem.wiki/teams/6263/wiki/layout/1-1-1.avif", width=100)
    st.header("🎭 Demo Control")

    playing = st.session_state.get('demo_playing', False)
    c_play, c_stop = st.columns(2)
    with c_play:
        if st.button("▶ Auto-Play", type="primary", use_container_width=True, disabled=playing):
            st.session_state['demo_playing'] = True
            st.session_state['demo_frame_idx'] = 0
            f0 = DEMO_FRAMES[0]
            for k, v in [('m_lac_420', f0['lac_420']), ('m_lac_485', f0['lac_485']),
                         ('m_pyr_420', f0['pyr_420']), ('m_pyr_485', f0['pyr_485'])]:
                st.session_state[f'_pending_{k}'] = v
            st.session_state['demo_current_label'] = f0['label']
            st.rerun()
    with c_stop:
        if st.button("⏹ Stop", use_container_width=True, disabled=not playing):
            st.session_state['demo_playing'] = False
            st.session_state['demo_frame_idx'] = 0
            st.rerun()

    if playing:
        idx = st.session_state.get('demo_frame_idx', 0)
        label = st.session_state.get('demo_current_label', '')
        st.info(f"🎬 Frame **{idx + 1}** / **{len(DEMO_FRAMES)}**\n\n{label}")
    else:
        st.caption("Auto-play cycles through 6 diagnostic states. "
                   "Or drag the sliders in **Hardware Scan** to explore interactively.")

    st.divider()
    st.markdown("### ⚡ Quick Presets")
    st.caption("Click to jump to a diagnostic state instantly.")
    for label, l420, l485, p420, p485 in PRESETS:
        if st.button(label, use_container_width=True, disabled=playing):
            for k, v in [('m_lac_420', l420), ('m_lac_485', l485),
                         ('m_pyr_420', p420), ('m_pyr_485', p485)]:
                st.session_state[f'_pending_{k}'] = v
            st.rerun()

    st.divider()
    st.markdown("### 🩺 Clinical Thresholds")
    lac_center = st.number_input("Lactate threshold (mM)", value=5.0, step=0.1, format="%.1f")
    pyr_center = st.number_input("Pyruvate threshold (μM)", value=200.0, step=10.0, format="%.0f")
    st.session_state['thresholds'] = {
        'lac_center': lac_center, 'lac_lo': lac_center * 0.9, 'lac_hi': lac_center * 1.1,
        'pyr_center': pyr_center, 'pyr_lo': pyr_center * 0.9, 'pyr_hi': pyr_center * 1.1,
    }
    st.caption(f"Borderline: Lactate {lac_center*0.9:.2f}–{lac_center*1.1:.2f} mM · "
               f"Pyruvate {pyr_center*0.9:.0f}–{pyr_center*1.1:.0f} μM")

    st.divider()
    st.markdown("### 📅 Calibration Status")
    for probe in ["Lactate", "Pyruvate"]:
        row = get_last_calibration(probe)
        if row:
            ts, _, _, r2 = row
            days = (datetime.now() - datetime.fromisoformat(ts)).days
            if days > 30:
                st.warning(f"{probe}: {days}d ago (EXPIRED)")
            else:
                st.success(f"{probe}: R²={r2:.4f}, {days}d ago")
        else:
            st.info(f"{probe}: not calibrated")

    st.divider()
    st.markdown("### 📋 Workflow Progress")
    _cal_ok = bool(st.session_state.get('lac_slope') and st.session_state.get('pyr_slope'))
    _synced = st.session_state.get('his_last_sync')
    _steps = [
        ("1. Calibration",  "✓ Ready" if _cal_ok else "⏳ Required", _cal_ok),
        ("2. Sample Input", "✓ Active", True),
        ("3. Lactate Scan", "✓ Live",   True),
        ("4. Pyruvate Scan", "✓ Live",  True),
        ("5. Diagnosis",    "✓ Live",   True),
        ("6. HIS/LIS Sync", f"✓ {_synced['ts']}" if _synced else "⏳ Pending", bool(_synced)),
    ]
    for name, status, done in _steps:
        st.markdown(f"{'🟢' if done else '⚪'} **{name}** · {status}")

    st.divider()
    st.caption("⚕️ Research / pre-screening use only. Results require clinical correlation.")

# ==========================================
# 7. 主区 Tabs
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 1. Calibration", "🔬 2. Hardware Scan", "📋 3. Diagnosis"])

# ---------- Tab 1: 校准 ----------
with tab1:
    st.markdown(
        '<div class="maintenance-box">⚠️ MAINTENANCE REQUIRED: Standard curves must be '
        'updated every 1 month or with new reagent batches.</div>',
        unsafe_allow_html=True)

    def parse_list(s):
        try:
            return [float(x.strip()) for x in s.split(',') if x.strip()], None
        except ValueError:
            return None, "Invalid numbers. Use English comma-separated values."

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Lactate Probe")
        lac_x = st.text_input("Lactate Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        lac_y420 = st.text_input("Lactate ADC_420 (Ref)", value="100, 102, 98, 105, 101")
        lac_y485 = st.text_input("Lactate ADC_485 (Signal)", value="120, 210, 320, 620, 1150")
        if st.button("Run Lactate Calibration", type="primary"):
            xs, e1 = parse_list(lac_x)
            ys420, e2 = parse_list(lac_y420)
            ys485, e3 = parse_list(lac_y485)
            if e1 or e2 or e3:
                st.error(e1 or e2 or e3)
            elif not (len(xs) == len(ys420) == len(ys485)):
                st.error("Arrays must have equal length.")
            else:
                ratios = [ys485[i] / ys420[i] for i in range(len(xs))]
                res = linregress(xs, ratios)
                r2 = res.rvalue ** 2
                st.session_state['lac_slope'] = res.slope
                st.session_state['lac_int'] = res.intercept
                st.session_state['lac_r2'] = r2
                save_calibration("Lactate", res.slope, res.intercept, r2)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=ratios, mode='markers', name='Standards',
                                         marker=dict(color='#0068c9', size=12)))
                fig.add_trace(go.Scatter(x=xs, y=res.intercept + res.slope * np.array(xs),
                                         mode='lines', name='Fit',
                                         line=dict(color='#333', width=3, dash='dash')))
                fig.update_layout(title="Lactate Calibration", xaxis_title="Conc (mM)",
                                  yaxis_title="Ratio (485/420)", height=300,
                                  margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
                msg = f"Ratio = {res.slope:.3f}·C + {res.intercept:.3f} | R² = {r2:.4f}"
                st.success(msg) if r2 >= 0.99 else st.warning(msg) if r2 >= 0.95 else st.error(msg)

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_y420 = st.text_input("Pyruvate ADC_420 (Ref)", value="100, 98, 102, 100, 99")
        pyr_y485 = st.text_input("Pyruvate ADC_485 (Signal)", value="120, 180, 250, 550, 1050")
        if st.button("Run Pyruvate Calibration", type="primary"):
            xs, e1 = parse_list(pyr_x)
            ys420, e2 = parse_list(pyr_y420)
            ys485, e3 = parse_list(pyr_y485)
            if e1 or e2 or e3:
                st.error(e1 or e2 or e3)
            elif not (len(xs) == len(ys420) == len(ys485)):
                st.error("Arrays must have equal length.")
            else:
                ratios = [ys485[i] / ys420[i] for i in range(len(xs))]
                res = linregress(xs, ratios)
                r2 = res.rvalue ** 2
                st.session_state['pyr_slope'] = res.slope
                st.session_state['pyr_int'] = res.intercept
                st.session_state['pyr_r2'] = r2
                save_calibration("Pyruvate", res.slope, res.intercept, r2)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=ratios, mode='markers', name='Standards',
                                         marker=dict(color='#ff4b4b', size=12)))
                fig.add_trace(go.Scatter(x=xs, y=res.intercept + res.slope * np.array(xs),
                                         mode='lines', name='Fit',
                                         line=dict(color='#333', width=3, dash='dash')))
                fig.update_layout(title="Pyruvate Calibration", xaxis_title="Conc (μM)",
                                  yaxis_title="Ratio (485/420)", height=300,
                                  margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
                msg = f"Ratio = {res.slope:.4f}·C + {res.intercept:.3f} | R² = {r2:.4f}"
                st.success(msg) if r2 >= 0.99 else st.warning(msg) if r2 >= 0.95 else st.error(msg)

# ---------- Tab 2: 硬件扫描（实时可操作）----------
with tab2:
    fig17_steps(1)

    if 'saved_lac' not in st.session_state:
        st.session_state['saved_lac'] = {}
    if 'saved_pyr' not in st.session_state:
        st.session_state['saved_pyr'] = {}

    lac_slope = st.session_state.get('lac_slope', 0.1)
    lac_int = st.session_state.get('lac_int', 1.0)
    pyr_slope = st.session_state.get('pyr_slope', 0.001)
    pyr_int = st.session_state.get('pyr_int', 1.0)
    th = st.session_state['thresholds']

    # 播放状态横幅
    if playing:
        label = st.session_state.get('demo_current_label', '')
        st.markdown(f"""
        <div class="live-banner">
            <span><span class="live-dot"></span>DEMO PLAYING</span>
            <span>{label}</span>
        </div>
        """, unsafe_allow_html=True)

    # Step 1
    st.markdown("### 📝 Step 1 · Sample Input")
    sid = st.text_input("Sample ID / Barcode",
                        value=st.session_state.get('demo_sid', 'DEMO-01'),
                        key='demo_sid_input')

    # Step 2 & 3
    st.markdown("### ⚙️ Step 2 & 3 · Probe Mode → Live Scan → Calibration")
    st.caption("🎭 Drag the sliders to change ADC in real time. Concentration and diagnosis update instantly. "
               "Or use **Auto-Play** in the sidebar.")

    col_l, col_p = st.columns(2)

    with col_l:
        st.markdown("#### 🧪 Lactate Probe")
        lac_420 = st.slider("Lactate ADC_420 (Ref)", 50.0, 200.0, step=1.0,
                            key='m_lac_420', disabled=playing)
        lac_485 = st.slider("Lactate ADC_485 (Signal)", 0.0, 1500.0, step=1.0,
                            key='m_lac_485', disabled=playing)
        lac_ratio = lac_485 / lac_420
        lac_conc = max(0.0, (lac_ratio - lac_int) / lac_slope) if lac_slope else 0.0

        c_m, c_s = st.columns(2)
        with c_m:
            st.metric("Ratio", f"{lac_ratio:.3f}")
        with c_s:
            st.metric("Concentration", f"{lac_conc:.2f} mM")

        if lac_conc > th['lac_hi']:
            st.error(f"🔴 Above threshold (> {th['lac_hi']:.2f} mM)")
        elif lac_conc >= th['lac_lo']:
            st.warning(f"🟡 Borderline ({th['lac_lo']:.2f}–{th['lac_hi']:.2f} mM)")
        else:
            st.success(f"🟢 Within reference (< {th['lac_hi']:.2f} mM)")

    with col_p:
        st.markdown("#### 🧪 Pyruvate Probe")
        pyr_420 = st.slider("Pyruvate ADC_420 (Ref)", 50.0, 200.0, step=1.0,
                            key='m_pyr_420', disabled=playing)
        pyr_485 = st.slider("Pyruvate ADC_485 (Signal)", 0.0, 1500.0, step=1.0,
                            key='m_pyr_485', disabled=playing)
        pyr_ratio = pyr_485 / pyr_420
        pyr_conc = max(0.0, (pyr_ratio - pyr_int) / pyr_slope) if pyr_slope else 0.0

        c_m, c_s = st.columns(2)
        with c_m:
            st.metric("Ratio", f"{pyr_ratio:.3f}")
        with c_s:
            st.metric("Concentration", f"{pyr_conc:.1f} μM")

        if pyr_conc > th['pyr_hi']:
            st.error(f"🔴 Above threshold (> {th['pyr_hi']:.0f} μM)")
        elif pyr_conc >= th['pyr_lo']:
            st.warning(f"🟡 Borderline ({th['pyr_lo']:.0f}–{th['pyr_hi']:.0f} μM)")
        else:
            st.success(f"🟢 Within reference (< {th['pyr_hi']:.0f} μM)")

    # 写入 saved（实时联动 Tab 3）
    st.session_state['saved_lac'][sid] = {'conc': round(lac_conc, 2), 'flag': 'OK'}
    st.session_state['saved_pyr'][sid] = {'conc': round(pyr_conc, 2), 'flag': 'OK'}
    st.session_state['demo_sid'] = sid

    # 实时诊断横幅
    st.divider()
    preview = classify(lac_conc, pyr_conc, th)
    st.markdown(f"""
    <div style="padding:16px 20px; border-radius:10px; background:#fff;
                border-left:8px solid {'#dc3545' if preview['status']=='High Cancer Risk' else '#D97706' if preview['status']=='High Lactate' else '#6f42c1' if preview['status']=='High Pyruvate' else '#6c757d' if preview['status']=='Borderline' else '#28a745'};
                box-shadow:0 4px 15px rgba(0,0,0,0.05); margin-bottom:16px;">
        <div style="font-size:13px;color:#888;margin-bottom:4px;">LIVE DIAGNOSIS</div>
        <div style="font-size:24px;font-weight:800;color:#262730;margin-bottom:6px;">{preview['status']}</div>
        <div style="font-size:13px;color:#666;">{preview['sub']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Step 4
    st.markdown("### ✓ Step 4 · Both Scans Completed?")
    existing = sorted(set(st.session_state['saved_lac'].keys()) & set(st.session_state['saved_pyr'].keys()))
    st.success(f"✅ **{len(existing)} sample(s)** ready for joint diagnosis: "
               f"`{', '.join(existing[:6])}{'...' if len(existing) > 6 else ''}`")
    st.info("→ Proceed to **Diagnosis** tab to view reports and export.")

# ---------- Tab 3: 诊断摘要 ----------
with tab3:
    fig17_steps(4)
    st.header("Diagnosis Report")

    st.markdown("""
    <div style="background:#e7f1ff;border-left:6px solid #0068c9;padding:14px 18px;
                border-radius:8px;margin-bottom:20px;font-size:14px;color:#084298;line-height:1.6;">
        <b>⚕️ Clinical Correlation Required</b><br>
        This assay measures <b>lactate and pyruvate only</b>. Results must be interpreted
        together with the patient's clinical presentation, medical history, and other
        laboratory findings. They are <b>not</b> a stand-alone diagnosis.
    </div>
    """, unsafe_allow_html=True)

    th = st.session_state.get('thresholds', {
        'lac_lo': 4.5, 'lac_hi': 5.5, 'pyr_lo': 180, 'pyr_hi': 220,
    })
    saved_lac = st.session_state.get('saved_lac', {})
    saved_pyr = st.session_state.get('saved_pyr', {})

    if not saved_lac or not saved_pyr:
        st.info("Please scan and save both Lactate and Pyruvate results first.")
    else:
        common_ids = sorted(set(saved_lac.keys()) & set(saved_pyr.keys()))
        if not common_ids:
            st.warning("No matching Sample IDs found.")
        else:
            joint = []
            for sid in common_ids:
                c_lac = saved_lac[sid]['conc']
                c_pyr = saved_pyr[sid]['conc']
                cls = classify(c_lac, c_pyr, th)
                joint.append({'sid': sid, 'c_lac': c_lac, 'c_pyr': c_pyr, 'cls': cls})

            st.markdown("### 🩺 Patient Summary Cards")
            cols = st.columns(3)
            for idx, j in enumerate(joint):
                with cols[idx % 3]:
                    c = j['cls']
                    lac_style = ('color:#D97706;font-weight:700;'
                                 if c['lac_flag'] == 'high'
                                 else ('color:#6c757d;font-style:italic;'
                                       if c['lac_flag'] == 'border' else ''))
                    pyr_style = ('color:#6f42c1;font-weight:700;'
                                 if c['pyr_flag'] == 'high'
                                 else ('color:#6c757d;font-style:italic;'
                                       if c['pyr_flag'] == 'border' else ''))
                    lac_text = f"{j['c_lac']:.2f} mM" if j['c_lac'] is not None else "—"
                    pyr_text = f"{j['c_pyr']:.1f} μM" if j['c_pyr'] is not None else "—"
                    st.markdown(f"""
                    <div class="diagnosis-card {c['border_cls']}">
                        <div class="card-title">{j['sid']}</div>
                        <div class="card-data">Lactate: <span style="{lac_style}"><b>{lac_text}</b></span></div>
                        <div class="card-data">Pyruvate: <span style="{pyr_style}"><b>{pyr_text}</b></span></div>
                        <div class="card-badge {c['badge_cls']}">{c['status']}</div>
                        <div class="card-sub">{c['sub']}</div>
                        <div class="card-note">Requires clinical correlation</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()
            st.markdown("### 📄 Export & Reports")
            df_out = pd.DataFrame([{
                'Sample ID': j['sid'],
                'Lactate (mM)': j['c_lac'],
                'Pyruvate (μM)': j['c_pyr'],
                'Status': j['cls']['status'],
                'Clinical Note': 'Requires clinical correlation; not a stand-alone diagnosis',
            } for j in joint])
            st.download_button(
                "📥 Download All Results (CSV)",
                data=df_out.to_csv(index=False).encode('utf-8'),
                file_name='PyrLac_Glow_Batch_Results.csv',
                mime='text/csv', type="primary")

            for j in joint:
                c = j['cls']
                with st.expander(f"📄 Report for {j['sid']} — {c['status']}"):
                    risk_color = {
                        'High Cancer Risk': '#dc3545', 'High Lactate': '#D97706',
                        'High Pyruvate': '#6f42c1', 'Borderline': '#6c757d',
                        'Invalid': '#adb5bd',
                    }.get(c['status'], '#2C6E4A')
                    lac_val = f"{j['c_lac']:.2f} mM"
                    pyr_val = f"{j['c_pyr']:.1f} μM"
                    report_html = f"""
                    <div style="border: 2px solid #333; padding: 30px; border-radius: 8px;
                                font-family: Arial, sans-serif; max-width: 650px;
                                margin: auto; background-color: #fff;">
                        <h2 style="text-align:center;border-bottom:2px solid #333;
                                   padding-bottom:10px;margin-top:0;">PyrLac Glow Diagnostic Report</h2>
                        <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
                            <div><b>Sample ID:</b> {j['sid']}</div>
                            <div><b>Date:</b> {time.strftime('%Y-%m-%d')}</div>
                        </div>
                        <table style="width:100%;border-collapse:collapse;margin-top:10px;">
                            <tr style="background:#f2f2f2;">
                                <th style="border:1px solid #ddd;padding:10px;text-align:left;">Biomarker</th>
                                <th style="border:1px solid #ddd;padding:10px;text-align:center;">Result</th>
                                <th style="border:1px solid #ddd;padding:10px;text-align:center;">Reference</th>
                            </tr>
                            <tr>
                                <td style="border:1px solid #ddd;padding:10px;">Lactate</td>
                                <td style="border:1px solid #ddd;padding:10px;text-align:center;font-weight:bold;color:{risk_color};">{lac_val}</td>
                                <td style="border:1px solid #ddd;padding:10px;text-align:center;">&lt; {th['lac_hi']:.1f} mM</td>
                            </tr>
                            <tr>
                                <td style="border:1px solid #ddd;padding:10px;">Pyruvate</td>
                                <td style="border:1px solid #ddd;padding:10px;text-align:center;font-weight:bold;color:{risk_color};">{pyr_val}</td>
                                <td style="border:1px solid #ddd;padding:10px;text-align:center;">&lt; {th['pyr_hi']:.0f} μM</td>
                            </tr>
                        </table>
                        <div style="background:#fff8e1;border:1px solid #ffc107;border-radius:6px;
                                    padding:12px 16px;margin-top:18px;font-size:13px;color:#856404;line-height:1.5;">
                            <b>⚠️ Clinical Correlation Required</b><br>
                            Values above are raw assay measurements. Interpretation requires
                            correlation with clinical symptoms, physical examination, and
                            additional laboratory tests.
                        </div>
                        <h3 style="margin-top:25px;color:{risk_color};border-bottom:1px solid #eee;
                                   padding-bottom:5px;">Finding</h3>
                        <p style="font-size:14px;line-height:1.5;"><b>{c['status']}</b> — {c['sub']}</p>
                        <h3 style="color:{risk_color};border-bottom:1px solid #eee;padding-bottom:5px;">
                            Interpretation &amp; Recommendation</h3>
                        <p style="font-size:14px;line-height:1.5;">{c['rec']}</p>
                        <div style="margin-top:40px;display:flex;justify-content:space-between;
                                    font-size:12px;color:#555;">
                            <div>检测人: __________</div>
                            <div>审核人: __________</div>
                            <div>日期: __________</div>
                        </div>
                        <p style="margin-top:20px;font-size:11px;color:#777;text-align:center;
                                  border-top:1px solid #eee;padding-top:10px;">
                            For research and pre-screening use only. Not a definitive clinical diagnosis.
                        </p>
                    </div>
                    """
                    st.markdown(report_html, unsafe_allow_html=True)
                    st.download_button(
                        f"📥 Download Report for {j['sid']} (HTML)",
                        data=report_html.encode('utf-8'),
                        file_name=f"PyrLac_Report_{j['sid']}.html",
                        mime="text/html", key=f"dl_{j['sid']}")

            st.divider()
            st.markdown("### 📤 End · Sync to HIS/LIS")
            batch_id = st.text_input("Batch ID",
                                     value=st.session_state.get('batch_id',
                                                                'B' + datetime.now().strftime('%Y%m%d-%H%M')),
                                     key='his_batch_id')
            c_sync, c_clear = st.columns(2)
            with c_sync:
                if st.button("📤 Sync All Records to HIS/LIS", type="primary",
                             use_container_width=True):
                    log_his_sync(batch_id, len(joint))
                    st.session_state['his_last_sync'] = {
                        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'count': len(joint), 'batch': batch_id,
                    }
                    st.success(f"✅ {len(joint)} record(s) synced to HIS/LIS "
                               f"(batch `{batch_id}`)")
            with c_clear:
                if st.button("🗑 Clear All Data", use_container_width=True):
                    st.session_state['saved_lac'] = {}
                    st.session_state['saved_pyr'] = {}
                    st.session_state.pop('his_last_sync', None)
                    st.rerun()

            if 'his_last_sync' in st.session_state:
                s = st.session_state['his_last_sync']
                st.info(f"Last sync · **{s['ts']}** · batch `{s['batch']}` · "
                        f"**{s['count']}** record(s)")

# ==========================================
# 8. Auto-Play 推进器（脚本末尾）
# ==========================================
if st.session_state.get('demo_playing'):
    idx = st.session_state.get('demo_frame_idx', 0)
    if idx + 1 < len(DEMO_FRAMES):
        next_f = DEMO_FRAMES[idx + 1]
        for k, v in [('m_lac_420', next_f['lac_420']), ('m_lac_485', next_f['lac_485']),
                     ('m_pyr_420', next_f['pyr_420']), ('m_pyr_485', next_f['pyr_485'])]:
            st.session_state[f'_pending_{k}'] = v
        st.session_state['demo_frame_idx'] = idx + 1
        st.session_state['demo_current_label'] = next_f['label']
        time.sleep(1.2)
        st.rerun()
    else:
        st.session_state['demo_playing'] = False
        st.session_state['demo_frame_idx'] = 0
