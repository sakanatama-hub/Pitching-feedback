import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.title("投手データフィードバック")

# ファイルアップローダー
uploaded_file = st.file_uploader("CSVファイルをアップロードしてください", type='csv')

if uploaded_file is not None:
    # 5行目からデータが始まるため skiprows=4
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # 【重要】数値変換の処理を追加
    # errors='coerce' を指定することで、"-" などの文字を自動的に欠損値(NaN)に変換し、エラーを防ぎます
    df['Velocity'] = pd.to_numeric(df['Velocity'], errors='coerce')
    df['Total Spin'] = pd.to_numeric(df['Total Spin'], errors='coerce')
    df['VB (trajectory)'] = pd.to_numeric(df['VB (trajectory)'], errors='coerce')
    df['HB (trajectory)'] = pd.to_numeric(df['HB (trajectory)'], errors='coerce')

    # --- 1. 基本統計量の算出 (エラー回避済み) ---
    st.subheader("📊 球種別統計 (平均・最大)")
    # numeric_only=True を指定して数値列のみ計算
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).round(1)
    
    # カラム名をわかりやすく整理
    stats.columns = ['平均球速', '最大球速', '平均回転数', '最大回転数']
    st.dataframe(stats)

    # --- 2. 変化量グラフ ---
    st.subheader("⚾ 変化量チャート (Movement Profile)")
    # 変化量の散布図
    fig_mov = px.scatter(df, x='HB (trajectory)', y='VB (trajectory)', 
                         color='Pitch Type',
                         hover_name='Pitch Type',
                         labels={'HB (trajectory)': '横の変化量 (cm)', 'VB (trajectory)': '縦の変化量 (cm)'},
                         title="縦横の変化量")
    
    # グラフの中心線を描画
    fig_mov.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_mov.add_vline(x=0, line_dash="dash", line_color="gray")
    
    # グラフの範囲をデータに合わせる（例：±60cm程度）
    fig_mov.update_xaxes(range=[-60, 60])
    fig_mov.update_yaxes(range=[-60, 60])
    
    st.plotly_chart(fig_mov)

    # --- 3. 回転軸の視覚化 (最新の1球を表示) ---
    st.subheader("🔄 回転軸の視覚化")
    
    # Spin Direction がある行だけ抽出
    valid_spin_df = df.dropna(subset=['Spin Direction'])
    if not valid_spin_df.empty:
        latest_pitch = valid_spin_df.iloc[0]
        spin_dir = latest_pitch['Spin Direction']
        p_type = latest_pitch['Pitch Type']

        def draw_ball_with_axis(spin_str):
            try:
                # "12:52" -> 時、分に分解
                hour, minute = map(int, spin_str.split(':'))
                # 角度計算 (12時=0度, 3時=90度)
                angle_deg = (hour % 12 + minute / 60) * 30
                angle_rad = np.deg2rad(angle_deg)
                
                # ボールの3D球体データ
                u, v = np.mgrid[0:2*np.pi:30j, 0:np.pi:15j]
                x = np.cos(u)*np.sin(v)
                y = np.sin(u)*np.sin(v)
                z = np.cos(v)
                
                fig = go.Figure()
                # ボールの表面
                fig.add_trace(go.Surface(x=x, y=y, z=z, colorscale='Greys', opacity=0.3, showscale=False))
                
                # 回転軸（ベクトル）
                vx = np.sin(angle_rad)
                vy = 0 # 奥行きは簡易化のため0
                vz = np.cos(angle_rad)
                
                # 赤い矢印を軸として表示
                fig.add_trace(go.Scatter3d(x=[-vx, vx], y=[0, 0], z=[-vz, vz],
                                         mode='lines+markers',
                                         line=dict(color='red', width=12),
                                         name="Spin Axis"))
                
                fig.update_layout(
                    scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                               aspectmode='cube'),
                    title=f"直近の投球: {p_type} (軸の向き: {spin_str})",
                    margin=dict(l=0, r=0, b=0, t=40)
                )
                return fig
            except:
                return None

        fig_spin = draw_ball_with_axis(spin_dir)
        if fig_spin:
            st.plotly_chart(fig_spin)
            st.write("※赤い線が回転軸です。12:00（真上）に近いほどバックスピンが強くなります。")

else:
    st.info("GitHubからダウンロードしたCSVファイルをアップロードしてください。")
