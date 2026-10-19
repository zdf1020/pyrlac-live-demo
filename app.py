import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
    /* 全局字体优化 */
    html, body, [class*="css"] { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    
    /* 提示框美化 */
    .maintenance-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffe8a1 100%); 
        color: #856404; border-left: 6px solid #ffc107;
        padding: 16px 20px; border-radius: 8px; margin-bottom: 25px; 
        font-weight: 600; font-size: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* 诊断结果卡片美化 */
    .diagnosis-card {
        padding: 20px; border-radius: 12px; margin-bottom: 15px;
        background-color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border-left: 8px solid #ccc; transition: transform 0.2s;
    }
    .diagnosis-card:hover { transform: translateY(-3px); }
    .card-title { font-size: 20px; font-weight: 800; color: #333; margin-bottom: 10px; }
    .card-data { font-size: 15px; color: #555; margin-bottom: 5px; }
    .card-badge {
        display: inline-block; padding: 6px 12px; border-radius: 20px; 
        font-size: 14px; font-weight: 700; color: white; margin-top: 10px;
    }
    
    /* 状态颜色 */
    .bg-normal { background-color: #28a745; }      /* 绿色 */
    .bg-inflam { background-color: #ffc107; }      /* 黄色 */
    .bg-cancer { background-color: #dc3545; }      /* 红色 */
    .bg-highpyr { background-color: #6f42c1; }     /* 紫色 */

    .border-normal { border-left-color: #28a745; }
    .border-inflam { border-left-color: #ffc107; }
    .border-cancer { border-left-color: #dc3545; }
    .border-highpyr { border-left-color: #6f42c1; }

    /* 按钮统一美化 */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; padding: 8px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Diagnostic Terminal")
st.markdown("**Workflow:** Calibrate → Hardware Scan → Joint Diagnosis Summary")

# ==========================================
# 2. 侧边栏：硬件设置与阈值
# ==========================================
with st.sidebar:
    st.image("https://static.igem.wiki/teams/6263/wiki/layout/1-1-1.avif", width=100)
    st.header("🔌 Hardware Status")
    if SERIAL_AVAILABLE:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        port_select = st.selectbox("Arduino Port", ports if ports else ["No Port Found"])
        st.session_state['serial_port'] = port_select if ports else None
        st.success("System Online & Ready") if ports else st.warning("Waiting for Device")
    else:
        st.info("🔒 Cloud Demo Mode (Simulated Data)")
        st.session_state['serial_port'] = None

    st.divider()
    st.markdown("### 🩺 Clinical Thresholds")
    st.info("**Lactate:** `5.0 mM`\n\n**Pyruvate:** `200 μM`")

# --- 模拟获取硬件 ADC 数据 ---
def get_adc_value(probe_type, current_well):
    port = st.session_state.get('serial_port')
    if port:
        try:
            ser = serial.Serial(port, 9600, timeout=1)
            time.sleep(0.1)
            ser.reset_input_buffer()
            line = ser.readline().decode('utf-8').strip()
            ser.close()
            match = re.search(r"[-+]?\d*\.\d+|\d+", line)
            if match: return float(match.group())
        except Exception:
            pass 
    
    # 模拟数据：W-05 双高(癌症)，W-06 乳酸高(炎症)，W-07 正常
    time.sleep(0.2)
    if probe_type == "Lactate":
        if current_well == 5: return random.uniform(750, 900) 
        elif current_well == 6: return random.uniform(600, 700)
        elif current_well == 7: return random.uniform(80, 150)
        else: return random.uniform(50, 200)
    else:
        if current_well == 5: return random.uniform(380, 480) 
        elif current_well == 6: return random.uniform(40, 80) 
        elif current_well == 7: return random.uniform(50, 100)
        else: return random.uniform(30, 90)

# ==========================================
# 3. 核心功能区
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 1. Calibration", "🔬 2. Hardware Scan", "📋 3. Diagnosis Summary"])

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
        lac_y = st.text_input("Lactate ADC Signals", value="50.1, 128.4, 255.3, 605.7, 1210.2")
        if st.button("Run Lactate Calibration", type="primary"):
            xd = [float(i) for i in lac_x.split(',')]
            yd = [float(i) for i in lac_y.split(',')]
            res = linregress(xd, yd)
            st.session_state['lac_slope'] = res.slope
            st.session_state['lac_int'] = res.intercept
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Standards', marker=dict(color='#0068c9', size=12, line=dict(width=2, color='white'))))
            fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='#333', width=3, dash='dash')))
            fig.update_layout(title="Lactate Standard Curve", template="plotly_white", height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.success(f"Fitted: y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_y = st.text_input("Pyruvate ADC Signals", value="45.2, 152.8, 310.5, 782.1, 1550.8")
        if st.button("Run Pyruvate Calibration", type="primary"):
            xd = [float(i) for i in pyr_x.split(',')]
            yd = [float(i) for i in pyr_y.split(',')]
            res = linregress(xd, yd)
            st.session_state['pyr_slope'] = res.slope
            st.session_state['pyr_int'] = res.intercept
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Standards', marker=dict(color='#ff4b4b', size=12, line=dict(width=2, color='white'))))
            fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='#333', width=3, dash='dash')))
            fig.update_layout(title="Pyruvate Standard Curve", template="plotly_white", height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.success(f"Fitted: y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")

# ------------------------------------------
# Tab 2: 硬件扫描
# ------------------------------------------
with tab2:
    lac_slope = st.session_state.get('lac_slope', 115.0)
    lac_int = st.session_state.get('lac_int', 50.0)
    pyr_slope = st.session_state.get('pyr_slope', 1.5)
    pyr_int = st.session_state.get('pyr_int', 40.0)
    
    col_setup, col_results = st.columns([1, 2], gap="large")
    
    with col_setup:
        st.markdown("### ⚙️ Scan Setup")
        probe_type = st.radio("Probe Mode", ["Lactate", "Pyruvate"])
        num_wells = st.slider("Number of Wells", 1, 16, 8)
        
        if st.button("▶ Start Detection", type="primary"):
            st.session_state['scan_data'] = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(1, num_wells + 1):
                status_text.text(f"Reading Well: W-{i:02d}...")
                adc = get_adc_value(probe_type, i)
                
                conc = max(0, (adc - lac_int) / lac_slope) if probe_type == "Lactate" else max(0, (adc - pyr_int) / pyr_slope)
                    
                st.session_state['scan_data'].append({
                    "Sample ID": f"W-{i:02d}",
                    "ADC": round(adc, 1),
                    "Concentration": round(conc, 2)
                })
                progress_bar.progress(i / num_wells)
            
            status_text.success("✅ Scan Completed!")

    with col_results:
        if 'scan_data' in st.session_state and st.session_state['scan_data']:
            df = pd.DataFrame(st.session_state['scan_data'])
            unit = "mM" if probe_type == "Lactate" else "μM"
            
            st.markdown(f"### 📋 {probe_type} Results ({unit})")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            fig = px.bar(df, x="Sample ID", y="Concentration", 
                         title=f"{probe_type} Concentration Profile",
                         color="Concentration", color_continuous_scale="Blues" if probe_type=="Lactate" else "Reds")
            fig.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("💾 Save for Joint Diagnosis", type="primary"):
                if 'saved_lac' not in st.session_state: st.session_state['saved_lac'] = {}
                if 'saved_pyr' not in st.session_state: st.session_state['saved_pyr'] = {}
                
                for row in st.session_state['scan_data']:
                    if probe_type == "Lactate":
                        st.session_state['saved_lac'][row['Sample ID']] = row['Concentration']
                    else:
                        st.session_state['saved_pyr'][row['Sample ID']] = row['Concentration']
                st.success("Data saved! Go to Diagnosis Summary.")

# ------------------------------------------
# Tab 3: 诊断摘要（卡片看板）
# ------------------------------------------
with tab3:
    st.header("Diagnostic Summary")
    
    if 'saved_lac' not in st.session_state or 'saved_pyr' not in st.session_state:
        st.info("Please scan and save both Lactate and Pyruvate results first.")
    else:
        common_ids = sorted(list(set(st.session_state['saved_lac'].keys()) & set(st.session_state['saved_pyr'].keys())))
        
        if not common_ids:
            st.warning("No matching Sample IDs found.")
        else:
            # 汇总数据表
            joint_data = []
            for sid in common_ids:
                c_lac = st.session_state['saved_lac'][sid]
                c_pyr = st.session_state['saved_pyr'][sid]
                
                if c_lac >= 5.0 and c_pyr >= 200: 
                    status, bg_cls, br_cls = "High Cancer Risk", "bg-cancer", "border-cancer"
                elif c_lac >= 5.0 and c_pyr < 200: 
                    status, bg_cls, br_cls = "Inflammation", "bg-inflam", "border-inflam"
                elif c_lac < 5.0 and c_pyr >= 200: 
                    status, bg_cls, br_cls = "High Pyruvate", "bg-highpyr", "border-highpyr"
                else: 
                    status, bg_cls, br_cls = "Normal", "bg-normal", "border-normal"
                
                joint_data.append({
                    "Sample ID": sid, "Lactate (mM)": c_lac, "Pyruvate (μM)": c_pyr,
                    "Status": status, "BgClass": bg_cls, "BrClass": br_cls
                })
            
            # 顶部统计概览
            df_joint = pd.DataFrame(joint_data)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Samples", len(df_joint))
            c2.metric("Cancer Risk", len(df_joint[df_joint['Status']=="High Cancer Risk"]), delta_color="inverse")
            c3.metric("Inflammation", len(df_joint[df_joint['Status']=="Inflammation"]), delta_color="off")
            c4.metric("Normal", len(df_joint[df_joint['Status']=="Normal"]))
            
            st.divider()
            st.markdown("### 🩺 Patient Sample Cards")
            
            # 使用网格布局渲染卡片
            cols = st.columns(3) # 每行3个卡片
            
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
            
            if st.button("🗑 Clear All Data"):
                st.session_state['saved_lac'] = {}
                st.session_state['saved_pyr'] = {}
                st.rerun()
