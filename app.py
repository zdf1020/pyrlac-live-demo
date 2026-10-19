import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import sqlite3
from datetime import datetime

__version__ = "1.0.0"

st.set_page_config(
    page_title="PyrLac Glow",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .formula-banner {
        background: linear-gradient(90deg, #433262 0%, #6A3AB2 100%);
        color: white; padding: 14px; border-radius: 10px;
        text-align: center; font-size: 18px; font-weight: 600;
        margin-bottom: 20px;
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
    .border-normal { border-left-color: #28a745; }
    .border-lac { border-left-color: #D97706; }
    .border-pdhc { border-left-color: #6f42c1; }
    .border-cancer { border-left-color: #dc3545; }
    .border-borderline { border-left-color: #6c757d; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SQLite
# ==========================================
@st.cache_resource
def get_db():
    conn = sqlite3.connect('pyrlac_demo.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS calibration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, probe TEXT, slope REAL, intercept REAL, r2 REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, batch_id TEXT, sample_id TEXT, operator TEXT,
        lac_mM REAL, pyr_uM REAL, status TEXT)''')
    conn.commit()
    return conn

db = get_db()

# ==========================================
# 全局 state
# ==========================================
def init_state():
    defaults = {
        'operator': 'demo_user',
        'batch_id': 'B' + datetime.now().strftime('%Y%m%d-%H%M'),
        'lac_slope': None, 'lac_int': None, 'lac_r2': None, 'lac_cal_ts': None,
        'pyr_slope': None, 'pyr_int': None, 'pyr_r2': None, 'pyr_cal_ts': None,
        'lac_center': 5.0, 'pyr_center': 200.0, 'border_pct': 0.10,
        'current_measurement': None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_state()


def thresholds():
    lc = st.session_state['lac_center']
    pc = st.session_state['pyr_center']
    bp = st.session_state['border_pct']
    return {
        'lac_center': lc, 'pyr_center': pc, 'border_pct': bp,
        'lac_lo': lc * (1 - bp), 'lac_hi': lc * (1 + bp),
        'pyr_lo': pc * (1 - bp), 'pyr_hi': pc * (1 + bp),
    }


def cal_valid():
    for p in ['lac', 'pyr']:
        ts = st.session_state.get(f'{p}_cal_ts')
        if not ts or not st.session_state.get(f'{p}_slope'):
            return False
        if (datetime.now() - datetime.fromisoformat(ts)).days > 30:
            return False
    return True


def classify(c_lac, c_pyr):
    th = thresholds()
    lac_border = th['lac_lo'] <= c_lac <= th['lac_hi']
    pyr_border = th['pyr_lo'] <= c_pyr <= th['pyr_hi']

    if lac_border or pyr_border:
        parts = []
        if lac_border: parts.append("Lactate near threshold")
        if pyr_border: parts.append("Pyruvate near threshold")
        return {
            'status': "Borderline",
            'sub': " · ".join(parts) + " — retest recommended",
            'badge_cls': 'bg-borderline', 'border_cls': 'border-borderline',
            'lac_flag': 'border' if lac_border else 'normal',
            'pyr_flag': 'border' if pyr_border else 'normal',
            'rec': "One or both markers fall within the borderline zone. "
                   "Retest is recommended before clinical interpretation.",
        }

    lac_high = c_lac > th['lac_hi']
    pyr_high = c_pyr > th['pyr_hi']

    if lac_high and pyr_high:
        return {
            'status': "High Cancer Risk",
            'sub': "Dual elevation — metabolic reprogramming / Warburg effect",
            'badge_cls': 'bg-cancer', 'border_cls': 'border-cancer',
            'lac_flag': 'high', 'pyr_flag': 'high',
            'rec': "Both lactate and pyruvate are markedly elevated. This pattern is "
                   "consistent with enhanced aerobic glycolysis (Warburg effect) and has "
                   "been associated with malignancy and poor prognosis. However, severe "
                   "sepsis or other critical illness can also produce dual elevation. "
                   "Prompt clinical evaluation is strongly advised.",
        }
    if lac_high:
        return {
            'status': "High Lactate",
            'sub': "Possible: shock, sepsis, liver failure, metformin, malignancy",
            'badge_cls': 'bg-lac', 'border_cls': 'border-lac',
            'lac_flag': 'high', 'pyr_flag': 'normal',
            'rec': "Isolated lactate elevation is non-specific. Consider: (A) tissue "
                   "hypoperfusion — shock, heart failure, severe anemia, ischemia; "
                   "(B) non-hypoxic metabolic causes — sepsis, liver failure, diabetic "
                   "ketoacidosis, seizures; (C) drugs/toxins — metformin, linezolid, "
                   "propofol, cyanide, alcohol; (D) malignancy (Warburg effect); "
                   "(E) inherited mitochondrial disorders. Clinical correlation and "
                   "repeat testing are required.",
        }
    if pyr_high:
        return {
            'status': "High Pyruvate",
            'sub': "Possible: PDHC deficiency, vitamin B1 deficiency, pyruvate carboxylase deficiency",
            'badge_cls': 'bg-pdhc', 'border_cls': 'border-pdhc',
            'lac_flag': 'normal', 'pyr_flag': 'high',
            'rec': "Isolated pyruvate elevation suggests impaired pyruvate utilization. "
                   "Primary considerations include: (1) pyruvate dehydrogenase complex "
                   "(PDHC) deficiency — confirmed by enzyme assay or DNA testing; "
                   "(2) vitamin B1 (thiamine) deficiency — a reversible cause, especially "
                   "in malnutrition or alcohol dependence; (3) pyruvate carboxylase "
                   "deficiency and other inherited pyruvate oxidation disorders. "
                   "Recommend PDHC functional assessment and thiamine screening.",
        }
    return {
        'status': "Normal", 'sub': "No obvious metabolic abnormality",
        'badge_cls': 'bg-normal', 'border_cls': 'border-normal',
        'lac_flag': 'normal', 'pyr_flag': 'normal',
        'rec': "No significant metabolic risk detected. Continue routine checkups.",
    }


def status_bar():
    cal_ok = cal_valid()
    op = st.session_state.get('operator') or '—'
    bid = st.session_state.get('batch_id') or '—'
    st.markdown(f"""
    <div style="display:flex;gap:24px;background:#1f2430;color:#c9d1d9;
                padding:10px 16px;border-radius:8px;font-size:13px;margin-bottom:16px;">
        <span>👤 {op}</span>
        <span>{'🟢' if cal_ok else '🟠'} Calibration {'valid' if cal_ok else 'required'}</span>
        <span>📦 Batch {bid}</span>
        <span style="margin-left:auto;">v{__version__}</span>
    </div>
    """, unsafe_allow_html=True)


def step_header(current: int):
    steps = ["Calibration", "Measurement", "Review"]
    html = '<div style="display:flex;gap:8px;margin-bottom:24px;">'
    for i, s in enumerate(steps, 1):
        if i < current:
            bg, fg, mark = "#28a745", "#fff", "✓"
        elif i == current:
            bg, fg, mark = "#6A3AB2", "#fff", str(i)
        else:
            bg, fg, mark = "#e9ecef", "#888", str(i)
        html += (f'<div style="flex:1;background:{bg};color:{fg};padding:10px 14px;'
                 f'border-radius:8px;font-weight:600;font-size:14px;">'
                 f'{mark}&nbsp;&nbsp;{s}</div>')
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 页面函数
# ==========================================
def page_calibration():
    status_bar()
    step_header(1)
    st.title("📈 Calibration")
    st.caption("Enter standard concentrations and ADC readings. Ratio = ADC_485 / ADC_420.")
    st.markdown('<div class="formula-banner">Ratio = ADC (485 nm) / ADC (420 nm)</div>',
                unsafe_allow_html=True)

    def parse_list(s):
        try:
            return [float(x.strip()) for x in s.split(',') if x.strip()], None
        except ValueError:
            return None, "Invalid numbers. Use English comma-separated values."

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Lactate Probe")
        lac_x = st.text_input("Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        lac_420 = st.text_input("ADC_420", value="100, 102, 98, 105, 101")
        lac_485 = st.text_input("ADC_485", value="120, 210, 320, 620, 1150")

        if st.button("Fit & Save Lactate", type="primary", use_container_width=True):
            xs, e1 = parse_list(lac_x)
            y420, e2 = parse_list(lac_420)
            y485, e3 = parse_list(lac_485)
            if e1 or e2 or e3:
                st.error(e1 or e2 or e3)
            elif not (len(xs) == len(y420) == len(y485)):
                st.error("Arrays must have equal length.")
            else:
                ratios = [y485[i] / y420[i] for i in range(len(xs))]
                res = linregress(xs, ratios)
                r2 = res.rvalue ** 2
                st.session_state['lac_slope'] = res.slope
                st.session_state['lac_int'] = res.intercept
                st.session_state['lac_r2'] = r2
                st.session_state['lac_cal_ts'] = datetime.now().isoformat()
                db.execute(
                    "INSERT INTO calibration (ts, probe, slope, intercept, r2) VALUES (?,?,?,?,?)",
                    (datetime.now().isoformat(), "Lactate", res.slope, res.intercept, r2))
                db.commit()

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=ratios, mode='markers', name='Standards',
                                         marker=dict(color='#0068c9', size=12)))
                fig.add_trace(go.Scatter(x=xs, y=res.intercept + res.slope * np.array(xs),
                                         mode='lines', name='Fit',
                                         line=dict(color='#333', width=3, dash='dash')))
                fig.update_layout(title="Lactate Calibration", xaxis_title="Conc (mM)",
                                  yaxis_title="Ratio (485/420)", height=320,
                                  margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

                msg = f"Ratio = {res.slope:.4f}·C + {res.intercept:.4f} | R² = {r2:.4f}"
                if r2 < 0.95:
                    st.error(msg + " — Low fit quality, recalibration required.")
                elif r2 < 0.99:
                    st.warning(msg)
                else:
                    st.success(msg)

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_420 = st.text_input("ADC_420", value="100, 98, 102, 100, 99")
        pyr_485 = st.text_input("ADC_485", value="120, 180, 250, 550, 1050")

        if st.button("Fit & Save Pyruvate", type="primary", use_container_width=True):
            xs, e1 = parse_list(pyr_x)
            y420, e2 = parse_list(pyr_420)
            y485, e3 = parse_list(pyr_485)
            if e1 or e2 or e3:
                st.error(e1 or e2 or e3)
            elif not (len(xs) == len(y420) == len(y485)):
                st.error("Arrays must have equal length.")
            else:
                ratios = [y485[i] / y420[i] for i in range(len(xs))]
                res = linregress(xs, ratios)
                r2 = res.rvalue ** 2
                st.session_state['pyr_slope'] = res.slope
                st.session_state['pyr_int'] = res.intercept
                st.session_state['pyr_r2'] = r2
                st.session_state['pyr_cal_ts'] = datetime.now().isoformat()
                db.execute(
                    "INSERT INTO calibration (ts, probe, slope, intercept, r2) VALUES (?,?,?,?,?)",
                    (datetime.now().isoformat(), "Pyruvate", res.slope, res.intercept, r2))
                db.commit()

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xs, y=ratios, mode='markers', name='Standards',
                                         marker=dict(color='#ff4b4b', size=12)))
                fig.add_trace(go.Scatter(x=xs, y=res.intercept + res.slope * np.array(xs),
                                         mode='lines', name='Fit',
                                         line=dict(color='#333', width=3, dash='dash')))
                fig.update_layout(title="Pyruvate Calibration", xaxis_title="Conc (μM)",
                                  yaxis_title="Ratio (485/420)", height=320,
                                  margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

                msg = f"Ratio = {res.slope:.6f}·C + {res.intercept:.4f} | R² = {r2:.4f}"
                if r2 < 0.95:
                    st.error(msg + " — Low fit quality, recalibration required.")
                elif r2 < 0.99:
                    st.warning(msg)
                else:
                    st.success(msg)


def page_measurement():
    status_bar()
    step_header(2)
    st.title("🔬 Measurement")

    if not cal_valid():
        st.warning("⚠ Calibration required before measurement.")
        if st.button("→ Go to Calibration", type="primary"):
            st.session_state['nav'] = "📈 Calibration"
            st.rerun()
        return

    st.caption("Demo sample — adjust ADC values below. Concentration and diagnosis update automatically.")

    lac_slope = st.session_state['lac_slope']
    lac_int = st.session_state['lac_int']
    pyr_slope = st.session_state['pyr_slope']
    pyr_int = st.session_state['pyr_int']
    th = thresholds()

    sid = st.text_input("Sample ID", value="DEMO-01")

    col_l, col_p = st.columns(2)

    with col_l:
        st.markdown("#### 🧪 Lactate Probe")
        lac_420 = st.number_input("Lactate ADC_420 (Ref)", value=100.0, step=1.0,
                                  min_value=1.0, format="%.1f", key='m_lac_420')
        lac_485 = st.number_input("Lactate ADC_485 (Signal)", value=140.0, step=1.0,
                                  min_value=0.0, format="%.1f", key='m_lac_485')
        lac_ratio = lac_485 / lac_420
        lac_conc = max(0.0, (lac_ratio - lac_int) / lac_slope) if lac_slope else 0.0
        st.metric("Concentration", f"{lac_conc:.2f} mM")
        if lac_conc > th['lac_hi']:
            st.caption(f"🔴 Ratio {lac_ratio:.3f} · above threshold (> {th['lac_hi']:.2f} mM)")
        elif lac_conc >= th['lac_lo']:
            st.caption(f"🟡 Ratio {lac_ratio:.3f} · borderline ({th['lac_lo']:.2f}–{th['lac_hi']:.2f} mM)")
        else:
            st.caption(f"🟢 Ratio {lac_ratio:.3f} · normal")

    with col_p:
        st.markdown("#### 🧪 Pyruvate Probe")
        pyr_420 = st.number_input("Pyruvate ADC_420 (Ref)", value=100.0, step=1.0,
                                  min_value=1.0, format="%.1f", key='m_pyr_420')
        pyr_485 = st.number_input("Pyruvate ADC_485 (Signal)", value=110.0, step=1.0,
                                  min_value=0.0, format="%.1f", key='m_pyr_485')
        pyr_ratio = pyr_485 / pyr_420
        pyr_conc = max(0.0, (pyr_ratio - pyr_int) / pyr_slope) if pyr_slope else 0.0
        st.metric("Concentration", f"{pyr_conc:.1f} μM")
        if pyr_conc > th['pyr_hi']:
            st.caption(f"🔴 Ratio {pyr_ratio:.3f} · above threshold (> {th['pyr_hi']:.0f} μM)")
        elif pyr_conc >= th['pyr_lo']:
            st.caption(f"🟡 Ratio {pyr_ratio:.3f} · borderline ({th['pyr_lo']:.0f}–{th['pyr_hi']:.0f} μM)")
        else:
            st.caption(f"🟢 Ratio {pyr_ratio:.3f} · normal")

    # 实时预览
    st.divider()
    preview = classify(lac_conc, pyr_conc)
    st.markdown(f"**Preview Diagnosis:** `{preview['status']}` — {preview['sub']}")

    # 保存到 session，供 Review 页使用
    st.session_state['current_measurement'] = {
        'sample_id': sid,
        'lac_conc': round(lac_conc, 2),
        'pyr_conc': round(pyr_conc, 2),
        'lac_ratio': round(lac_ratio, 3),
        'pyr_ratio': round(pyr_ratio, 3),
    }

    st.info("💡 Measurement is saved automatically. Go to **Review** to submit and generate reports.")


def page_review():
    status_bar()
    step_header(3)
    st.title("📋 Review & Report")

    m = st.session_state.get('current_measurement')
    if not m:
        st.warning("No measurement data. Please complete Measurement first.")
        if st.button("→ Go to Measurement", type="primary"):
            st.session_state['nav'] = "🔬 Measurement"
            st.rerun()
        return

    st.markdown("""
    <div style="background:#e7f1ff;border-left:6px solid #0068c9;padding:14px 18px;
                border-radius:8px;margin-bottom:20px;font-size:14px;color:#084298;line-height:1.6;">
        <b>⚕️ Clinical Correlation Required</b><br>
        This assay measures <b>lactate and pyruvate only</b>. Results must be interpreted
        together with the patient's clinical presentation, medical history, and other
        laboratory findings. They are <b>not</b> a stand-alone diagnosis.
    </div>
    """, unsafe_allow_html=True)

    cls = classify(m['lac_conc'], m['pyr_conc'])
    th = thresholds()

    lac_style = ('color:#D97706;font-weight:700;' if cls['lac_flag'] == 'high'
                 else 'color:#6c757d;font-style:italic;' if cls['lac_flag'] == 'border'
                 else '')
    pyr_style = ('color:#6f42c1;font-weight:700;' if cls['pyr_flag'] == 'high'
                 else 'color:#6c757d;font-style:italic;' if cls['pyr_flag'] == 'border'
                 else '')

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"""
        <div class="diagnosis-card {cls['border_cls']}">
            <div class="card-title">{m['sample_id']}</div>
            <div class="card-data">Lactate: <span style="{lac_style}"><b>{m['lac_conc']:.2f} mM</b></span></div>
            <div class="card-data">Pyruvate: <span style="{pyr_style}"><b>{m['pyr_conc']:.1f} μM</b></span></div>
            <div class="card-badge {cls['badge_cls']}">{cls['status']}</div>
            <div class="card-sub">{cls['sub']}</div>
            <div class="card-note">Requires clinical correlation</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("### 📝 Interpretation")
        st.write(f"**Finding:** {cls['status']} — {cls['sub']}")
        st.write("**Recommendation:** " + cls['rec'])

    st.divider()
    st.markdown("### 📤 Actions")
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("✅ Submit to Database", type="primary", use_container_width=True):
            db.execute(
                "INSERT INTO measurements (ts, batch_id, sample_id, operator, lac_mM, pyr_uM, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.now().isoformat(), st.session_state['batch_id'], m['sample_id'],
                 st.session_state['operator'], m['lac_conc'], m['pyr_conc'], cls['status']))
            db.commit()
            st.success(f"Submitted to batch `{st.session_state['batch_id']}`")

    with col_b:
        df_out = pd.DataFrame([{
            'Sample ID': m['sample_id'],
            'Lactate (mM)': m['lac_conc'],
            'Pyruvate (μM)': m['pyr_conc'],
            'Status': cls['status'],
            'Clinical Note': 'Requires clinical correlation; not a stand-alone diagnosis',
        }])
        csv = df_out.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv,
                           file_name=f"PyrLac_{m['sample_id']}.csv",
                           mime='text/csv', use_container_width=True)

    st.divider()
    st.markdown("### 📄 Diagnostic Report")

    risk_color = {
        'High Cancer Risk': '#dc3545',
        'High Lactate': '#D97706',
        'High Pyruvate': '#6f42c1',
        'Borderline': '#6c757d',
    }.get(cls['status'], '#2C6E4A')

    report_html = f"""
    <div style="border: 2px solid #333; padding: 30px; border-radius: 8px; font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; background: #fff;">
        <h2 style="text-align:center;border-bottom:2px solid #333;padding-bottom:10px;margin-top:0;">PyrLac Glow Diagnostic Report</h2>
        <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
            <div><b>Sample ID:</b> {m['sample_id']}</div>
            <div><b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
            <div><b>Batch:</b> {st.session_state['batch_id']}</div>
            <div><b>Operator:</b> {st.session_state['operator']}</div>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-top:10px;">
            <tr style="background:#f2f2f2;">
                <th style="border:1px solid #ddd;padding:10px;text-align:left;">Biomarker</th>
                <th style="border:1px solid #ddd;padding:10px;text-align:center;">Result</th>
                <th style="border:1px solid #ddd;padding:10px;text-align:center;">Reference</th>
            </tr>
            <tr>
                <td style="border:1px solid #ddd;padding:10px;">Lactate</td>
                <td style="border:1px solid #ddd;padding:10px;text-align:center;font-weight:bold;color:{risk_color};">{m['lac_conc']:.2f} mM</td>
                <td style="border:1px solid #ddd;padding:10px;text-align:center;">&lt; {th['lac_hi']:.1f} mM</td>
            </tr>
            <tr>
                <td style="border:1px solid #ddd;padding:10px;">Pyruvate</td>
                <td style="border:1px solid #ddd;padding:10px;text-align:center;font-weight:bold;color:{risk_color};">{m['pyr_conc']:.1f} μM</td>
                <td style="border:1px solid #ddd;padding:10px;text-align:center;">&lt; {th['pyr_hi']:.0f} μM</td>
            </tr>
        </table>
        <div style="background:#fff8e1;border:1px solid #ffc107;border-radius:6px;padding:12px 16px;margin-top:18px;font-size:13px;color:#856404;line-height:1.5;">
            <b>⚠️ Clinical Correlation Required</b><br>
            The values above are raw assay measurements. Interpretation requires correlation with clinical symptoms, physical examination, and additional laboratory tests.
        </div>
        <h3 style="margin-top:25px;color:{risk_color};border-bottom:1px solid #eee;padding-bottom:5px;">Finding</h3>
        <p style="font-size:14px;line-height:1.5;"><b>{cls['status']}</b> — {cls['sub']}</p>
        <h3 style="color:{risk_color};border-bottom:1px solid #eee;padding-bottom:5px;">Interpretation &amp; Recommendation</h3>
        <p style="font-size:14px;line-height:1.5;">{cls['rec']}</p>
        <div style="margin-top:40px;display:flex;justify-content:space-between;font-size:12px;color:#555;">
            <div>检测人: __________</div>
            <div>审核人: __________</div>
            <div>日期: __________</div>
        </div>
        <p style="margin-top:20px;font-size:11px;color:#777;text-align:center;border-top:1px solid #eee;padding-top:10px;">
            For research and pre-screening use only. This report does not constitute a definitive clinical diagnosis.
        </p>
    </div>
    """
    st.markdown(report_html, unsafe_allow_html=True)
    st.download_button("📥 Download Report (HTML)",
                       data=report_html.encode('utf-8'),
                       file_name=f"PyrLac_Report_{m['sample_id']}.html",
                       mime="text/html")


def page_history():
    status_bar()
    st.title("🗂️ History")
    st.caption("All measurements submitted to the local database.")

    df = pd.read_sql_query(
        "SELECT ts AS 'Timestamp', batch_id AS 'Batch', sample_id AS 'Sample', "
        "operator AS 'Operator', lac_mM AS 'Lactate (mM)', pyr_uM AS 'Pyruvate (μM)', "
        "status AS 'Status' FROM measurements ORDER BY id DESC", db)

    if df.empty:
        st.info("No records yet. Submit a measurement in the Review page.")
        return

    batches = ['All'] + sorted(df['Batch'].unique().tolist())
    sel = st.selectbox("Filter by Batch", batches)
    if sel != 'All':
        df = df[df['Batch'] == sel]

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button("📥 Export CSV", df.to_csv(index=False).encode('utf-8'),
                       file_name='PyrLac_History.csv', mime='text/csv')


def page_settings():
    status_bar()
    st.title("⚙️ Settings")

    st.markdown("### 🩺 Clinical Thresholds")
    st.number_input("Lactate threshold (mM)", min_value=0.1, step=0.1,
                    format="%.1f", key='lac_center')
    st.number_input("Pyruvate threshold (μM)", min_value=1.0, step=10.0,
                    format="%.0f", key='pyr_center')

    pct = st.slider("Borderline zone ±%", min_value=0, max_value=30,
                    value=int(round(st.session_state['border_pct'] * 100)),
                    key='border_slider')
    st.session_state['border_pct'] = pct / 100.0

    th = thresholds()
    st.caption(f"Borderline: Lactate {th['lac_lo']:.2f}–{th['lac_hi']:.2f} mM · "
               f"Pyruvate {th['pyr_lo']:.0f}–{th['pyr_hi']:.0f} μM")

    st.divider()
    st.markdown("### 🗄️ Data Management")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑 Clear Measurement History", use_container_width=True):
            db.execute("DELETE FROM measurements")
            db.commit()
            st.success("Measurement history cleared.")
    with col2:
        if st.button("🔄 Reset Calibration", use_container_width=True):
            for k in ['lac_slope', 'lac_int', 'lac_r2', 'lac_cal_ts',
                      'pyr_slope', 'pyr_int', 'pyr_r2', 'pyr_cal_ts']:
                st.session_state[k] = None
            st.success("Calibration reset.")


def page_about():
    status_bar()
    st.title("ℹ️ About")

    st.markdown(f"""
    **PyrLac Glow** — Ratiometric biosensor diagnostic terminal  
    Version **{__version__}** (Demo)

    ### 📐 Principle
    Dual-channel ADC measurement at **485 nm** (signal) and **420 nm** (reference).
    Ratio `ADC_485 / ADC_420` corrects for optical path and sample turbidity.
    Calibration curves convert ratios to lactate (mM) and pyruvate (μM).

    ### 🧬 Diagnosis Logic

    | Condition | Status |
    |---|---|
    | Lactate & Pyruvate both high | 🔴 High Cancer Risk |
    | Only Lactate high | 🟡 High Lactate |
    | Only Pyruvate high | 🟣 High Pyruvate |
    | Both normal | 🟢 Normal |
    | Near threshold (±{int(st.session_state['border_pct']*100)}%) | ⚪ Borderline |

    ### ⚕️ Disclaimer
    This software is for **research and pre-screening** use only.
    Results must be interpreted by qualified clinical staff in the context of
    the patient's full clinical picture. This software does **not** provide a
    definitive medical diagnosis.
    """)

# ==========================================
# 侧边栏导航
# ==========================================
with st.sidebar:
    st.markdown("## 🧬 PyrLac Glow")
    st.caption(f"v{__version__} · Demo")

    st.divider()
    st.markdown("### 👤 Session")
    st.text_input("Operator", key='operator')
    st.text_input("Batch ID", key='batch_id')

    if st.button("🆕 New Batch", use_container_width=True):
        st.session_state['batch_id'] = 'B' + datetime.now().strftime('%Y%m%d-%H%M')
        st.session_state['current_measurement'] = None
        st.rerun()

    st.divider()
    st.markdown("### 📅 Calibration")
    if cal_valid():
        st.success("✓ Valid (both probes)")
        for p in ['lac', 'pyr']:
            ts = st.session_state[f'{p}_cal_ts']
            days = (datetime.now() - datetime.fromisoformat(ts)).days
            st.caption(f"{p.capitalize()}: R²={st.session_state[f'{p}_r2']:.4f}, {days}d")
    else:
        st.warning("⚠ Calibration required")

    st.divider()
    st.markdown("### 🧭 Navigation")
    page = st.radio(
        "Navigate",
        ["📈 Calibration", "🔬 Measurement", "📋 Review",
         "🗂️ History", "⚙️ Settings", "ℹ️ About"],
        key='nav',
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("⚕️ Research / pre-screening use only.")

# ==========================================
# 分发
# ==========================================
if page == "📈 Calibration":
    page_calibration()
elif page == "🔬 Measurement":
    page_measurement()
elif page == "📋 Review":
    page_review()
elif page == "🗂️ History":
    page_history()
elif page == "⚙️ Settings":
    page_settings()
elif page == "ℹ️ About":
    page_about()
