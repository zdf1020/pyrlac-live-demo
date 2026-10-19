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
# 1. 页面基础配置与 CSS 注入
# ==========================================
st.set_page_config(
    page_title="PyrLac Glow | Diagnostic System",
    page_icon="🧬",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card {
        background-color: white; padding: 24px 30px; border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08); border-left: 8px solid #ccc; margin-bottom: 20px;
    }
    .metric-value { font-size: 42px; font-weight: 800; line-height: 1.1; }
    .metric-label { font-size: 14px; color: #666; font-weight: 700; text-transform: uppercase; }
    .risk-text { font-size: 28px; font-weight: 800; margin-top: 12px;}
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Automated Diagnostic System")
st.markdown("**Workflow:** Load Disk → Close Lid → Select Mode → Start Scan → Analyze Results")

# ==========================================
# 2. 侧边栏：硬件设置与阈值
# ==========================================
with st.sidebar:
    st.header("🔌 Hardware Settings")
    if SERIAL_AVAILABLE:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        port_select = st.selectbox("Arduino Port", ports if ports else ["No Port Found"])
        st.session_state['serial_port'] = port_select if ports else None
    else:
        st.info("🔒 Cloud Mode: Using simulated hardware data.")
        st.session_state['serial_port'] = None

    st.divider()
    st.markdown("**Clinical Thresholds:**")
    st.markdown("- Lactate: `5.0 mM`\n- Pyruvate: `200 μM`")

# --- 模拟获取硬件 ADC 数据 ---
def get_adc_value(probe_type, current_well):
    """
    如果连接了硬件，尝试读取真实串口。
    如果没连接，根据当前孔位生成逼真的模拟数据（比如孔位 5 设为强阳性）。
    """
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
            pass # 如果读取失败，回退到模拟数据
    
    # 模拟数据生成（让结果有高低起伏，方便展示）
    time.sleep(0.1) # 模拟机械转动延迟
    if probe_type == "Lactate":
        # 模拟：第5孔高浓度，第6孔炎症，其余正常
        if current_well == 5: return random.uniform(700, 900) 
        elif current_well == 6: return random.uniform(600, 750)
        else: return random.uniform(50, 200)
    else:
        # Pyruvate 模拟
        if current_well == 5: return random.uniform(350, 450) # 第5孔也是高
        elif current_well == 6: return random.uniform(50, 100) # 第6孔正常
        else: return random.uniform(40, 80)

# ==========================================
# 3. 核心功能区
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 1. Calibration", "🔬 2. Hardware Scan", "📊 3. Joint Diagnosis"])

# ------------------------------------------
# Tab 1: 双通道校准
# ------------------------------------------
with tab1:
    st.header("Dual-Probe Calibration")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lactate Probe")
        lac_x = st.text_input("Lactate Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        lac_y = st.text_input("Lactate ADC Signals", value="50.1, 128.4, 255.3, 605.7, 1210.2")
        if st.button("Calibrate Lactate"):
            res = linregress([float(i) for i in lac_x.split(',')], [float(i) for i in lac_y.split(',')])
            st.session_state['lac_slope'] = res.slope
            st.session_state['lac_int'] = res.intercept
            st.success(f"Lactate Curve fitted. y = {res.slope:.2f}x + {res.intercept:.2f}")

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_y = st.text_input("Pyruvate ADC Signals", value="45.2, 152.8, 310.5, 782.1, 1550.8")
        if st.button("Calibrate Pyruvate"):
            res = linregress([float(i) for i in pyr_x.split(',')], [float(i) for i in pyr_y.split(',')])
            st.session_state['pyr_slope'] = res.slope
            st.session_state['pyr_int'] = res.intercept
            st.success(f"Pyruvate Curve fitted. y = {res.slope:.2f}x + {res.intercept:.2f}")

# ------------------------------------------
# Tab 2: 硬件批量扫描
# ------------------------------------------
with tab2:
    st.header("Automated Plate Scanner")
    
    # 获取曲线参数
    lac_slope = st.session_state.get('lac_slope', 115.0)
    lac_int = st.session_state.get('lac_int', 50.0)
    pyr_slope = st.session_state.get('pyr_slope', 1.5)
    pyr_int = st.session_state.get('pyr_int', 40.0)
    
    col_setup, col_results = st.columns([1, 2], gap="large")
    
    with col_setup:
        st.markdown("### ⚙️ Scan Setup")
        probe_type = st.radio("Select Probe Mode", ["Lactate", "Pyruvate"])
        num_wells = st.slider("Number of Wells (Samples)", 1, 16, 8)
        
        if st.button("▶ Start Detection", type="primary"):
            st.session_state['scanning'] = True
            st.session_state['scan_data'] = [] # 清空旧数据
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(1, num_wells + 1):
                status_text.text(f"Scanning Well ID: W-{i:02d}...")
                adc = get_adc_value(probe_type, i)
                
                # 计算浓度
                if probe_type == "Lactate":
                    conc = max(0, (adc - lac_int) / lac_slope)
                else:
                    conc = max(0, (adc - pyr_int) / pyr_slope)
                    
                st.session_state['scan_data'].append({
                    "Sample ID": f"W-{i:02d}",
                    "ADC": round(adc, 1),
                    "Concentration": round(conc, 2)
                })
                progress_bar.progress(i / num_wells)
            
            status_text.success("✅ Scan Completed!")
            st.session_state['scanning'] = False

    with col_results:
        if 'scan_data' in st.session_state and st.session_state['scan_data']:
            df = pd.DataFrame(st.session_state['scan_data'])
            unit = "mM" if probe_type == "Lactate" else "μM"
            
            st.markdown(f"### 📋 {probe_type} Results ({unit})")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # 画柱状图
            fig = px.bar(df, x="Sample ID", y="Concentration", 
                         title=f"{probe_type} Concentration across Wells",
                         color="Concentration", color_continuous_scale="Blues" if probe_type=="Lactate" else "Reds")
            st.plotly_chart(fig, use_container_width=True)
            
            # 将当前扫描数据存入长期存储，供Tab 3使用
            if st.button("💾 Save Results for Joint Diagnosis"):
                if 'saved_lac' not in st.session_state: st.session_state['saved_lac'] = {}
                if 'saved_pyr' not in st.session_state: st.session_state['saved_pyr'] = {}
                
                for row in st.session_state['scan_data']:
                    if probe_type == "Lactate":
                        st.session_state['saved_lac'][row['Sample ID']] = row['Concentration']
                    else:
                        st.session_state['saved_pyr'][row['Sample ID']] = row['Concentration']
                st.success("Results saved! Go to Tab 3 to view Joint Diagnosis.")

# ------------------------------------------
# Tab 3: 联合诊断
# ------------------------------------------
with tab3:
    st.header("Dual-Probe Joint Diagnosis")
    
    if 'saved_lac' not in st.session_state or 'saved_pyr' not in st.session_state:
        st.info("Please scan and save both Lactate and Pyruvate results first.")
    else:
        # 匹配同一 ID 的数据
        common_ids = set(st.session_state['saved_lac'].keys()) & set(st.session_state['saved_pyr'].keys())
        
        if not common_ids:
            st.warning("No matching Sample IDs found between Lactate and Pyruvate datasets.")
        else:
            joint_data = []
            for sid in sorted(list(common_ids)):
                c_lac = st.session_state['saved_lac'][sid]
                c_pyr = st.session_state['saved_pyr'][sid]
                
                # 判定
                if c_lac >= 5.0 and c_pyr >= 200: status, color = "High Cancer Risk", "#B91C1C"
                elif c_lac >= 5.0 and c_pyr < 200: status, color = "Inflammation", "#A86A1A"
                elif c_lac < 5.0 and c_pyr >= 200: status, color = "High Pyruvate", "#5A4A9A"
                else: status, color = "Normal", "#2C6E4A"
                
                joint_data.append({
                    "Sample ID": sid, "Lactate (mM)": c_lac, "Pyruvate (μM)": c_pyr,
                    "Status": status, "Color": color
                })
            
            df_joint = pd.DataFrame(joint_data)
            st.dataframe(df_joint.drop(columns=['Color']), use_container_width=True, hide_index=True)
            
            # 画四象限图
            fig = go.Figure()
            # 背景
            fig.add_shape(type="rect", x0=0, y0=0, x1=200, y1=5, fillcolor="#bfe3c8", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=0, y0=5, x1=200, y1=30, fillcolor="#f6d9a8", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=200, y0=5, x1=800, y1=30, fillcolor="#e9b8d4", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=200, y0=0, x1=800, y1=5, fillcolor="#c9c4e6", opacity=0.4, line_width=0)
            # 阈值线
            fig.add_shape(type="line", x0=200, y0=0, x1=200, y1=30, line=dict(color="#6A3AB2", width=2, dash="dash"))
            fig.add_shape(type="line", x0=0, y0=5, x1=800, y1=5, line=dict(color="#6A3AB2", width=2, dash="dash"))
            
            # 数据点
            for _, row in df_joint.iterrows():
                fig.add_trace(go.Scatter(
                    x=[min(row['Pyruvate (μM)'], 800)], y=[min(row['Lactate (mM)'], 30)],
                    mode='markers', marker=dict(size=14, color=row['Color'], line=dict(width=2, color='white')),
                    hoverinfo='text', text=[row['Sample ID']], showlegend=False
                ))
                
            fig.update_layout(
                xaxis_title="Pyruvate Concentration (μM)", yaxis_title="Lactate Concentration (mM)",
                xaxis=dict(range=[0, 800], showgrid=False), yaxis=dict(range=[0, 30], showgrid=False),
                height=500, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🗑 Clear All Saved Data"):
                st.session_state['saved_lac'] = {}
                st.session_state['saved_pyr'] = {}
                st.rerun()
