import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.stats import linregress
import time
import re

# 尝试导入串口库（用于本地连接硬件）
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

# 注入自定义 CSS 美化卡片
st.markdown("""
<style>
    /* 指标卡片样式 */
    .metric-card {
        background-color: white;
        padding: 24px 30px;
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border-left: 8px solid #ccc;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .metric-value { font-size: 42px; font-weight: 800; line-height: 1.1; }
    .metric-label { font-size: 14px; color: #666; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;}
    .risk-text { font-size: 28px; font-weight: 800; margin-top: 12px;}
    .note-text { font-size: 16px; color: #555; margin-top: 12px; line-height: 1.6;}
    
    /* 按钮美化 */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Rapid Diagnostic Interface")
st.markdown("**Hardware:** Dual-Probe Detection | **Sensors:** L4 (Lactate) & P2 (Pyruvate)")

# ==========================================
# 2. 侧边栏：硬件连接与阈值说明
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
        st.info("🔒 Cloud Mode: Serial ports are disabled. Run locally to connect hardware.")
        st.session_state['serial_port'] = None

    st.divider()
    st.markdown("**Clinical Thresholds:**")
    st.markdown("- Lactate (L4): `5.0 mM`\n- Pyruvate (P2): `200 μM`")
    st.markdown("""
    **Quadrant Interpretation:**
    * 🟢 Normal: Both < Thresholds
    * 🟡 Inflammation: Lac↑, Pyr normal
    * 🔴 High Cancer: Both↑ (Warburg)
    * 🟣 High Pyruvate: Pyr↑, Lac normal
    """)

# --- 串口读取核心函数 ---
def read_hardware_signal():
    port = st.session_state.get('serial_port')
    baud = st.session_state.get('baud_rate', 9600)
    if not port:
        st.error("No port selected.")
        return None
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.1)
        ser.reset_input_buffer()
        line = ser.readline().decode('utf-8').strip()
        ser.close()
        if not line:
            st.warning("No data received from hardware.")
            return None
        # 提取字符串中的数字
        match = re.search(r"[-+]?\d*\.\d+|\d+", line)
        if match:
            return float(match.group())
        else:
            st.error(f"Could not parse data: {line}")
            return None
    except Exception as e:
        st.error(f"Serial Read Error: {e}")
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
    
    # 左侧：L4 校准
    with col1:
        st.subheader("L4 Protein (Lactate)")
        l4_x = st.text_input("Lactate Standards (mM)", value="0.0, 1.0, 2.0, 5.0, 10.0")
        l4_y = st.text_input("L4 ADC Signals", value="50.1, 128.4, 255.3, 605.7, 1210.2")
        if st.button("Run L4 Calibration", type="primary"):
            try:
                xd = [float(i) for i in l4_x.split(',')]
                yd = [float(i) for i in l4_y.split(',')]
                res = linregress(xd, yd)
                st.session_state['l4_slope'] = res.slope
                st.session_state['l4_int'] = res.intercept
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Data', marker=dict(color='#0068c9', size=10)))
                fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='black', dash='dash')))
                fig.update_layout(title="L4 Standard Curve", xaxis_title="Conc (mM)", yaxis_title="ADC", height=280, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")
            except Exception as e:
                st.error(f"Error parsing inputs.")

    # 右侧：P2 校准
    with col2:
        st.subheader("P2 Protein (Pyruvate)")
        p2_x = st.text_input("Pyruvate Standards (μM)", value="0, 100, 200, 500, 1000")
        p2_y = st.text_input("P2 ADC Signals", value="45.2, 152.8, 310.5, 782.1, 1550.8")
        if st.button("Run P2 Calibration", type="primary"):
            try:
                xd = [float(i) for i in p2_x.split(',')]
                yd = [float(i) for i in p2_y.split(',')]
                res = linregress(xd, yd)
                st.session_state['p2_slope'] = res.slope
                st.session_state['p2_int'] = res.intercept
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xd, y=yd, mode='markers', name='Data', marker=dict(color='#ff4b4b', size=10)))
                fig.add_trace(go.Scatter(x=xd, y=res.intercept + res.slope * np.array(xd), mode='lines', name='Fit', line=dict(color='black', dash='dash')))
                fig.update_layout(title="P2 Standard Curve", xaxis_title="Conc (μM)", yaxis_title="ADC", height=280, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"y = {res.slope:.2f}x + {res.intercept:.2f} | R² = {res.rvalue**2:.4f}")
            except Exception as e:
                st.error(f"Error parsing inputs.")

# ------------------------------------------
# Tab 2: 联合诊断
# ------------------------------------------
with tab2:
    # 检查是否已完成校准，未完成则使用默认模拟值
    if 'l4_slope' not in st.session_state or 'p2_slope' not in st.session_state:
        st.warning("⚠️ Please complete calibration for both L4 and P2 in Tab 1 first. (Using simulated calibration for preview).")
        l4_slope, l4_int = 115.0, 50.0
        p2_slope, p2_int = 1.5, 40.0
    else:
        l4_slope = st.session_state['l4_slope']
        l4_int = st.session_state['l4_int']
        p2_slope = st.session_state['p2_slope']
        p2_int = st.session_state['p2_int']

    st.header("Joint Diagnostic Interface")
    col_input, col_plot = st.columns([1, 2], gap="large")
    
    with col_input:
        st.markdown("### 🧪 Sample Inputs")
        
        # L4 ADC 输入与读取
        col_l4_in1, col_l4_in2 = st.columns([3, 1])
        with col_l4_in1:
            adc_lac = st.number_input("Lactate Channel (L4) ADC", value=800.0, step=10.0)
        with col_l4_in2:
            st.write("")
            if st.button("📡 Fetch", key="fetch_l4"):
                val = read_hardware_signal()
                if val is not None:
                    st.session_state['adc_lac_val'] = val
                    st.rerun()
                    
        # P2 ADC 输入与读取
        col_p2_in1, col_p2_in2 = st.columns([3, 1])
        with col_p2_in1:
            adc_pyr = st.number_input("Pyruvate Channel (P2) ADC", value=300.0, step=10.0)
        with col_p2_in2:
            st.write("")
            if st.button("📡 Fetch", key="fetch_p2"):
                val = read_hardware_signal()
                if val is not None:
                    st.session_state['adc_pyr_val'] = val
                    st.rerun()

        # 实时计算浓度
        conc_lac = max(0, (adc_lac - l4_int) / l4_slope)
        conc_pyr = max(0, (adc_pyr - p2_int) / p2_slope)

        st.markdown("---")
        st.markdown("### 🩺 Diagnostic Result")
        
        # 四象限判定逻辑
        if conc_lac >= 5.0 and conc_pyr >= 200:
            status, color = "High Cancer Risk", "#B91C1C"
            note = "Warburg effect signature detected. Both biomarkers are synchronously elevated."
        elif conc_lac >= 5.0 and conc_pyr < 200:
            status, color = "Inflammation / Ischemia", "#A86A1A"
            note = "Lactate is elevated but pyruvate remains normal. Likely benign."
        elif conc_lac < 5.0 and conc_pyr >= 200:
            status, color = "High Pyruvate", "#5A4A9A"
            note = "Pyruvate is elevated but lactate is normal. Not typical of Warburg effect."
        else:
            status, color = "Normal", "#2C6E4A"
            note = "Both biomarkers are within normal ranges."

        st.markdown(f"""
        <div class="metric-card" style="border-left-color: {color};">
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <div>
                    <div class="metric-label" style="color: #0068c9;">Lactate (L4)</div>
                    <div class="metric-value" style="color: #0068c9;">{conc_lac:.2f} <span style="font-size:16px; font-weight:normal;">mM</span></div>
                </div>
                <div style="text-align: right;">
                    <div class="metric-label" style="color: #ff4b4b;">Pyruvate (P2)</div>
                    <div class="metric-value" style="color: #ff4b4b;">{conc_pyr:.0f} <span style="font-size:16px; font-weight:normal;">μM</span></div>
                </div>
            </div>
            <hr style="margin: 15px 0; border-top: 1px solid #eee;">
            <div class="metric-label">Risk Classification</div>
            <div class="risk-text" style="color: {color};">{status}</div>
            <div class="note-text">{note}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_plot:
        st.markdown("### 📊 Metabolic Fingerprint Quadrant")
        fig = go.Figure()

        # 画四个象限的背景色
        fig.add_shape(type="rect", x0=0, y0=0, x1=200, y1=5, fillcolor="#bfe3c8", opacity=0.4, line_width=0)
        fig.add_shape(type="rect", x0=0, y0=5, x1=200, y1=30, fillcolor="#f6d9a8", opacity=0.4, line_width=0)
        fig.add_shape(type="rect", x0=200, y0=5, x1=800, y1=30, fillcolor="#e9b8d4", opacity=0.4, line_width=0)
        fig.add_shape(type="rect", x0=200, y0=0, x1=800, y1=5, fillcolor="#c9c4e6", opacity=0.4, line_width=0)
        
        # 画阈值虚线
        fig.add_shape(type="line", x0=200, y0=0, x1=200, y1=30, line=dict(color="#6A3AB2", width=2, dash="dash"))
        fig.add_shape(type="line", x0=0, y0=5, x1=800, y1=5, line=dict(color="#6A3AB2", width=2, dash="dash"))
        
        # 添加象限文字标签
        fig.add_annotation(x=100, y=2.5, text="Normal", showarrow=False, font=dict(color="#2C6E4A", size=14, weight="bold"))
        fig.add_annotation(x=100, y=15, text="Inflammation", showarrow=False, font=dict(color="#A86A1A", size=14, weight="bold"))
        fig.add_annotation(x=500, y=15, text="High Cancer Risk", showarrow=False, font=dict(color="#B91C1C", size=16, weight="bold"))
        fig.add_annotation(x=500, y=2.5, text="High Pyruvate", showarrow=False, font=dict(color="#5A4A9A", size=14, weight="bold"))

        # 绘制当前样本点
        fig.add_trace(go.Scatter(
            x=[min(conc_pyr, 800)], 
            y=[min(conc_lac, 30)],
            mode='markers',
            marker=dict(size=18, color=color, line=dict(width=3, color='white'), symbol='circle'),
            hoverinfo='text',
            text=[f"Lac: {conc_lac:.1f} mM<br>Pyr: {conc_pyr:.0f} μM"]
        ))

        fig.update_layout(
            xaxis_title="Pyruvate Concentration (μM)",
            yaxis_title="Lactate Concentration (mM)",
            xaxis=dict(range=[0, 800], showgrid=False),
            yaxis=dict(range=[0, 30], showgrid=False),
            height=500,
            margin=dict(l=0, r=0, t=10, b=0),
            showlegend=False,
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)
