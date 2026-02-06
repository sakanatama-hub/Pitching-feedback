import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.title("投手データフィードバック")

# ファイルアップローダーを設置
uploaded_file = st.file_uploader("RapsodoなどのCSVファイルをアップロードしてください", type='csv')

if uploaded_file is not None:
    # アップロードされたファイルを読み込む (ヘッダー5行目から)
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # --- データ集計 ---
    st.subheader("📊 球種別統計")
    # Velocity(球速)を数値に変換（念のため）
    df['Velocity'] = pd.to_numeric(df['Velocity'], errors='coerce')
    stats = df.groupby('Pitch Type').agg({
        'Velocity': ['mean', 'max'],
        'Total Spin': ['mean', 'max']
    }).round(1)
    st.dataframe(stats)

    # --- 変化量グラフ ---
    st.subheader("⚾ 変化量 (Movement Profile)")
    fig_mov = px.scatter(df, x='HB (trajectory)', y='VB (trajectory)', 
                         color='Pitch Type',
                         labels={'HB (trajectory)': '横の変化 (cm)', 'VB (trajectory)': '縦の変化 (cm)'})
    fig_mov.add_hline(y=0, line_dash="dash")
    fig_mov.add_vline(x=0, line_dash="dash")
    st.plotly_chart(fig_mov)

    # --- 回転軸の視覚化 (1つ目のデータで例示) ---
    st.subheader("🔄 回転軸イメージ (最新の投球)")
    latest_pitch = df.iloc[0]
    spin_dir = latest_pitch['Spin Direction']
    pitch_type = latest_pitch['Pitch Type']
    
    def plot_ball_spin_logic(spin_str):
        try:
            hour, minute = map(int, spin_str.split(':'))
            # 12時を0度、時計回りに角度計算
            angle_deg = (hour % 12 + minute / 60) * 30
            angle_rad = np.deg2rad(angle_deg)
            
            # ボールの球体描画
            u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
            x, y, z = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
            fig = go.Figure(data=[go.Surface(x=x, y=y, z=z, colorscale='Greys', opacity=0.4, showscale=False)])
            
            # 回転軸ベクトル (簡易化のため2D的な向きを3Dに投影)
            vx, vy, vz = np.sin(angle_rad), 0, np.cos(angle_rad)
            fig.add_trace(go.Scatter3d(x=[0, vx], y=[0, vy], z=[0, vz], mode='lines+markers',
                                     line=dict(color='red', width=10), name=f"Axis: {spin_str}"))
            fig.update_layout(scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False))
            return fig
        except:
            return None

    fig_spin = plot_ball_spin_logic(spin_dir)
    if fig_spin:
        st.write(f"球種: {pitch_type} / 回転方向: {spin_dir}")
        st.plotly_chart(fig_spin)

else:
    st.info("CSVファイルをアップロードしてください。")
