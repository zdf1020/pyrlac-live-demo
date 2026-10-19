import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
import time

# ==========================================
# 1. 页面配置与全局样式
# ==========================================
st.set_page_config(
    page_title="PyrLac Glow | Diagnostic Interface",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS 美化卡片
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .metric-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.08);
        border-left: 6px solid #6A3AB2;
        margin-bottom: 20px;
    }
    .big-number { font-size: 42px; font-weight: 800; color: #2f2a3d; line-height: 1.2; }
    .status-pass { color: #28a745; font-weight: bold; font-size: 18px; }
    .status-fail { color: #dc3545; font-weight: bold; font-size: 18px; }
    .risk-low { color: #28a745; font-weight: bold; font-size: 24px; }
    .risk-med { color: #ffc107; font-weight: bold; font-size: 24px; }
    .risk-high { color: #dc3545; font-weight: bold; font-size: 24px; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 PyrLac Glow - Rapid Cancer Risk Pre-screening")
st.markdown("**Next-Generation Metabolic Profiling** | Target: Dual-fluorescence biomarkers (Lactate & Pyruvate)")

# ==========================================
# 2. 侧边栏：系统设置与参数
# ==========================================
with st.sidebar:
    st.image("https://static.igem.wiki/teams/6263/wiki/layout/1-1-1.avif", width=120) # 吉祥物
    st.header("⚙️ Hardware & Assay Settings")
    
    # 蛋白选择
    target = st.selectbox(
        "Select Active Sensor Protein", 
        ["L2 Protein (Lactate)", "P4 Protein (Pyruvate)"]
    )
    
    if "Lactate" in target:
        biomarker = "Lactate"
        unit = "mM"
        normal_range = (0.5, 2.2) # 正常生理乳酸范围
        default_x = [0.0, 1.0, 2.0, 5.0, 10.0]
        default_y = [50.1, 128.4, 255.3, 605.7, 1210.2]
        color = "#0068c9"
    else:
        biomarker = "Pyruvate"
        unit = "mM"
        normal_range = (0.05, 0.2) # 正常生理丙酮酸范围
        default_x = [0.0, 0.1, 0.2, 0.5, 1.0]
        default_y = [45.2, 152.8, 310.5, 782.1, 1550.8]
        color = "#ff4b4b"

    st.info(f"**Normal Reference Range:**\n{normal_range[0]} - {normal_range[1]} {unit}")
    
    st.divider()
    st.write("**System Status:**")
    st.success("Optical Module: Online")
    st.success("Rotation Servo: Ready")

# ==========================================
# 3. 核心功能区：Tabs
# ==========================================
tab_demo, tab_cal, tab_measure = st.tabs(["🚀 Quick Live Demo", "📈 1. Calibration", "🧪 2. Sample Measurement"])

# ------------------------------------------
# Tab 0: 一键演示模式 (方便现场答辩)
# ------------------------------------------
with tab_demo:
    st.header("Live Demonstration Mode")
    st.write("Use this button to instantly populate mock data for a quick demonstration without typing.")
    
    if st.button("⚡ Auto-fill Demo Data & Run", type="primary"):
        # 修复：这里算好 R2 并存入 session_state
        res = linregress(default_x, default_y)
        st.session_state['slope'] = res.slope
        st.session_state['intercept'] = res.intercept
        st.session_state['r2'] = res.rvalue ** 2  # <--- 修复了这里
        st.session_state['calibrated'] = True
        st.session_state['demo_mode'] = True
        st.session_state['target'] = target
        
        # 模拟生成一个高风险的样本 ADC 值
        mock_adc = (normal_range[1] * 1.8 * st.session_state['slope']) + st.session_state['intercept']
        st.session_state['last_adc'] = mock_adc
        
        st.success("✅ Demo data loaded! Please go to **Tab 2** to see the diagnostic result.")

# ------------------------------------------
# Tab 1: 校准模块
# ------------------------------------------
with tab_cal:
    st.header(f"Calibration Curve for {biomarker}")
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.write("**Input Standard Data**")
        x_input = st.text_input(f"Standard Concentrations ({unit})", value=", ".join(map(str, default_x)))
        y_input = st.text_input("ADC Signal Readings", value=", ".join(map(str, default_y)))
        
        if st.button("Run Calibration & Check QC", type="secondary"):
            with st.spinner("Fitting data..."):
                time.sleep(0.5)
                try:
                    x_data = [float(i.strip()) for i in x_input.split(",") if i.strip()]
                    y_data = [float(i.strip()) for i in y_input.split(",") if i.strip()]
                    
                    if len(x_data) == len(y_data) and len(x_data) >= 2:
                        slope, intercept, r_val, _, _ = linregress(x_data, y_data)
                        st.session_state.update({
                            'slope': slope, 'intercept': intercept, 
                            'r2': r_val**2, 'calibrated': True, 'target': target
                        })
                        st.session_state.pop('last_adc', None) # 清除旧结果
                    else:
                        st.error("Please ensure X and Y arrays have the same length.")
                except Exception as e:
                    st.error(f"Data parsing error: {e}")

    with col2:
        st.write("**Calibration Quality Control**")
        # 这里安全获取，防止报错
        if st.session_state.get('calibrated', False) and st.session_state.get('target') == target:
            # 画图
            x_data = [float(i.strip()) for i in x_input.split(",")]
            y_data = [float(i.strip()) for i in y_input.split(",")]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='markers', name='Standards', 
                                     marker=dict(size=12, color=color, line=dict(width=2, color='white'))))
            
            line_x = np.array([min(x_data), max(x_data)])
            line_y = st.session_state['slope'] * line_x + st.session_state['intercept']
            fig.add_trace(go.Scatter(x=line_x, y=line_y, mode='lines', name='Fit', line=dict(color='#333', width=2, dash='dash')))
            
            fig.update_layout(template="plotly_white", height=350, margin=dict(l=0, r=0, t=20, b=0),
                              xaxis_title=f"Concentration ({unit})", yaxis_title="ADC Signal")
            st.plotly_chart(fig, use_container_width=True)
            
            # QC 面板
            r2 = st.session_state.get('r2', 0) # 安全获取
            if r2 > 0.98:
                st.markdown(f"**Equation:** y = `{st.session_state['slope']:.2f}` x + `{st.session_state['intercept']:.2f}` | **R²:** <span class='status-pass'>{r2:.4f} (PASS)</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**Equation:** y = `{st.session_state['slope']:.2f}` x + `{st.session_state['intercept']:.2f}` | **R²:** <span class='status-fail'>{r2:.4f} (FAIL)</span>", unsafe_allow_html=True)
                st.warning("Low linearity. Please check sample preparation.")
        else:
            st.info("Awaiting calibration data...")

# ------------------------------------------
# Tab 2: 测量与诊断
# ------------------------------------------
with tab_measure:
    st.header("Sample Analysis & Risk Stratification")
    
    if not st.session_state.get('calibrated', False) or st.session_state.get('target') != target:
        st.warning("⚠️ Please complete calibration first or check if the active protein matches.")
    else:
        col_in, col_out = st.columns([1, 1.2])
        
        with col_in:
            st.write("**Input Unknown Sample**")
            # 检查是否有 Demo 模式的数据
            default_adc = st.session_state.get('last_adc', 800.0) if st.session_state.get('demo_mode') else 800.0
            
            sample_adc = st.number_input("Raw ADC Signal", value=float(default_adc), step=5.0)
            
            if st.button("🔍 Analyze & Diagnose", type="primary"):
                conc = max(0, (sample_adc - st.session_state['intercept']) / st.session_state['slope'])
                
                # 风险逻辑
                if conc <= normal_range[1]:
                    risk, cls = "Normal / Low Risk", "risk-low"
                    note = "Metabolite level is within the normal physiological range."
                elif conc <= normal_range[1] * 1.5:
                    risk, cls = "Moderate Risk", "risk-med"
                    note = "Slightly elevated. Suggest follow-up physical examination."
                else:
                    risk, cls = "High Risk", "risk-high"
                    note = "Significantly elevated. Strongly recommend immediate clinical consultation."
                
                # 存入历史
                if 'history' not in st.session_state: st.session_state['history'] = []
                st.session_state['history'].append({
                    "Biomarker": biomarker, "ADC": sample_adc, f"Conc. ({unit})": round(conc, 3), "Result": risk
                })
                
                # 显示结果卡片
                with col_out:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4 style="margin-top:0; color:#666;">Detected {biomarker}</h4>
                        <div class="big-number">{conc:.2f} <span style="font-size: 20px; color:#999;">{unit}</span></div>
                        <hr style="margin: 15px 0;">
                        <h4 style="margin-top:0; color:#666;">Risk Classification</h4>
                        <div class="{cls}">{risk}</div>
                        <p style="margin-top:10px; font-size: 14px; color:#555;">{note}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.toast("Data recorded successfully!")

# ==========================================
# 4. 底部：历史数据与导出
# ==========================================
with st.expander("📂 View & Export Measurement History"):
    if 'history' in st.session_state and st.session_state['history']:
        df = pd.DataFrame(st.session_state['history'])
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name='pyrlac_results.csv',
            mime='text/csv',
            type="primary"
        )
        if st.button("Clear History"):
            st.session_state['history'] = []
            st.rerun()
    else:
        st.info("No records yet. Analyze a sample to generate data.")
