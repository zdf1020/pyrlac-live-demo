import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import time
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
    page_title="PyrLac Glow | Diagnostic Interface",
    page_icon="🧬",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card {
        background-color: white;
        padding: 24px 30px;
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border-left: 8px solid #ccc;
        margin-bottom: 20px;
    }
    .metric-value { font-size: 42px; font-weight: 800; line-height: 1.1; }
    .metric-label { font-size: 14px; color: #666; font-weight: 700; text-transform: uppercase; }
    .risk-text { font-size: 28px; font-weight: 800; margin-top: 12px;}
    .note-text { font-size: 16px; color: #555; margin-top: 12px; line-height: 1.6;}
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    
    /* 模拟终端样式 */
    .terminal-box {
        background-color: #1e1e1e;
        color: #00ff00;
        font-family: 'Courier New', Courier, monospace;
        padding: 15px;
        border-radius: 8px;
        height: 150px;
        overflow-y: auto;
        font-size: 14px;
        line-height: 1.5;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Rapid Diagnostic Interface")
st.markdown("**Hardware:** Dual-Probe Detection | **Sensors:** Lactate Probe & Pyruvate Probe")

# ==========================================
# 2. 侧边栏：硬件连接与设置
# ==========================================
with st.sidebar:
    st.header("🔌 Hardware Connection")
    if SERIAL_AVAILABLE:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            st.warning("No serial ports detected. (Expected on cloud).")
            port_select = st.text_input("Enter COM Port manually (e.g., COM3)", value="")
        else:
            port_select = st.selectbox("Select Arduino Port", ports)
        baud_rate = st.number_input("Baud Rate", value=9600)
        st.session_state['serial_port'] = port_select
        st.session_state['baud_rate'] = baud_rate
    else:
        st.info("🔒 Cloud Mode: Serial ports disabled. Run locally to connect hardware.")
        st.session_state['serial_port'] = None

    st.divider()
    st.markdown("**Clinical Thresholds:**")
    st.markdown("- Lactate: `5.0 mM`\n- Pyruvate: `200 μM`")

# --- 串口读取函数 ---
def read_hardware_signal():
    port = st.session_state.get('serial_port')
    baud = st.session_state.get('baud_rate', 9600)
    if not port: return None
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.1)
        ser.reset_input_buffer()
        line = ser.readline().decode('utf-8').strip()
        ser.close()
        if not line: return None
        # 提取字符串中的数字
        match = re.search(r"[-+]?\d*\.\d+|\d+", line)
        if match: return float(match.group())
        else: return None
    except Exception as e:
        st.error(f"Serial Error: {e}")
        return None

# ==========================================
# 3. 核心功能区
# ==========================================
tab1, tab2 = st.tabs(["📈 1. Calibration Mode", "🧪 2. Diagnostic Interface"])

# ------------------------------------------
# Tab 1: 双通道校准
# ------------------------------------------
with tab1:
    st.header("Dual-Probe Calibration")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lactate Probe")
        lac_x = st.text_input("Lactate Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        lac_y = st.text_input("Lactate Probe ADC Signals", value="50.1, 128.4, 255.3, 605.7, 1210.2")
        if st.button("Run Lactate Calibration", type="primary"):
            try:
                xd = [float(i) for i in lac_x.split(',')]
                yd = [float(i) for i in lac_y.split(',')]
                res = linregress(xd, yd)
                st.session_state['lac_slope'] = res.slope
                st.session_state['lac_int'] = res.intercept
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Data', marker=dict(color='#0068c9', size=10)))
                fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='black', dash='dash')))
                fig.update_layout(title="Lactate Standard Curve", xaxis_title="Conc (mM)", yaxis_title="ADC", height=280, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")
            except: st.error("Error parsing inputs.")

    with col2:
        st.subheader("Pyruvate Probe")
        pyr_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        pyr_y = st.text_input("Pyruvate Probe ADC Signals", value="45.2, 152.8, 310.5, 782.1, 1550.8")
        if st.button("Run Pyruvate Calibration", type="primary"):
            try:
                xd = [float(i) for i in pyr_x.split(',')]
                yd = [float(i) for i in pyr_y.split(',')]
                res = linregress(xd, yd)
                st.session_state['pyr_slope'] = res.slope
                st.session_state['pyr_int'] = res.intercept
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Data', marker=dict(color='#ff4b4b', size=10)))
                fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='black', dash='dash')))
                fig.update_layout(title="Pyruvate Standard Curve", xaxis_title="Conc (μM)", yaxis_title="ADC", height=280, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")
            except: st.error("Error parsing inputs.")

# ------------------------------------------
# Tab 2: 联合诊断 & 数据终端
# ------------------------------------------
with tab2:
    # 获取校准参数（如果没有校准，使用默认模拟值）
    lac_slope = st.session_state.get('lac_slope', 115.0)
    lac_int = st.session_state.get('lac_int', 50.0)
    pyr_slope = st.session_state.get('pyr_slope', 1.5)
    pyr_int = st.session_state.get('pyr_int', 40.0)

    st.header("Joint Diagnostic Interface")
    
    # 初始化历史记录
    if 'history' not in st.session_state:
        st.session_state['history'] = []
    if 'current_sample' not in st.session_state:
        st.session_state['current_sample'] = None

    col_left, col_right = st.columns([1.2, 1.5], gap="large")
    
    # === 左侧：输入与数据终端 ===
    with col_left:
        st.markdown("### 🧪 Hardware Data Input")
        
        sample_id = st.text_input("Sample ID", value=f"S-{len(st.session_state['history'])+1:03d}")
        
        # Lactate 输入
        col_lac, col_lac_btn = st.columns([3, 1])
        with col_lac: adc_lac = st.number_input("Lactate Probe ADC", value=800.0, step=10.0)
        with col_lac_btn:
            st.write("")
            if st.button("📡 Fetch", key="fetch_lac"):
                val = read_hardware_signal()
                if val is not None: st.session_state['temp_lac'] = val

        # Pyruvate 输入
        col_pyr, col_pyr_btn = st.columns([3, 1])
        with col_pyr: adc_pyr = st.number_input("Pyruvate Probe ADC", value=300.0, step=10.0)
        with col_pyr_btn:
            st.write("")
            if st.button("📡 Fetch", key="fetch_pyr"):
                val = read_hardware_signal()
                if val is not None: st.session_state['temp_pyr'] = val

        if st.button("💾 Record & Diagnose", type="primary"):
            # 计算浓度
            c_lac = max(0, (adc_lac - lac_int) / lac_slope)
            c_pyr = max(0, (adc_pyr - pyr_int) / pyr_slope)
            
            # 判定
            if c_lac >= 5.0 and c_pyr >= 200: status, color = "High Cancer Risk", "#B91C1C"
            elif c_lac >= 5.0 and c_pyr < 200: status, color = "Inflammation", "#A86A1A"
            elif c_lac < 5.0 and c_pyr >= 200: status, color = "High Pyruvate", "#5A4A9A"
            else: status, color = "Normal", "#2C6E4A"
            
            # 存入记录
            record = {
                "Sample ID": sample_id,
                "Lac ADC": adc_lac,
                "Pyr ADC": adc_pyr,
                "Lactate (mM)": round(c_lac, 2),
                "Pyruvate (μM)": round(c_pyr, 1),
                "Status": status,
                "Color": color
            }
            st.session_state['history'].append(record)
            st.session_state['current_sample'] = record
            st.rerun()

        # 模拟终端输出
        st.markdown("### 💻 Serial Monitor (Raw Output)")
        terminal_content = ""
        for rec in st.session_state['history'][-4:]: 
            terminal_content += f"> {rec['Sample ID']} | Lac:{rec['Lac ADC']} | Pyr:{rec['Pyr ADC']} | Status:{rec['Status']}<br>"
        if not terminal_content: terminal_content = "Waiting for data..."
        
        st.markdown(f'<div class="terminal-box">{terminal_content}</div>', unsafe_allow_html=True)
        
        # 历史数据表格
        st.markdown("### 📋 Recorded Samples")
        if st.session_state['history']:
            df = pd.DataFrame(st.session_state['history']).drop(columns=['Color'])
            st.dataframe(df, use_container_width=True, hide_index=True)
            if st.button("Clear All Data"):
                st.session_state['history'] = []
                st.session_state['current_sample'] = None
                st.rerun()
        else:
            st.info("No data recorded yet.")


    # === 右侧：诊断结果与象限图 ===
    with col_right:
        if st.session_state['current_sample']:
            res = st.session_state['current_sample']
            
            # 诊断结果卡片
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: {res['Color']};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <div>
                        <div class="metric-label" style="color: #0068c9;">Lactate Probe</div>
                        <div class="metric-value" style="color: #0068c9;">{res['Lactate (mM)']} <span style="font-size:16px; font-weight:normal;">mM</span></div>
                    </div>
                    <div style="text-align: right;">
                        <div class="metric-label" style="color: #ff4b4b;">Pyruvate Probe</div>
                        <div class="metric-value" style="color: #ff4b4b;">{res['Pyruvate (μM)']} <span style="font-size:16px; font-weight:normal;">μM</span></div>
                    </div>
                </div>
                <hr style="margin: 15px 0; border-top: 1px solid #eee;">
                <div class="metric-label">Risk Classification</div>
                <div class="risk-text" style="color: {res['Color']};">{res['Status']}</div>
            </div>
            """, unsafe_allow_html=True)

            # 画图
            st.markdown("### 📊 Metabolic Fingerprint Quadrant")
            fig = go.Figure()
            fig.add_shape(type="rect", x0=0, y0=0, x1=200, y1=5, fillcolor="#bfe3c8", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=0, y0=5, x1=200, y1=30, fillcolor="#f6d9a8", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=200, y0=5, x1=800, y1=30, fillcolor="#e9b8d4", opacity=0.4, line_width=0)
            fig.add_shape(type="rect", x0=200, y0=0, x1=800, y1=5, fillcolor="#c9c4e6", opacity=0.4, line_width=0)
            fig.add_shape(type="line", x0=200, y0=0, x1=200, y1=30, line=dict(color="#6A3AB2", width=2, dash="dash"))
            fig.add_shape(type="line", x0=0, y0=5, x1=800, y1=5, line=dict(color="#6A3AB2", width=2, dash="dash"))
            
            # 画所有历史点
            for h in st.session_state['history']:
                is_current = (h['Sample ID'] == res['Sample ID'])
                fig.add_trace(go.Scatter(
                    x=[min(h['Pyruvate (μM)'], 800)], y=[min(h['Lactate (mM)'], 30)],
                    mode='markers',
                    marker=dict(size=18 if is_current else 10, color=h['Color'], line=dict(width=2, color='white' if is_current else 'gray')),
                    hoverinfo='text', text=[f"{h['Sample ID']}"], showlegend=False
                ))

            fig.update_layout(
                xaxis_title="Pyruvate Concentration (μM)", yaxis_title="Lactate Concentration (mM)",
                xaxis=dict(range=[0, 800], showgrid=False), yaxis=dict(range=[0, 30], showgrid=False),
                height=400, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please record a sample on the left to view the diagnosis.")
