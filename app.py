import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import time
import random
import re

# 尝试导入串口库
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ==========================================
# 1. 页面基础配置与全局 CSS 美化
# ==========================================
st.set_page_config(
    page_title="PyrLac Glow | Diagnostic System",
    page_icon="🧬",
    layout="wide"
)

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    .formula-banner {
        background: linear-gradient(90deg, #433262 0%, #6A3AB2 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-size: 20px; font-weight: bold;
        margin-bottom: 25px; box-shadow: 0 4px 15px rgba(106,58,178,0.3);
    }
    .maintenance-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffe8a1 100%); 
        color: #856404; border-left: 6px solid #ffc107;
        padding: 16px 20px; border-radius: 8px; margin-bottom: 25px; 
        font-weight: 600; font-size: 15px;
    }
    .diagnosis-card {
        padding: 20px; border-radius: 12px; margin-bottom: 15px;
        background-color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border-left: 8px solid #ccc; transition: transform 0.2s;
    }
    .card-title { font-size: 20px; font-weight: 800; color: #333; margin-bottom: 10px; }
    .card-data { font-size: 15px; color: #555; margin-bottom: 5px; }
    .card-badge {
        display: inline-block; padding: 6px 12px; border-radius: 20px; 
        font-size: 14px; font-weight: 700; color: white; margin-top: 10px;
    }
    .bg-normal { background-color: #28a745; }
    .bg-inflam { background-color: #ffc107; color: #333; }
    .bg-cancer { background-color: #dc3545; }
    .bg-pdhc { background-color: #6f42c1; }
    .border-normal { border-left-color: #28a745; }
    .border-inflam { border-left-color: #ffc107; }
    .border-cancer { border-left-color: #dc3545; }
    .border-pdhc { border-left-color: #6f42c1; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; padding: 8px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Diagnostic Terminal")
st.markdown('<div class="formula-banner">Ratiometric Signal (Ratio) = ADC (485 nm) / ADC (420 nm)</div>', unsafe_allow_html=True)

# ==========================================
# 2. 侧边栏（双端口：硬件 / 演示）
# ==========================================
with st.sidebar:
    st.image("https://static.igem.wiki/teams/6263/wiki/layout/1-1-1.avif", width=100)
    st.header("🔌 Data Source")

    source_mode = st.radio(
        "Select Input Port",
        ["🔌 Hardware Port", "🎭 Demo Port (Simulated)"],
        index=1 if not SERIAL_AVAILABLE else 0,
        help="Hardware 连接真实 Arduino；Demo 使用内置模拟例子"
    )

    st.divider()

    if source_mode == "🔌 Hardware Port":
        st.markdown("### Hardware Connection")
        if SERIAL_AVAILABLE:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            port_select = st.selectbox(
                "Arduino Port",
                ports if ports else ["No Port Found"]
            )
            st.session_state['serial_port'] = port_select if ports else None
            st.session_state['data_source'] = 'hardware'
            if ports:
                st.success(f"Connected: {port_select}")
            else:
                st.warning("⚠️ No device detected")
        else:
            st.session_state['serial_port'] = None
            st.session_state['data_source'] = 'hardware'
            st.error("❌ pyserial not installed. Please `pip install pyserial`.")

    else:  # Demo Port
        st.markdown("### Demo Mode")
        st.session_state['serial_port'] = None
        st.session_state['data_source'] = 'demo'
        st.info("🎭 Running with built-in sample data.\n\nNo real hardware required.")
        demo_sample = st.selectbox(
            "Demo Sample Set",
            ["Sample Set A (Mixed)", "Sample Set B (Normal)", "Sample Set C (Abnormal)"]
        )
        st.session_state['demo_sample_set'] = demo_sample

    st.divider()
    st.markdown("### 🩺 Clinical Thresholds")
    st.info("**Lactate:** `5.0 mM`\n\n**Pyruvate:** `200 μM`")

# ==========================================
# 硬件读取
# ==========================================
def read_from_hardware(port):
    """从串口读取真实 ADC 值；失败返回 None"""
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(0.05)
        ser.reset_input_buffer()
        line = ser.readline().decode('utf-8').strip()
        ser.close()
        match = re.search(r"420:(\d+),\s*485:(\d+)", line)
        if match:
            return float(match.group(1)), float(match.group(2))
    except Exception:
        pass
    return None

# ==========================================
# 演示数据（三套示例）
# ==========================================
def get_demo_adc(probe_type, well_idx, sample_set):
    """
    well_idx: 1, 2, 3
    返回 (adc_420, adc_485)
    """
    if sample_set == "Sample Set A (Mixed)":
        if probe_type == "Lactate":
            adc_485 = [150, 620, 175][well_idx - 1]
        else:
            adc_485 = [140, 155, 460][well_idx - 1]
        seed = 100 + well_idx
    elif sample_set == "Sample Set B (Normal)":
        adc_485 = [145, 160, 152][well_idx - 1]
        seed = 200 + well_idx
    else:  # Sample Set C (Abnormal)
        if probe_type == "Lactate":
            adc_485 = [600, 640, 580][well_idx - 1]
        else:
            adc_485 = [420, 470, 450][well_idx - 1]
        seed = 300 + well_idx

    rng = random.Random(seed)
    adc_420 = rng.uniform(95, 105)
    adc_485 = adc_485 + rng.uniform(-10, 10)
    return adc_420, adc_485


def get_adc_values(probe_type, current_well):
    """统一入口：根据 data_source 分流到硬件或演示"""
    source = st.session_state.get('data_source', 'demo')

    if source == 'hardware':
        port = st.session_state.get('serial_port')
        if port:
            result = read_from_hardware(port)
            if result:
                return result
            st.warning("⚠️ Hardware read failed, using demo data for this well.")
        else:
            st.error("❌ No hardware port selected.")

    time.sleep(0.2)
    sample_set = st.session_state.get('demo_sample_set', "Sample Set A (Mixed)")
    return get_demo_adc(probe_type, current_well, sample_set)

# ==========================================
# 3. 核心功能区
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 1. Calibration (Ratio)", "🔬 2. Hardware Scan", "📋 3. Diagnosis Summary"])

# ------------------------------------------
# Tab 1: 校准
# ------------------------------------------
with tab1:
    st.markdown("""
    <div class="maintenance-box">
        ⚠️ MAINTENANCE REQUIRED: Standard curves must be updated every 1 month or with new reagent batches.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lactate Probe")
        lac_x = st.text_input("Lactate Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        lac_y420 = st.text_input("Lactate ADC_420 (Ref)", value="100, 102, 98, 105, 101")
        lac_y485 = st.text_input("Lactate ADC_485 (Signal)", value="120, 210, 320, 620, 1150")
        
        if st.button("Run Lactate Calibration", type="primary"):
            xd = [float(i) for i in lac_x.split(',')]
            y420 = [float(i) for i in lac_y420.split(',')]
            y485 = [float(i) for i in lac_y485.split(',')]
            
            ratios = [y485[i] / y420[i] for i in range(len(xd))]
            
            res = linregress(xd, ratios)
            st.session_state['lac_slope'] = res.slope
            st.session_state['lac_int'] = res.intercept
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xd, y=ratios, mode='markers', name='Standards', marker=dict(color='#0068c9', size=12)))
            fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='#333', width=3, dash='dash')))
            fig.update_layout(title="Lactate Calibration (Ratio vs Conc)", xaxis_title="Conc (mM)", yaxis_title="Ratio (485/420)", height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.success(f"Fitted: Ratio = {res.slope:.3f} * Conc + {res.intercept:.3f} | R² = {res.rvalue**2:.4f}")

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_y420 = st.text_input("Pyruvate ADC_420 (Ref)", value="100, 98, 102, 100, 99")
        pyr_y485 = st.text_input("Pyruvate ADC_485 (Signal)", value="120, 180, 250, 550, 1050")
        
        if st.button("Run Pyruvate Calibration", type="primary"):
            xd = [float(i) for i in pyr_x.split(',')]
            y420 = [float(i) for i in pyr_y420.split(',')]
            y485 = [float(i) for i in pyr_y485.split(',')]
            
            ratios = [y485[i] / y420[i] for i in range(len(xd))]
            
            res = linregress(xd, ratios)
            st.session_state['pyr_slope'] = res.slope
            st.session_state['pyr_int'] = res.intercept
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xd, y=ratios, mode='markers', name='Standards', marker=dict(color='#ff4b4b', size=12)))
            fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='#333', width=3, dash='dash')))
            fig.update_layout(title="Pyruvate Calibration (Ratio vs Conc)", xaxis_title="Conc (μM)", yaxis_title="Ratio (485/420)", height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.success(f"Fitted: Ratio = {res.slope:.4f} * Conc + {res.intercept:.3f} | R² = {res.rvalue**2:.4f}")

# ------------------------------------------
# Tab 2: 硬件扫描
# ------------------------------------------
with tab2:
    lac_slope = st.session_state.get('lac_slope', 0.1)
    lac_int = st.session_state.get('lac_int', 1.0)
    pyr_slope = st.session_state.get('pyr_slope', 0.001)
    pyr_int = st.session_state.get('pyr_int', 1.0)

    source = st.session_state.get('data_source', 'demo')
    if source == 'hardware':
        st.success(f"🔌 Hardware Mode | Port: {st.session_state.get('serial_port', 'N/A')}")
    else:
        st.info(f"🎭 Demo Mode | Set: {st.session_state.get('demo_sample_set', 'N/A')}")

    col_setup, col_results = st.columns([1, 2], gap="large")
    
    with col_setup:
        st.markdown("### ⚙️ Scan Setup")
        probe_type = st.radio("Probe Mode", ["Lactate", "Pyruvate"])
        st.caption("📌 3 sample wells are scanned per probe.")
        
        if st.button("▶ Start Detection", type="primary"):
            st.session_state['scan_data'] = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            num_wells = 3
            for i in range(1, num_wells + 1):
                status_text.text(f"Reading Well: W-{i:02d}...")
                adc_420, adc_485 = get_adc_values(probe_type, i)
                ratio = adc_485 / adc_420
                
                if probe_type == "Lactate":
                    conc = max(0, (ratio - lac_int) / lac_slope)
                else:
                    conc = max(0, (ratio - pyr_int) / pyr_slope)
                    
                st.session_state['scan_data'].append({
                    "Sample ID": f"W-{i:02d}",
                    "ADC_420": round(adc_420, 1),
                    "ADC_485": round(adc_485, 1),
                    "Ratio (485/420)": round(ratio, 3),
                    "Conc.": round(conc, 2)
                })
                progress_bar.progress(i / num_wells)
            
            status_text.success("✅ Scan Completed!")

    with col_results:
        if 'scan_data' in st.session_state and st.session_state['scan_data']:
            df = pd.DataFrame(st.session_state['scan_data'])
            unit = "mM" if probe_type == "Lactate" else "μM"
            
            st.markdown(f"### 📋 {probe_type} Results ({unit})")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            if st.button("💾 Save for Joint Diagnosis", type="primary"):
                if 'saved_lac' not in st.session_state: st.session_state['saved_lac'] = {}
                if 'saved_pyr' not in st.session_state: st.session_state['saved_pyr'] = {}
                
                for row in st.session_state['scan_data']:
                    if probe_type == "Lactate":
                        st.session_state['saved_lac'][row['Sample ID']] = row['Conc.']
                    else:
                        st.session_state['saved_pyr'][row['Sample ID']] = row['Conc.']
                st.success("Data saved! Go to Diagnosis Summary.")

# ------------------------------------------
# Tab 3: 诊断摘要
# ------------------------------------------
with tab3:
    st.header("Diagnosis Report")
    
    if 'saved_lac' not in st.session_state or 'saved_pyr' not in st.session_state:
        st.info("Please scan and save both Lactate and Pyruvate results first.")
    else:
        common_ids = sorted(list(set(st.session_state['saved_lac'].keys()) & set(st.session_state['saved_pyr'].keys())))
        
        if not common_ids:
            st.warning("No matching Sample IDs found.")
        else:
            joint_data = []
            for sid in common_ids:
                c_lac = st.session_state['saved_lac'][sid]
                c_pyr = st.session_state['saved_pyr'][sid]
                
                if c_lac >= 5.0 and c_pyr >= 200: 
                    status, bg_cls, br_cls = "High Cancer Risk", "bg-cancer", "border-cancer"
                elif c_lac >= 5.0 and c_pyr < 200: 
                    status, bg_cls, br_cls = "Inflammation", "bg-inflam", "border-inflam"
                elif c_lac < 5.0 and c_pyr >= 200: 
                    status, bg_cls, br_cls = "PDHC", "bg-pdhc", "border-pdhc"
                else: 
                    status, bg_cls, br_cls = "Normal", "bg-normal", "border-normal"
                
                joint_data.append({
                    "Sample ID": sid, "Lactate (mM)": c_lac, "Pyruvate (μM)": c_pyr,
                    "Status": status, "BgClass": bg_cls, "BrClass": br_cls
                })
            
            df_joint = pd.DataFrame(joint_data)
            
            st.markdown("### 🩺 Patient Sample Cards")
            
            cols = st.columns(3)
            for idx, row in df_joint.iterrows():
                col_idx = idx % 3
                with cols[col_idx]:
                    st.markdown(f"""
                    <div class="diagnosis-card {row['BrClass']}">
                        <div class="card-title">{row['Sample ID']}</div>
                        <div class="card-data">Lactate: <b>{row['Lactate (mM)']:.2f} mM</b></div>
                        <div class="card-data">Pyruvate: <b>{row['Pyruvate (μM)']:.1f} μM</b></div>
                        <div class="card-badge {row['BgClass']}">{row['Status']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()
            st.markdown("### 📄 Export & Reports")
            csv = df_joint.drop(columns=['BgClass', 'BrClass']).to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download All Results (CSV)",
                data=csv,
                file_name='PyrLac_Glow_Batch_Results.csv',
                mime='text/csv',
                type="primary"
            )
            
            for idx, row in df_joint.iterrows():
                with st.expander(f"📄 Report for {row['Sample ID']} - {row['Status']}"):
                    # ★ 为 PDHC 增加专门的临床建议
                    if row['Status'] == 'High Cancer Risk':
                        rec_text = 'Immediate clinical consultation strongly advised.'
                        risk_color = '#B91C1C'
                    elif row['Status'] == 'Inflammation':
                        rec_text = 'Slight elevation detected. Follow-up physical examination recommended.'
                        risk_color = '#D97706'
                    elif row['Status'] == 'PDHC':
                        rec_text = ('Elevated pyruvate with normal lactate suggests impaired pyruvate utilization. '
                                    'Evaluate the lactate/pyruvate (L/P) ratio and PDHC function, '
                                    'and screen for vitamin B1 (thiamine) deficiency as a reversible cause.')
                        risk_color = '#6f42c1'
                    else:
                        rec_text = 'No significant metabolic risk detected. Continue routine checkups.'
                        risk_color = '#2C6E4A'

                    report_html = f"""
                    <div style="border: 2px solid #333; padding: 30px; border-radius: 8px; font-family: Arial, sans-serif; max-width: 650px; margin: auto; background-color: #fff;">
                        <h2 style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-top: 0;">PyrLac Glow Diagnostic Report</h2>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                            <div><b>Sample ID:</b> {row['Sample ID']}</div>
                            <div><b>Date:</b> {time.strftime('%Y-%m-%d')}</div>
                        </div>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                            <tr style="background-color: #f2f2f2;">
                                <th style="border: 1px solid #ddd; padding: 10px; text-align: left;">Biomarker</th>
                                <th style="border: 1px solid #ddd; padding: 10px; text-align: center;">Result</th>
                                <th style="border: 1px solid #ddd; padding: 10px; text-align: center;">Reference Threshold</th>
                            </tr>
                            <tr>
                                <td style="border: 1px solid #ddd; padding: 10px;">Lactate</td>
                                <td style="border: 1px solid #ddd; padding: 10px; text-align: center; font-weight: bold; color: {risk_color};">{row['Lactate (mM)']:.2f} mM</td>
                                <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">&lt; 5.0 mM</td>
                            </tr>
                            <tr>
                                <td style="border: 1px solid #ddd; padding: 10px;">Pyruvate</td>
                                <td style="border: 1px solid #ddd; padding: 10px; text-align: center; font-weight: bold; color: {risk_color};">{row['Pyruvate (μM)']:.1f} μM</td>
                                <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">&lt; 200 μM</td>
                            </tr>
                        </table>
                        <h3 style="margin-top: 25px; color: {risk_color}; border-bottom: 1px solid #eee; padding-bottom: 5px;">Diagnosis: {row['Status']}</h3>
                        <p style="font-size: 14px; line-height: 1.5;"><b>Clinical Recommendation:</b><br>{rec_text}</p>
                        <p style="margin-top: 40px; font-size: 12px; color: #777; text-align: center;">Generated by PyrLac Glow Automated Diagnostic System.<br>For research and pre-screening use only. Not a definitive diagnosis.</p>
                    </div>
                    """
                    st.markdown(report_html, unsafe_allow_html=True)
                    st.download_button(
                        label=f"📥 Download Report for {row['Sample ID']} (HTML)",
                        data=report_html.encode('utf-8'),
                        file_name=f"PyrLac_Report_{row['Sample ID']}.html",
                        mime="text/html",
                        key=f"dl_report_{row['Sample ID']}"
                    )

            st.divider()
            if st.button("🗑 Clear All Data"):
                st.session_state['saved_lac'] = {}
                st.session_state['saved_pyr'] = {}
                st.rerun()
