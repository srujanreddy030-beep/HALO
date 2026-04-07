from pathlib import Path
import time as _time

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

import shutil

from utils.alerts import get_recent_alert_log, is_email_configured, is_telegram_configured, send_email_alert
from utils.database import delete_all_incidents, fetch_recent, stats, init_db, set_active_user
from utils.auth import authenticate_user, create_user


ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "worker_safety.db")
init_db(DB_PATH)  # Ensure users table is ready
LATEST_FRAME_PATH = ROOT / "artifacts" / "latest_frame.jpg"


st.set_page_config(page_title="HALO — Worker Safety", layout="wide", page_icon="🛡️")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Orbitron:wght@500;700;900&display=swap');

:root{
  --bg0:        #060D1A;
  --bg1:        #080F20;
  --bg2:        #0A1428;
  --card:       rgba(10,22,48,0.88);
  --card2:      rgba(14,28,55,0.92);
  --panel:      #0B1628;
  --stroke:     rgba(0,212,255,0.14);
  --stroke2:    rgba(43,108,255,0.18);
  --text:       #D8E6F5;
  --muted:      #6B80A0;
  --accent:     #2B6CFF;
  --accent2:    #00D4FF;
  --red:        #FF2D55;
  --amber:      #FF9500;
  --yellow:     #FFCC00;
  --green:      #34C759;
  --shadow:     0 8px 32px rgba(0,0,0,0.50);
  --shadow2:    0 16px 48px rgba(0,0,0,0.65);
  --glow-blue:  0 0 20px rgba(43,108,255,0.28);
  --glow-cyan:  0 0 20px rgba(0,212,255,0.22);
}

body, .stApp {
  background: linear-gradient(135deg, #050B14 0%, #0A1430 100%) !important;
  color: var(--text) !important;
  font-family: 'Inter', sans-serif !important;
  overflow-x: hidden;
}

/* Fluid Glassmorphism Background Orbs */
.stApp::before {
  content: ''; position: fixed; top: -10vw; left: -10vw; width: 60vw; height: 60vw;
  background: radial-gradient(circle, rgba(138, 43, 226, 0.35) 0%, transparent 65%);
  filter: blur(80px); z-index: -1; animation: floatOrb1 20s infinite alternate cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: none;
}
.stApp::after {
  content: ''; position: fixed; bottom: -10vw; right: -5vw; width: 70vw; height: 70vw;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.30) 0%, transparent 65%);
  filter: blur(80px); z-index: -1; animation: floatOrb2 25s infinite alternate cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: none;
}
@keyframes floatOrb1 { 
  0% { transform: translate(0, 0) scale(1); } 
  100% { transform: translate(20vw, 15vh) scale(1.3); } 
}
@keyframes floatOrb2 { 
  0% { transform: translate(0, 0) scale(1); } 
  100% { transform: translate(-15vw, -20vh) scale(1.1); } 
}

/* Animated Cursor Robot */
#cursor-robot {
  position: fixed;
  width: 40px;
  height: 40px;
  pointer-events: none;
  z-index: 10000;
  transition: transform 0.1s ease-out;
  transform-origin: center center;
}
.bot-body {
  fill: #0D1E3A;
  stroke: var(--accent2);
  stroke-width: 2;
  filter: drop-shadow(0 4px 14px rgba(0,212,255,0.45));
}
.bot-eye {
  fill: var(--accent2);
  transition: transform 0.1s ease-out;
}
.bot-antenna {
  stroke: var(--accent);
  stroke-width: 2;
  stroke-linecap: round;
}
.bot-glow {
  fill: var(--accent2);
  animation: pulseAntenna 1.5s infinite;
}
@keyframes pulseAntenna {
  0%, 100% { filter: drop-shadow(0 0 2px var(--accent2)) brightness(1); }
  50% { filter: drop-shadow(0 0 8px var(--accent2)) brightness(1.5); }
}

/* Sidebar Dark Theme */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #04080F 0%, #060C1A 100%) !important;
  border-right: 1px solid rgba(0,212,255,0.12) !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] div, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] li {
  color: #8A9DBE !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #00D4FF !important;
  font-family: 'Orbitron', sans-serif !important;
  border-bottom: 1px solid rgba(0,212,255,0.12);
  padding-bottom: 8px;
}
[data-testid="stSidebar"] hr {
  border-color: rgba(0,212,255,0.10) !important;
}
[data-testid="stSidebar"] b, [data-testid="stSidebar"] strong {
  color: #C8D8F0 !important;
}

/* Flash Transition */
.dashboard-flash {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background: radial-gradient(circle, rgba(0,212,255,0.18) 0%, rgba(6,13,26,0) 70%);
  z-index: 9999; pointer-events: none;
  animation: flashOut 1s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}
@keyframes flashOut {
  0%   { opacity: 1; transform: scale(0.95); }
  100% { opacity: 0; transform: scale(1.1); }
}

h1, h2, h3, .halo-title {
  font-family: 'Orbitron', sans-serif !important;
}

section.main > div { padding-top: 1.1rem; }

/* Dashboard Landing */
.landing-card{
  border: 1px solid rgba(255,255,255,0.1);
  border-top: 1px solid rgba(255,255,255,0.2);
  background: linear-gradient(135deg, rgba(8,16,36,0.25), rgba(10,22,50,0.1));
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-radius: 22px;
  box-shadow: var(--shadow2), 0 0 60px rgba(43,108,255,0.10), inset 0 0 20px rgba(0,212,255,0.05);
  position: relative;
  overflow: hidden;
  height: 260px;
}
.landing-content {
  position: absolute; top: 0; left: 0; bottom: 0; width: 60%;
  padding: 40px 36px; z-index: 2;
  background: linear-gradient(90deg, rgba(6,13,26,0.98) 0%, rgba(8,16,36,0.80) 65%, transparent 100%);
  display: flex; flex-direction: column; justify-content: center;
}
.halo-word{
  font-size: 72px; font-weight: 900; letter-spacing: 6px; margin: 0;
  background: linear-gradient(135deg, #FFFFFF 0%, #00D4FF 50%, #2B6CFF 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 0 20px rgba(0,212,255,0.50));
  position: relative; display: inline-block;
  animation: floatBob 4s ease-in-out infinite;
}
.halo-word::after {
  content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(0,212,255,0.35), transparent);
  transform: skewX(-20deg); animation: flareSweep 5s infinite;
}
@keyframes floatBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes flareSweep { 0%, 60% { left: -100%; } 80%, 100% { left: 200%; } }

.landing-sub{
  color: var(--muted); font-size: 14px; margin-top: 12px; line-height: 1.7; max-width: 420px;
}

/* Header */
.halo-header{
  border: 1px solid rgba(255,255,255,0.1);
  border-top: 1px solid rgba(255,255,255,0.15);
  background: linear-gradient(135deg, rgba(8,18,40,0.25), rgba(10,22,48,0.1));
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 18px; padding: 18px 24px; margin-bottom: 14px;
  box-shadow: var(--shadow), inset 0 0 20px rgba(0,212,255,0.05);
}
.halo-title{
  font-size: 26px; font-weight: 800; margin: 0;
  background: linear-gradient(90deg, #FFFFFF, #00D4FF, #2B6CFF);
  -webkit-background-clip: text; color: transparent;
}
.halo-subtitle{ margin-top: 6px; color: var(--muted); font-size: 13px; }
.halo-badges{ margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
.badge{
  border: 1px solid rgba(0,212,255,0.18);
  background: rgba(0,212,255,0.06);
  padding: 5px 12px; border-radius: 999px; font-size: 11.5px; color: var(--muted);
  transition: all .2s ease;
}
.badge b{ color: var(--accent2); font-weight: 700; }
.badge:hover{ transform: translateY(-2px); box-shadow: var(--glow-cyan); border-color: rgba(0,212,255,0.35); color: var(--text); }

/* KPI Cards 3D */
.kpi {
  perspective: 1000px; height: 110px; margin-bottom: 10px;
}
.kpi-inner {
  position: relative; width: 100%; height: 100%;
  transition: transform 0.6s cubic-bezier(0.4, 0.2, 0.2, 1); transform-style: preserve-3d;
  border: 1px solid rgba(255,255,255,0.08);
  border-top: 1px solid rgba(255,255,255,0.15);
  background: linear-gradient(135deg, rgba(10,22,48,0.25), rgba(8,16,36,0.1));
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 16px; box-shadow: var(--shadow); cursor: default;
}
.kpi:hover .kpi-inner { transform: rotateY(180deg) scale(1.02); box-shadow: var(--shadow2); }
.kpi.card-crit .kpi-inner { border-bottom: 2px solid var(--red); box-shadow: 0 4px 20px rgba(255,45,85,0.15); }
.kpi.card-high .kpi-inner { border-bottom: 2px solid var(--amber); box-shadow: 0 4px 20px rgba(255,149,0,0.15); }
.kpi.card-med  .kpi-inner { border-bottom: 2px solid var(--yellow); box-shadow: 0 4px 20px rgba(255,204,0,0.12); }
.kpi.card-tot  .kpi-inner { border-bottom: 2px solid var(--accent2); box-shadow: 0 4px 20px rgba(0,212,255,0.15); }
.kpi.card-crit:hover .kpi-inner { border-color: rgba(255,45,85,0.40); box-shadow: 0 14px 34px rgba(255,45,85,0.22); }
.kpi.card-high:hover .kpi-inner { border-color: rgba(255,149,0,0.40); box-shadow: 0 14px 34px rgba(255,149,0,0.22); }
.kpi.card-med:hover  .kpi-inner { border-color: rgba(255,204,0,0.40); box-shadow: 0 14px 34px rgba(255,204,0,0.18); }
.kpi.card-tot:hover  .kpi-inner { border-color: rgba(0,212,255,0.40); box-shadow: 0 14px 34px rgba(0,212,255,0.22); }
.kpi.card-crit { animation: critGlowCard 2.8s ease-in-out infinite; }
@keyframes critGlowCard { 0%,100%{ filter:none; } 50%{ filter:drop-shadow(0 0 8px rgba(255,45,85,0.25)); } }
.kpi-front, .kpi-back {
  position: absolute; width: 100%; height: 100%; backface-visibility: hidden;
  display: flex; flex-direction: column; justify-content: center; padding: 16px;
}
.kpi-back {
  transform: rotateY(180deg); align-items: center; text-align: center;
  background: linear-gradient(135deg, rgba(10,22,48,0.25), rgba(8,16,36,0.1));
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-radius: 16px; font-size: 13px; color: var(--text);
}
.kpi .label{ color: var(--muted); font-size: 11px; margin-bottom: 6px; display: flex; align-items: center; font-family: 'Orbitron', sans-serif; letter-spacing: 1.5px; }
.kpi .value{ font-size: 36px; font-weight: 800; line-height: 1.0; font-family: 'Orbitron', sans-serif; }
.kpi .value.vc { color: var(--red);    text-shadow: 0 0 16px rgba(255,45,85,0.35); }
.kpi .value.vh { color: var(--amber);  text-shadow: 0 0 16px rgba(255,149,0,0.30); }
.kpi .value.vm { color: var(--yellow); text-shadow: 0 0 16px rgba(255,204,0,0.25); }
.kpi .value.vt { color: var(--accent2);text-shadow: 0 0 16px rgba(0,212,255,0.30); }
.kpi .hint{ margin-top: 6px; font-size: 11px; color: var(--muted); }

/* Dots */
.dot{ position: relative; display:inline-block; width:10px; height:10px; border-radius:999px; margin-right:8px; }
.dot::after { content:''; position:absolute; top:0; left:0; width:100%; height:100%; border-radius:100%; }
.dot.red{ background: var(--red); box-shadow: 0 0 6px var(--red); }
.dot.red::after{ animation: pulseRed 2s infinite; }
@keyframes pulseRed { 70% { box-shadow: 0 0 0 8px rgba(225,29,72,0); } 100% { box-shadow: 0 0 0 0 rgba(225,29,72,0); } }
.dot.amber{ background: var(--amber); animation: shimmerAmber 3s infinite linear; }
@keyframes shimmerAmber { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:0.8; transform:scale(1.1); box-shadow:0 0 8px var(--amber); } }
.dot.yellow{ background: var(--yellow); border-radius:2px; transform: rotate(45deg); animation: bounceYellow 1.5s infinite; }
@keyframes bounceYellow { 0%,100%{ transform: translateY(0) rotate(45deg); } 50%{ transform: translateY(-3px) rotate(45deg); } }
.dot.green{ background: var(--green); }
.dot.green::after{ animation: pulseGreen 2.5s infinite; }
@keyframes pulseGreen { 70% { box-shadow: 0 0 0 8px rgba(16,185,129,0); } 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); } }

/* Tabs */
div[data-baseweb="tab-list"]{
  gap: 8px; padding: 6px 8px; border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.1);
  border-top: 1px solid rgba(255,255,255,0.15);
  background: linear-gradient(135deg, rgba(8,16,36,0.25), rgba(10,22,50,0.1));
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  box-shadow: var(--shadow);
}
button[data-baseweb="tab"]{
  border-radius: 10px !important; border: 1px solid rgba(0,212,255,0.12) !important;
  background: rgba(10,22,48,0.60) !important; color: var(--muted) !important;
  font-family: 'Orbitron', sans-serif !important; font-weight: 600 !important;
  font-size: 12px !important; letter-spacing: 0.5px !important;
  padding: 10px 22px !important; min-height: 42px !important; transition: all 0.22s ease;
}
button[data-baseweb="tab"]:hover{
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0,212,255,0.14); background: rgba(0,212,255,0.08) !important;
  border-color: rgba(0,212,255,0.28) !important; color: var(--accent2) !important;
}
button[data-baseweb="tab"][aria-selected="true"]{
  background: linear-gradient(135deg, #1A50CC, #2B6CFF) !important;
  border-color: rgba(43,108,255,0.50) !important; color: white !important;
  box-shadow: 0 8px 24px rgba(43,108,255,0.35); transform: translateY(-2px); position: relative;
}
button[data-baseweb="tab"][aria-selected="true"]::after {
  content: ''; position: absolute; bottom: -8px; left: 30%; right: 30%; height: 3px;
  background: var(--accent2); border-radius: 4px; box-shadow: 0 0 10px var(--accent2);
}

/* Incident Table Enhancement */
div[data-testid="stDataFrame"] {
  border: 1px solid rgba(255,255,255,0.1) !important;
  border-top: 1px solid rgba(255,255,255,0.15) !important;
  border-radius: 14px !important; overflow: hidden !important;
  box-shadow: var(--shadow), inset 0 0 20px rgba(0,212,255,0.05) !important;
  background: linear-gradient(135deg, rgba(8,16,36,0.25), rgba(10,22,50,0.1)) !important;
  backdrop-filter: blur(24px) !important;
  -webkit-backdrop-filter: blur(24px) !important;
}
div[data-testid="stDataFrame"] tr { animation: slideInLeft 0.5s ease-out backwards; }
@keyframes slideInLeft { from { opacity: 0; transform: translateX(-15px); } to { opacity: 1; transform: translateX(0); } }

/* ── CCTV DARK HUD FRAME ── */
.cctv-shell {
  background: #04090F;
  border-radius: 16px;
  border: 1px solid rgba(0,212,255,0.25);
  box-shadow: 0 0 0 1px rgba(0,212,255,0.08),
              0 24px 64px rgba(0,0,0,0.55),
              inset 0 1px 0 rgba(0,212,255,0.14);
  overflow: hidden;
  margin-bottom: 6px;
}
.cctv-topbar {
  background: linear-gradient(90deg, #020810, #061020);
  padding: 9px 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid rgba(0,212,255,0.18);
}
.cctv-cam-id {
  font-family: 'Orbitron', monospace;
  font-size: 10px; letter-spacing: 2.5px; color: #00D4FF;
}
.cctv-rec-badge {
  font-family: 'Orbitron', monospace;
  font-size: 10px; letter-spacing: 2px; color: #FF2D55;
  display: flex; align-items: center; gap: 7px;
}
.cctv-rec-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #FF2D55; box-shadow: 0 0 8px #FF2D55;
  animation: recBlink 1s ease-in-out infinite;
}
@keyframes recBlink { 0%,100%{ opacity:1; } 50%{ opacity:0.12; } }
.cctv-imgbox { position: relative; line-height: 0; }
.cctv-corner {
  position: absolute; width: 22px; height: 22px;
  border-color: #00D4FF; border-style: solid; opacity: 0.75;
  z-index: 10;
}
.cctv-corner.ctl { top:10px; left:10px;  border-width:2px 0 0 2px; }
.cctv-corner.ctr { top:10px; right:10px; border-width:2px 2px 0 0; }
.cctv-corner.cbl { bottom:10px; left:10px;  border-width:0 0 2px 2px; }
.cctv-corner.cbr { bottom:10px; right:10px; border-width:0 2px 2px 0; }
.cctv-scanline {
  position: absolute; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0,212,255,0.30), transparent);
  animation: cctvscan 3.5s linear infinite; pointer-events: none; z-index: 9;
}
@keyframes cctvscan {
  0%  { top: 0%;   opacity: 0; }
  5%  { opacity: 1; }
  95% { opacity: 1; }
  100%{ top: 100%; opacity: 0; }
}
.cctv-noframe {
  background: #04090F;
  padding: 68px 20px; text-align: center;
  font-family: 'Orbitron', monospace;
  color: rgba(0,212,255,0.35); font-size: 11px; letter-spacing: 3px; line-height: 2.4;
}
.cctv-botbar {
  background: linear-gradient(90deg, #020810, #061020);
  padding: 8px 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-top: 1px solid rgba(0,212,255,0.18);
}
.cctv-ts {
  font-family: 'Orbitron', monospace;
  font-size: 9px; color: rgba(0,212,255,0.55); letter-spacing: 1.5px;
}
.cctv-signal { display: flex; gap: 3px; align-items: flex-end; }
.cctv-sigbar { width: 4px; background: #00D4FF; border-radius: 1px; opacity: 0.75; }

/* ── ALERT STATUS PILLS ── */
.alert-status-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.alert-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 16px; border-radius: 999px;
  font-family: 'Orbitron', sans-serif;
  font-size: 10px; letter-spacing: 1px; border: 1px solid;
}
.alert-pill.ap-safe  { background:rgba(52,199,89,0.08);  border-color:rgba(52,199,89,0.28);  color:#34C759; }
.alert-pill.ap-crit  { background:rgba(255,45,85,0.10);  border-color:rgba(255,45,85,0.35);  color:var(--red);   animation: pillGlowR 2.2s ease-in-out infinite; }
.alert-pill.ap-high  { background:rgba(255,149,0,0.10);  border-color:rgba(255,149,0,0.35);  color:var(--amber); }
.alert-pill.ap-med   { background:rgba(255,204,0,0.08);  border-color:rgba(255,204,0,0.30);  color:var(--yellow); }
@keyframes pillGlowR { 0%,100%{ box-shadow:none; } 50%{ box-shadow:0 0 14px rgba(225,29,72,0.22); } }
.pill-orb { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.pill-orb.po-safe  { background:var(--green);  box-shadow:0 0 6px var(--green); }
.pill-orb.po-crit  { background:var(--red);    box-shadow:0 0 7px var(--red);   animation:orbPop 1.6s ease-in-out infinite; }
.pill-orb.po-high  { background:var(--amber);  box-shadow:0 0 6px var(--amber); }
.pill-orb.po-med   { background:var(--yellow); box-shadow:0 0 5px var(--yellow); }
@keyframes orbPop { 0%,100%{ transform:scale(1); box-shadow:0 0 7px var(--red); } 50%{ transform:scale(1.5); box-shadow:0 0 18px rgba(225,29,72,0.40); } }

/* ── SECTION LABELS ── */
.sec-eyebrow {
  font-family: 'Orbitron', sans-serif;
  font-size: 9px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--accent); opacity: 0.7; margin-bottom: 6px;
}

/* ── SNAPSHOT CARDS ── */
.snap-header {
  font-family: 'Orbitron', sans-serif;
  font-size: 9.5px; letter-spacing: 2px; color: var(--muted); margin-bottom: 6px;
}
.snap-severity-badge {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-family: 'Orbitron', sans-serif; font-size: 9px; letter-spacing: 1px;
  font-weight: 700; margin-bottom: 8px;
}
.ssb-normal { background:rgba(16,185,129,0.10); color:#059669; border:1px solid rgba(16,185,129,0.25); }
.ssb-fault  { background:rgba(225,29,72,0.10);  color:var(--red); border:1px solid rgba(225,29,72,0.25); }

/* ── OLD HUD (kept for JS compatibility) ── */
.hud-wrapper {
  position: relative; display: inline-block; width: 100%; border-radius: 12px;
  background: #FFF; padding: 6px; box-shadow: var(--shadow);
}
.hud-corner { position: absolute; width: 24px; height: 24px; border: 3px solid var(--accent); z-index: 10; }
.hud-tl { top:6px; left:6px; border-right:none; border-bottom:none; border-top-left-radius:8px; }
.hud-tr { top:6px; right:6px; border-left:none; border-bottom:none; border-top-right-radius:8px; }
.hud-bl { bottom:6px; left:6px; border-right:none; border-top:none; border-bottom-left-radius:8px; }
.hud-br { bottom:6px; right:6px; border-left:none; border-top:none; border-bottom-right-radius:8px; }
.hud-live {
  position:absolute; top:16px; right:40px; color:var(--accent);
  font-family:'Orbitron',sans-serif; font-size:12px; font-weight:700;
  z-index:10; animation:blink 1.5s infinite;
}
@keyframes blink { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }
.hud-scanline {
  position:absolute; top:6px; left:6px; right:6px; bottom:6px;
  background:linear-gradient(to bottom,transparent 0%,rgba(43,108,255,0.08) 50%,transparent 100%);
  background-size:100% 12px; animation:scanline 5s linear infinite;
  pointer-events:none; z-index:5; border-radius:8px; overflow:hidden;
}
@keyframes scanline { 0%{ background-position:0 -100%; } 100%{ background-position:0 100%; } }
</style>
    """,
    unsafe_allow_html=True,
)

st.components.v1.html(
    """
<script>
  const pDoc = window.parent.document;
  const pBody = pDoc.body;
  
  // Flash Transition on entry
  if(!window.parent.haloFlashed) {
    window.parent.haloFlashed = true;
    const flash = pDoc.createElement('div');
    flash.className = 'dashboard-flash';
    pBody.appendChild(flash);
    setTimeout(() => { if(flash.parentNode) flash.parentNode.removeChild(flash); }, 1000);
  }

  // Animated Cursor Robot
  if (!pDoc.getElementById('cursor-robot')) {
      const robotSVG = `
      <svg id="cursor-robot" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
          <!-- Antenna -->
          <line class="bot-antenna" x1="32" y1="18" x2="32" y2="6"/>
          <circle class="bot-glow" cx="32" cy="6" r="3"/>
          
          <!-- Head -->
          <rect class="bot-body" x="12" y="18" width="40" height="32" rx="8"/>
          
          <!-- Eyes -->
          <g id="bot-eyes">
              <!-- Left Eye -->
              <rect fill="#1E293B" x="20" y="26" width="8" height="12" rx="4"/>
              <circle class="bot-eye left-pupil" cx="24" cy="32" r="2.5"/>
              
              <!-- Right Eye -->
              <rect fill="#1E293B" x="36" y="26" width="8" height="12" rx="4"/>
              <circle class="bot-eye right-pupil" cx="40" cy="32" r="2.5"/>
          </g>
          
          <!-- Mouth / Screen -->
          <rect fill="#E2E8F0" x="24" y="42" width="16" height="4" rx="2"/>
          <circle fill="#27D6C8" cx="28" cy="44" r="1"/>
          <circle fill="#2B6CFF" cx="32" cy="44" r="1"/>
          <circle fill="#27D6C8" cx="36" cy="44" r="1"/>
      </svg>`;
      
      pBody.insertAdjacentHTML('beforeend', robotSVG);
      
      const robot = pDoc.getElementById('cursor-robot');
      const leftPupil = pDoc.querySelector('.left-pupil');
      const rightPupil = pDoc.querySelector('.right-pupil');
      
      let rX = window.parent.innerWidth / 2;
      let rY = window.parent.innerHeight / 2;
      let mX = rX;
      let mY = rY;
      
      // Floating animation variables
      let hoverTime = 0;
      
      window.parent.addEventListener('mousemove', (e) => {
          mX = e.clientX;
          mY = e.clientY;
      });
      
      function updateRobot() {
          // Smooth follow (delay effect)
          rX += (mX - rX) * 0.08;
          rY += (mY - rY) * 0.08;
          
          hoverTime += 0.05;
          const bobY = Math.sin(hoverTime) * 4;
          
          // Calculate angle string to cursor for body rotation
          const dx = mX - rX;
          const dy = mY - rY;
          const currentDist = Math.sqrt(dx*dx + dy*dy);
          
          let rotZ = 0;
          let rotY = 0;
          
          if(currentDist > 0) {
              // Tilt body slightly in direction of movement
              rotZ = (dx / window.parent.innerWidth) * 20;
          }
          
          // Position robot offset slightly below and right of cursor
          robot.style.left = (rX + 20) + 'px';
          robot.style.top = (rY + 20 + bobY) + 'px';
          robot.style.transform = `rotate(${rotZ}deg)`;
          
          // Pupil tracking (look at cursor)
          // The center of the robot relative to viewport
          const cx = rX + 20 + 20; // left + half-size
          const cy = rY + 20 + bobY + 20;
          
          const ex = mX - cx;
          const ey = mY - cy;
          
          // Max movement of pupil inside the eye rect
          const maxEyeMove = 2; 
          
          // Calculate normalized eye offset
          const distEye = Math.sqrt(ex*ex + ey*ey);
          let nx = 0; let ny = 0;
          if(distEye > 0) {
              nx = (ex / distEye) * maxEyeMove;
              ny = (ey / distEye) * maxEyeMove;
          }
          
          if(leftPupil && rightPupil) {
              leftPupil.style.transform = `translate(${nx}px, ${ny}px)`;
              rightPupil.style.transform = `translate(${nx}px, ${ny}px)`;
          }
          
          requestAnimationFrame(updateRobot);
      }
      
      updateRobot();
  }

  // Animated Soft Particle Background
  if(!pDoc.getElementById('halo-particles')) {
      const canvas = pDoc.createElement('canvas');
      canvas.id = 'halo-particles';
      canvas.style.position = 'fixed';
      canvas.style.top = '0'; canvas.style.left = '0';
      canvas.style.width = '100vw'; canvas.style.height = '100vh';
      canvas.style.pointerEvents = 'none'; canvas.style.zIndex = '0';
      pBody.insertBefore(canvas, pBody.firstChild);
      
      const ctx = canvas.getContext('2d');
      let particles = [];
      let w = canvas.width = window.parent.innerWidth;
      let h = canvas.height = window.parent.innerHeight;
      
      for(let i=0; i<60; i++) {
          particles.push({
              x: Math.random() * w, y: Math.random() * h, 
              r: Math.random() * 2.5 + 1.5,
              vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
              opacity: Math.random() * 0.4 + 0.1
          });
      }
      
      let mouseX = w/2; let mouseY = h/2;
      window.parent.addEventListener('mousemove', (e) => {
          mouseX = e.clientX; mouseY = e.clientY;
      }, { passive: true });
      
      window.parent.addEventListener('resize', () => {
          w = canvas.width = window.parent.innerWidth;
          h = canvas.height = window.parent.innerHeight;
      });
      
      function draw() {
          ctx.clearRect(0,0,w,h);
          particles.forEach(p => {
              p.x += p.vx; p.y += p.vy;
              let dx = mouseX - p.x; let dy = mouseY - p.y;
              let dist = Math.sqrt(dx*dx + dy*dy);
              if(dist < 120) { p.x -= dx * 0.015; p.y -= dy * 0.015; }
              
              if(p.x < -10) p.x = w+10; if(p.x > w+10) p.x = -10;
              if(p.y < -10) p.y = h+10; if(p.y > h+10) p.y = -10;
              
              ctx.beginPath();
              ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
              ctx.fillStyle = `rgba(0, 180, 255, ${p.opacity * 0.5})`;
              ctx.fill();
          });
          requestAnimationFrame(draw);
      }
      draw();
  }
  
  // Table row severity styling, count-up animations, HUD wrap
  function enhanceUI() {
    // 1. Table soft badges
    const cells = pDoc.querySelectorAll('div[data-testid="stDataFrame"] td');
    cells.forEach(c => {
        let txt = c.textContent.trim();
        if(txt === 'CRITICAL' || txt === 'HIGH' || txt === 'MEDIUM' || txt === 'INFO') {
            if(!c.dataset.enhanced) {
                c.dataset.enhanced = true;
                c.innerHTML = `<span style="padding:4px 8px; border-radius:12px; font-weight:600; font-size:12px; 
                  ${txt==='CRITICAL' ? 'background:rgba(225,29,72,0.1); color:#E11D48;' : 
                    txt==='HIGH' ? 'background:rgba(245,158,11,0.1); color:#F59E0B;' : 
                    txt==='MEDIUM' ? 'background:rgba(251,191,36,0.1); color:#D97706;' : 
                    'background:rgba(43,108,255,0.1); color:#2B6CFF;'}">${txt}</span>`;
                if(txt === 'CRITICAL') {
                    c.parentElement.style.background = 'rgba(225,29,72,0.03)';
                }
            }
        }
    });
    
    // 2. Wrap Live Feed image for HUD
    const images = pDoc.querySelectorAll('div[data-testid="stImage"] img');
    images.forEach(img => {
        if(!img.dataset.hud) {
            img.dataset.hud = "true";
            const container = img.closest('div[data-testid="stImage"]');
            if(container && !container.parentNode.classList.contains('hud-wrapper')) {
                container.style.position = 'relative';
                const wrapper = pDoc.createElement('div');
                wrapper.className = 'hud-wrapper';
                container.parentNode.insertBefore(wrapper, container);
                wrapper.appendChild(container);
                
                const accents = `<div class="hud-corner hud-tl"></div><div class="hud-corner hud-tr"></div>
                                 <div class="hud-corner hud-bl"></div><div class="hud-corner hud-br"></div>
                                 <div class="hud-live">● LIVE</div><div class="hud-scanline"></div>`;
                wrapper.insertAdjacentHTML('beforeend', accents);
                container.style.borderRadius = '8px';
                container.style.overflow = 'hidden';
            }
        }
    });

    // 3. Number count up animation for KPIs
    const values = pDoc.querySelectorAll('.kpi .value');
    values.forEach(v => {
        if(!v.dataset.counted && v.textContent.trim() !== "") {
            v.dataset.counted = true;
            let finalVal = parseInt(v.textContent.replace(/,/g, ''), 10);
            if(isNaN(finalVal)) return;
            let start = 0;
            let duration = 1500;
            let startTime = null;
            function step(timestamp) {
                if(!startTime) startTime = timestamp;
                let progress = timestamp - startTime;
                let current = Math.min(Math.floor((progress/duration) * finalVal), finalVal);
                v.textContent = current.toLocaleString();
                if(progress < duration) window.requestAnimationFrame(step);
                else v.textContent = finalVal.toLocaleString();
            }
            window.requestAnimationFrame(step);
        }
    });
  }
  
  setInterval(enhanceUI, 1000);
</script>
    """,
    height=0,
)

refresh_ms = 2000
max_rows = 500

import os

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "login"
if "entered_dashboard" not in st.session_state:
    st.session_state["entered_dashboard"] = False

if not st.session_state["logged_in"]:
    st.markdown(
        """
<style>
.bg-icon {
  position: absolute;
  font-size: 42px;
  opacity: 0.15;
  filter: grayscale(0.2);
  animation: floatBg 20s infinite ease-in-out alternate;
  pointer-events: none;
  z-index: 0;
}
@keyframes floatBg {
  0% { transform: translateY(0) rotate(0deg) scale(1); }
  50% { transform: translateY(-40px) rotate(15deg) scale(1.1); filter: grayscale(0); opacity: 0.25; }
  100% { transform: translateY(15px) rotate(-10deg) scale(0.95); }
}
.icon1 { top: 15%; left: 30%; animation-delay: 0s; font-size: 50px; }
.icon2 { bottom: 20%; left: 45%; animation-delay: -5s; font-size: 45px; }
.icon3 { top: 12%; right: 15%; animation-delay: -9s; font-size: 60px; opacity: 0.2; }
.icon4 { bottom: 15%; right: 28%; animation-delay: -13s; font-size: 38px; }

</style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(
            """
            <style>
            .login-box {
                background: linear-gradient(135deg, rgba(16, 32, 64, 0.2), rgba(8, 16, 36, 0.4));
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-top: 1px solid rgba(255, 255, 255, 0.2);
                border-left: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 16px;
                padding: 30px;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4), inset 0 0 20px rgba(0, 212, 255, 0.05);
                text-align: center;
                position: relative;
                z-index: 10;
                backdrop-filter: blur(24px);
                -webkit-backdrop-filter: blur(24px);
            }
            .login-title {
                font-family: 'Orbitron', sans-serif;
                font-size: 20px;
                color: #00D4FF;
                margin-bottom: 20px;
                letter-spacing: 2px;
            }
            /* Style the Streamlit text input */
            div[data-testid="stTextInput"] input {
                background: rgba(4, 9, 15, 0.8) !important;
                border: 1px solid rgba(0, 212, 255, 0.3) !important;
                color: #00D4FF !important;
                font-family: 'Inter', sans-serif !important;
                text-align: center !important;
                letter-spacing: 2px !important;
                border-radius: 8px !important;
            }
            div[data-testid="stTextInput"] input:focus {
                border-color: #2B6CFF !important;
                box-shadow: 0 0 15px rgba(43, 108, 255, 0.3) !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        mode = st.session_state["auth_mode"]
        
        if mode == "login":
            st.markdown('<div class="login-box"><div class="login-title">SYSTEM LOGIN</div></div>', unsafe_allow_html=True)
            
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                
                sub, c_sw, _ = st.columns([2, 1, 1])
                with sub:
                    submit = st.form_submit_button("AUTHORIZE", type="primary", use_container_width=True)
                
            if submit:
                if authenticate_user(DB_PATH, username, password):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    set_active_user(DB_PATH, username)
                    # Clear the shared live feed frame so the new user starts fresh
                    if LATEST_FRAME_PATH.exists():
                        LATEST_FRAME_PATH.unlink(missing_ok=True)
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
            
            if st.button("Need an account? Sign Up", use_container_width=True):
                st.session_state["auth_mode"] = "signup"
                st.rerun()
                
        else:
            st.markdown('<div class="login-box"><div class="login-title">REGISTER SYSTEM ACCESS</div></div>', unsafe_allow_html=True)
            
            with st.form("signup_form"):
                username = st.text_input("Username", placeholder="johndoe")
                email = st.text_input("Email", placeholder="johndoe@example.com")
                phone = st.text_input("Phone Number", placeholder="+1 234 567 8900")
                company = st.text_input("Company", placeholder="Acme Corp")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                
                sub, c_sw, _ = st.columns([2, 1, 1])
                with sub:
                    submit = st.form_submit_button("REGISTER", type="primary", use_container_width=True)
                
            if submit:
                if password != confirm:
                    st.error("❌ Passwords do not match")
                else:
                    success, msg = create_user(DB_PATH, username, password, email, phone, company)
                    if success:
                        st.success(f"✅ {msg}")
                        st.session_state["auth_mode"] = "login"
                        _time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
            
            if st.button("Already have an account? Login", use_container_width=True):
                st.session_state["auth_mode"] = "login"
                st.rerun()

    st.stop()

if st.session_state["logged_in"] and not st.session_state["entered_dashboard"]:
    if not st.session_state.get("flash_landing"):
        st.session_state["flash_landing"] = True
        st.components.v1.html(
            """<script>
            const pDoc = window.parent.document;
            const flash = pDoc.createElement('div');
            flash.className = 'dashboard-flash';
            pDoc.body.appendChild(flash);
            setTimeout(() => { if(flash.parentNode) flash.parentNode.removeChild(flash); }, 1000);
            </script>""", height=0
        )
    st.markdown(
        """
<style>
.bg-icon {
  position: absolute;
  font-size: 42px;
  opacity: 0.15;
  filter: grayscale(0.2);
  animation: floatBg 20s infinite ease-in-out alternate;
  pointer-events: none;
  z-index: 0;
}
@keyframes floatBg {
  0% { transform: translateY(0) rotate(0deg) scale(1); }
  50% { transform: translateY(-40px) rotate(15deg) scale(1.1); filter: grayscale(0); opacity: 0.25; }
  100% { transform: translateY(15px) rotate(-10deg) scale(0.95); }
}
.icon1 { top: 15%; left: 30%; animation-delay: 0s; font-size: 50px; }
.icon2 { bottom: 20%; left: 45%; animation-delay: -5s; font-size: 45px; }
.icon3 { top: 12%; right: 15%; animation-delay: -9s; font-size: 60px; opacity: 0.2; }
.icon4 { bottom: 15%; right: 28%; animation-delay: -13s; font-size: 38px; }
</style>
<div class="landing-card" style="height: 50vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
  <!-- Background Project-related Icons -->
  <div class="bg-icon icon1">🎥</div> <!-- CCTV / Camera Feed -->
  <div class="bg-icon icon2">🤖</div> <!-- AI Model -->
  <div class="bg-icon icon3">🛡️</div> <!-- Safety Shield -->
  <div class="bg-icon icon4">🚨</div> <!-- Alerts -->

  <div id="threejs-hero" style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1; pointer-events: none;"></div>
  
  <div class="landing-content" style="width: 100%; align-items: center; padding: 0;">
    <div style="font-family:'Orbitron',sans-serif; font-size:12px; letter-spacing:3.5px; color:#00D4FF; opacity:0.8; margin-bottom:12px;">// AI-POWERED SAFETY SYSTEM · v2.0</div>
    <div class="halo-word" style="font-size: 100px;">HALO</div>
    <div class="landing-sub" style="font-size: 18px; max-width: 600px; text-align: center;">
      <b style="color:#C8D8F0;">Hazard Analytics and Live Oversight</b> — real-time AI monitoring for industrial safety and productivity.
      <br/><br/>
      Live camera feed • incident evidence • supervisor-ready dashboard.
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.components.v1.html("""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
      const pDoc = window.parent.document;
      const container = pDoc.getElementById("threejs-hero");
      if(container && !container.dataset.init) {
          container.dataset.init = "true";
          const scene = new THREE.Scene();
          const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
          const renderer = new THREE.WebGLRenderer({alpha: true, antialias: true});
          renderer.setSize(container.clientWidth, container.clientHeight);
          container.appendChild(renderer.domElement);
          
          // CCTV Camera Group
          const cameraGroup = new THREE.Group();
          scene.add(cameraGroup);
          
          // Main Body (Cylinder)
          const bodyGeo = new THREE.CylinderGeometry(1.2, 1.2, 4, 32);
          const bodyMat = new THREE.MeshStandardMaterial({
              color: 0xE2E8F0,
              roughness: 0.6,
              metalness: 0.1
          });
          const body = new THREE.Mesh(bodyGeo, bodyMat);
          body.rotation.x = Math.PI / 2; // Point forward
          cameraGroup.add(body);
          
          // Back cap
          const backCapGeo = new THREE.SphereGeometry(1.2, 32, 16, 0, Math.PI);
          const backCapMat = new THREE.MeshStandardMaterial({
              color: 0x94A3B8,
              roughness: 0.7,
              metalness: 0.1
          });
          const backCap = new THREE.Mesh(backCapGeo, backCapMat);
          backCap.rotation.x = Math.PI / 2;
          backCap.position.z = -2;
          cameraGroup.add(backCap);
          
          // Front Bezel (Dark)
          const bezelGeo = new THREE.CylinderGeometry(1.25, 1.25, 0.4, 32);
          const bezelMat = new THREE.MeshStandardMaterial({
              color: 0x1E293B,
              roughness: 0.8,
              metalness: 0.1
          });
          const bezel = new THREE.Mesh(bezelGeo, bezelMat);
          bezel.rotation.x = Math.PI / 2;
          bezel.position.z = 2;
          cameraGroup.add(bezel);
          
          // Lens Glass
          const lensGeo = new THREE.SphereGeometry(0.8, 32, 16, 0, Math.PI);
          const lensMat = new THREE.MeshStandardMaterial({
              color: 0x020617,
              roughness: 0.1,
              metalness: 0.8,
          });
          const lens = new THREE.Mesh(lensGeo, lensMat);
          lens.rotation.x = -Math.PI / 2;
          lens.position.z = 2.0;
          cameraGroup.add(lens);
          
          // Inner Lens ring
          const innerRingGeo = new THREE.RingGeometry(0.4, 0.6, 32);
          const innerRingMat = new THREE.MeshBasicMaterial({ color: 0x334155 });
          const innerRing = new THREE.Mesh(innerRingGeo, innerRingMat);
          innerRing.position.z = 2.4;
          cameraGroup.add(innerRing);
          
          // Recording Light (Red LED)
          const ledGeo = new THREE.CircleGeometry(0.15, 16);
          const ledMat = new THREE.MeshBasicMaterial({ color: 0xE11D48 });
          const led = new THREE.Mesh(ledGeo, ledMat);
          led.position.set(0.7, 0.7, 2.21);
          cameraGroup.add(led);
          
          // Sun Shield / Visor
          const visorGeo = new THREE.CylinderGeometry(1.3, 1.3, 2.5, 32, 1, true, Math.PI * 0.25, Math.PI * 0.5);
          const visorMat = new THREE.MeshStandardMaterial({
              color: 0xF8FAFC,
              roughness: 0.6,
              metalness: 0.1,
              side: THREE.DoubleSide
          });
          const visor = new THREE.Mesh(visorGeo, visorMat);
          visor.rotation.x = Math.PI / 2;
          visor.position.z = 1;
          cameraGroup.add(visor);
          
          // Mounting bracket
          const bracketGroup = new THREE.Group();
          scene.add(bracketGroup);
          
          // Bracket arm
          const armGeo = new THREE.CylinderGeometry(0.3, 0.3, 3, 16);
          const armMat = new THREE.MeshStandardMaterial({ color: 0x64748B, roughness: 0.7, metalness: 0.1 });
          const arm = new THREE.Mesh(armGeo, armMat);
          arm.position.y = 2.5;
          arm.position.z = -1;
          bracketGroup.add(arm);
          
          // Base Plate
          const plateGeo = new THREE.CylinderGeometry(1.5, 1.5, 0.2, 16);
          const plate = new THREE.Mesh(plateGeo, armMat);
          plate.position.y = 4;
          plate.position.z = -1;
          bracketGroup.add(plate);

          // Connect bracket and camera visually
          const jointGeo = new THREE.SphereGeometry(0.5, 16, 16);
          const joint = new THREE.Mesh(jointGeo, armMat);
          joint.position.y = 1;
          joint.position.z = -1;
          cameraGroup.add(joint);

          // Create Right & Left Systems
          const rightSystem = new THREE.Group();
          rightSystem.add(cameraGroup);
          rightSystem.add(bracketGroup);
          rightSystem.scale.set(2.5, 2.5, 2.5);
          rightSystem.position.set(14, -1, 0); 
          scene.add(rightSystem);

          const leftSystem = rightSystem.clone();
          leftSystem.position.set(-14, -1, 0); 
          scene.add(leftSystem);
          const leftCameraGroup = leftSystem.children[0];

          // Lighting (Extra Bright & Vibrant)
          const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444477, 2.5);
          scene.add(hemiLight);

          const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
          scene.add(ambientLight);
          
          const dirLight = new THREE.DirectionalLight(0xffffff, 2.5);
          dirLight.position.set(5, 10, 10);
          scene.add(dirLight);

          const dirLight2 = new THREE.DirectionalLight(0xffffff, 2.0);
          dirLight2.position.set(-5, -5, 10);
          scene.add(dirLight2);
          
          const pointLight = new THREE.PointLight(0x00D4FF, 15, 60); 
          pointLight.position.set(20, 5, 10);
          scene.add(pointLight);
          
          const pointLight2 = new THREE.PointLight(0x8A2BE2, 15, 60); 
          pointLight2.position.set(-20, 5, 10);
          scene.add(pointLight2);

          // Interaction variables
          let targetRotationY = 0;
          let targetRotationX = 0;

          window.parent.addEventListener('mousemove', (e) => {
              if(!container) return;
              const rect = container.getBoundingClientRect();
              const x = e.clientX - rect.left - (rect.width / 2);
              const y = e.clientY - rect.top - (rect.height / 2);
              
              const normX = x / (rect.width / 2);
              const normY = y / (rect.height / 2);
              
              // Camera points at cursor (invert Y for proper tilt)
              targetRotationY = -normX * 0.8;
              targetRotationX = -normY * 0.6;
          });
          
          // Angle camera slightly down by default
          cameraGroup.rotation.x = 0.2;
          cameraGroup.rotation.y = -0.3;
          leftCameraGroup.rotation.x = 0.2;
          leftCameraGroup.rotation.y = 0.3;
          
          camera.fov = 55;
          camera.updateProjectionMatrix();
          camera.position.z = 22;
          camera.position.y = 0;
          camera.position.x = 0; // Centered to capture both left and right
          
          let clock = new THREE.Clock();
          
          function animate() {
              requestAnimationFrame( animate );
              
              let t = clock.getElapsedTime();
              
              // Smoothly track cursor
              cameraGroup.rotation.y += (targetRotationY - cameraGroup.rotation.y) * 0.08;
              cameraGroup.rotation.x += (targetRotationX - cameraGroup.rotation.x) * 0.08;
              leftCameraGroup.rotation.y += (targetRotationY - leftCameraGroup.rotation.y) * 0.08;
              leftCameraGroup.rotation.x += (targetRotationX - leftCameraGroup.rotation.x) * 0.08;
              
              // Hovering animation for entire assembly
              rightSystem.position.y = Math.sin(t * 1.5) * 0.2;
              leftSystem.position.y = Math.sin(t * 1.5 + 1.5) * 0.2; // Offset phase
              
              // Blinking LED
              if(Math.sin(t * 4) > 0) {
                  ledMat.color.setHex(0xE11D48); // Red
              } else {
                  ledMat.color.setHex(0x3B0712); // Dim red
              }
              
              renderer.render( scene, camera );
          };
          animate();
          
          window.parent.addEventListener('resize', () => {
              if(!container) return;
              camera.aspect = container.clientWidth / container.clientHeight;
              camera.updateProjectionMatrix();
              renderer.setSize(container.clientWidth, container.clientHeight);
          });
      }
    </script>
    """, height=0)

    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("ENTER DASHBOARD", type="primary", use_container_width=True):
            st.session_state["entered_dashboard"] = True
            st.rerun()

    st.markdown("""
<style>
.uses-container {
    margin-top: 50px;
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
    padding: 0 5%;
}
.use-card {
    flex: 1;
    min-width: 220px;
    background: linear-gradient(135deg, rgba(10,22,48,0.25), rgba(8,16,36,0.1));
    border: 1px solid rgba(255,255,255,0.1);
    border-top: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px;
    padding: 24px 16px;
    text-align: center;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow: 0 16px 40px rgba(0,0,0,0.4), inset 0 0 20px rgba(0,212,255,0.05);
}
.use-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 30px rgba(0,212,255,0.15);
    border-color: rgba(0,212,255,0.4);
}
.use-icon {
    font-size: 32px;
    margin-bottom: 12px;
}
.use-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 13px;
    color: #00D4FF;
    margin-bottom: 8px;
    letter-spacing: 1.5px;
}
.use-desc {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: #8A9DBE;
    line-height: 1.6;
}
</style>

<div class="uses-container">
    <div class="use-card">
        <div class="use-icon">🚨</div>
        <div class="use-title">FALL DETECTION</div>
        <div class="use-desc">Instant alerts for slips, trips, and falls using advanced AI posture analysis.</div>
    </div>
    <div class="use-card">
        <div class="use-icon">⏱️</div>
        <div class="use-title">IDLE TRACKING</div>
        <div class="use-desc">Welfare checks triggered by prolonged inactivity or dangerous isolation.</div>
    </div>
    <div class="use-card">
        <div class="use-icon">📊</div>
        <div class="use-title">EVIDENCE LOGS</div>
        <div class="use-desc">Secure SQLite incident logging with automated snapshot captures.</div>
    </div>
</div>
""", unsafe_allow_html=True)
            
    st.stop()

if not st.session_state.get("flash_main"):
    st.session_state["flash_main"] = True
    st.components.v1.html(
        """<script>
        const pDoc = window.parent.document;
        const flash = pDoc.createElement('div');
        flash.className = 'dashboard-flash';
        pDoc.body.appendChild(flash);
        setTimeout(() => { if(flash.parentNode) flash.parentNode.removeChild(flash); }, 1000);
        </script>""", height=0
    )

st.markdown(
    """
<div class="halo-header">
  <div class="halo-title">HALO • Lone Worker Safety & Productivity</div>
  <div class="halo-subtitle">Real-time monitoring dashboard · YOLOv8 detection · incident logging · alert evidence</div>
  <div class="halo-badges">
    <div class="badge"><b>Prototype</b> • CPU-friendly</div>
    <div class="badge"><b>Safety</b> • Fall / PPE (optional)</div>
    <div class="badge"><b>Productivity</b> • Idle detection</div>
    <div class="badge"><b>Evidence</b> • Snapshots + SQLite</div>
  </div>
</div>
    """,
    unsafe_allow_html=True,
)

st_autorefresh(interval=int(refresh_ms), key="refresh")

active_user = st.session_state.get("username")
db_stats = stats(DB_PATH, owner_username=active_user) if Path(DB_PATH).exists() else {"total": 0, "by_severity": {}, "by_type": {}}
total_inc = int(db_stats.get("total", 0))
crit = int(db_stats.get("by_severity", {}).get("CRITICAL", 0))
high = int(db_stats.get("by_severity", {}).get("HIGH", 0))
med = int(db_stats.get("by_severity", {}).get("MEDIUM", 0))

# ── Live Alert Status Pills ──
st.markdown(f"""
<div class="alert-status-row">
  <div class="alert-pill {'ap-crit' if crit > 0 else 'ap-safe'}">
    <span class="pill-orb {'po-crit' if crit > 0 else 'po-safe'}"></span>
    {"⚠ CRITICAL ALERTS ACTIVE" if crit > 0 else "NO CRITICAL ALERTS"}
  </div>
  <div class="alert-pill {'ap-high' if high > 0 else 'ap-safe'}">
    <span class="pill-orb {'po-high' if high > 0 else 'po-safe'}"></span>
    {"⚠ PPE VIOLATIONS DETECTED" if high > 0 else "PPE STATUS OK"}
  </div>
  <div class="alert-pill {'ap-med' if med > 0 else 'ap-safe'}">
    <span class="pill-orb {'po-med' if med > 0 else 'po-safe'}"></span>
    {"⚠ IDLE WORKERS DETECTED" if med > 0 else "ACTIVITY NORMAL"}
  </div>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.markdown(
    f"""
<div class="kpi card-tot">
  <div class="kpi-inner">
      <div class="kpi-front">
        <div class="label"><span class="dot green"></span>Total incidents</div>
        <div class="value vt">{total_inc}</div>
        <div class="hint">All logged safety/productivity events</div>
      </div>
      <div class="kpi-back">
          <div>Overall safety trend</div>
          <div style="font-size:24px; margin-top:4px">📊</div>
      </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
k2.markdown(
    f"""
<div class="kpi card-crit">
  <div class="kpi-inner">
      <div class="kpi-front">
        <div class="label"><span class="dot red"></span>Critical</div>
        <div class="value vc">{crit}</div>
        <div class="hint">Fall-like posture alerts</div>
      </div>
      <div class="kpi-back">
          <div style="color:var(--red)">Immediate action</div>
          <div style="font-size:24px; margin-top:4px">⚠️</div>
      </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
k3.markdown(
    f"""
<div class="kpi card-high">
  <div class="kpi-inner">
      <div class="kpi-front">
        <div class="label"><span class="dot amber"></span>High</div>
        <div class="value vh">{high}</div>
        <div class="hint">PPE violations (if enabled)</div>
      </div>
      <div class="kpi-back">
          <div style="color:var(--amber)">Policy enforcement</div>
          <div style="font-size:24px; margin-top:4px">🛡️</div>
      </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
k4.markdown(
    f"""
<div class="kpi card-med">
  <div class="kpi-inner">
      <div class="kpi-front">
        <div class="label"><span class="dot yellow"></span>Medium</div>
        <div class="value vm">{med}</div>
        <div class="hint">Idle threshold exceeded</div>
      </div>
      <div class="kpi-back">
          <div style="color:var(--yellow)">Productivity review</div>
          <div style="font-size:24px; margin-top:4px">⏱️</div>
      </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("---")

import time as _time
import subprocess
import sys

STOP_SIGNAL_PATH = ROOT / "artifacts" / "stop_signal"

# Detect if running on Streamlit Cloud (no local camera/subprocess support)
_IS_CLOUD = os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_SERVER_HEADLESS") == "true" or not Path(sys.executable).exists()

def _is_monitoring_running():
    """Check if monitoring subprocess is still alive."""
    if _IS_CLOUD:
        return False
    proc = st.session_state.get("monitor_process")
    if proc is None:
        return False
    poll = proc.poll()
    if poll is not None:
        # Process has exited
        st.session_state["monitor_process"] = None
        return False
    return True

ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([5, 2, 2, 1])

with ctrl2:
    if _IS_CLOUD:
        st.info("☁️ Cloud Mode — Run main.py locally")
    else:
        monitoring_active = _is_monitoring_running()
        if not monitoring_active:
            if st.button("▶ Start Monitoring", use_container_width=True, type="primary"):
                # Remove old stop signal if any
                if STOP_SIGNAL_PATH.exists():
                    STOP_SIGNAL_PATH.unlink(missing_ok=True)
                # Clear old frame
                if LATEST_FRAME_PATH.exists():
                    LATEST_FRAME_PATH.unlink(missing_ok=True)
                # Launch main.py --headless as a background subprocess
                main_py = str(ROOT / "main.py")
                proc = subprocess.Popen(
                    [sys.executable, main_py, "--headless"],
                    cwd=str(ROOT),
                )
                st.session_state["monitor_process"] = proc
                st.rerun()
        else:
            st.success("● Monitoring Active")

with ctrl3:
    if not _IS_CLOUD and _is_monitoring_running():
        if st.button("■ Stop Monitoring", use_container_width=True):
            # Create stop signal file for main.py to pick up
            STOP_SIGNAL_PATH.touch()
            _time.sleep(1)
            # Force kill if still alive
            proc = st.session_state.get("monitor_process")
            if proc and proc.poll() is None:
                proc.terminate()
            st.session_state["monitor_process"] = None
            st.rerun()

with ctrl4:
    if st.button("Logout", use_container_width=True):
        # Stop monitoring if running
        if not _IS_CLOUD and _is_monitoring_running():
            STOP_SIGNAL_PATH.touch()
            proc = st.session_state.get("monitor_process")
            if proc and proc.poll() is None:
                proc.terminate()
            st.session_state["monitor_process"] = None
        st.session_state["logged_in"] = False
        st.session_state["entered_dashboard"] = False
        st.rerun()


tab_overview, tab_incidents, tab_gallery, tab_analytics = st.tabs(["📺 Overview", "📊 Incidents", "🖼 Snapshots", "📈 Analytics"])

with tab_overview:
    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="sec-eyebrow">// LIVE CAMERA FEED</div>', unsafe_allow_html=True)
        ts_now = _time.strftime("%Y-%m-%d  %H:%M:%S")

        # ── CCTV Dark HUD Shell ──
        st.markdown(f"""
<div class="cctv-shell">
  <div class="cctv-topbar">
    <span class="cctv-cam-id">CAM-01 · ZONE A · LONE WORKER MONITORING</span>
    <span class="cctv-rec-badge"><span class="cctv-rec-dot"></span>REC</span>
  </div>
  <div class="cctv-imgbox">
""", unsafe_allow_html=True)

        if LATEST_FRAME_PATH.exists():
            st.image(str(LATEST_FRAME_PATH), channels="BGR", use_container_width=True)
        else:
            st.markdown("""
<div class="cctv-noframe">
  [ NO SIGNAL DETECTED ]<br/>
  RUN  python main.py  TO ACTIVATE LIVE FEED<br/>
  WAITING FOR YOLO ENGINE...
</div>""", unsafe_allow_html=True)

        st.markdown(f"""
    <div class="cctv-corner ctl"></div>
    <div class="cctv-corner ctr"></div>
    <div class="cctv-corner cbl"></div>
    <div class="cctv-corner cbr"></div>
    <div class="cctv-scanline"></div>
  </div>
  <div class="cctv-botbar">
    <span class="cctv-ts">{ts_now} · UTC+5:30</span>
    <span class="cctv-ts">HALO AI · YOLOv8 · MEDIAPIPE POSE</span>
    <div class="cctv-signal">
      <div class="cctv-sigbar" style="height:5px"></div>
      <div class="cctv-sigbar" style="height:9px"></div>
      <div class="cctv-sigbar" style="height:13px"></div>
      <div class="cctv-sigbar" style="height:17px"></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="sec-eyebrow">// INCIDENT BREAKDOWN BY TYPE</div>', unsafe_allow_html=True)
        by_type = db_stats.get("by_type", {})
        if by_type:
            df_type = (
                pd.DataFrame({"Incident Type": list(by_type.keys()), "Count": list(by_type.values())})
                .sort_values("Count", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(df_type, hide_index=True, use_container_width=True)
        else:
            st.info("No incidents yet. Start `python main.py` to begin monitoring.")

with tab_incidents:
    st.markdown('<div class="sec-eyebrow">// INCIDENT LOG — TIME · SEVERITY · TYPE · WORKER TRACK</div>', unsafe_allow_html=True)
    st.markdown("""
<div style="font-family:'Inter',sans-serif; font-size:13px; color:var(--muted); margin-bottom:14px; line-height:1.7;">
  Every detected safety or productivity event is logged here with its <b>timestamp</b>,
  <b>severity level</b> (CRITICAL / HIGH / MEDIUM / INFO), <b>incident type</b>
  (fall / ppe_violation / idle / normal_snapshot), the <b>worker Track ID</b>,
  and the path to the saved snapshot evidence.
</div>
""", unsafe_allow_html=True)
    rows = fetch_recent(DB_PATH, limit=int(max_rows), owner_username=st.session_state.get("username")) if Path(DB_PATH).exists() else []
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.info("No incidents logged yet. Run `python main.py` and point the camera at a worker.")

with tab_gallery:
    st.markdown('<div class="sec-eyebrow">// SNAPSHOT EVIDENCE GALLERY</div>', unsafe_allow_html=True)
    st.markdown("""
<div style="font-family:'Inter',sans-serif; font-size:13px; color:var(--muted); margin-bottom:14px; line-height:1.7;">
  <b>Normal snapshots</b> — frames saved every ~30s when the worker is detected
  <b>standing or sitting</b> normally. These are demo evidence of healthy activity, not incidents.<br/>
  <b>Fault snapshots</b> — frames captured at the exact moment a hazard was detected:
  a worker <b>lying / falling</b> (CRITICAL), missing PPE (HIGH), or idle too long (MEDIUM).
</div>
""", unsafe_allow_html=True)
    rows = fetch_recent(DB_PATH, limit=int(max_rows), owner_username=st.session_state.get("username")) if Path(DB_PATH).exists() else []
    if not rows:
        st.info("No snapshots yet. Run `python main.py` to start capturing evidence.")
    else:
        df = pd.DataFrame(rows)
        df = df[df["image_path"].notna()]
        if df.empty:
            st.caption("No snapshot images saved yet.")
        else:
            normal_df = df[df["incident_type"] == "normal_snapshot"].copy()
            fault_df  = df[df["incident_type"] != "normal_snapshot"].copy()

            g1, g2 = st.tabs(["✅ Normal Snapshots (standing / sitting)", "⚠️ Fault Snapshots (fall / PPE / idle)"])

            with g1:
                st.markdown("""
<div style="font-size:12px; color:var(--muted); margin-bottom:12px;">
  Worker was detected in a <b>normal posture</b> (standing or sitting).
  Saved automatically every ~30 seconds as baseline evidence.
</div>""", unsafe_allow_html=True)
                if normal_df.empty:
                    st.info("No normal snapshots yet. Keep `main.py` running for ~30s.")
                else:
                    for _, r in normal_df.head(24).iterrows():
                        img_path = str(r.get("image_path", ""))
                        if not img_path or not Path(img_path).exists():
                            continue
                        posture = "Standing" if "standing" in str(r.get("message","")).lower() else "Sitting"
                        label = f"🟢 {posture}  ·  Track #{r.get('track_id')}  ·  {str(r.get('ts_utc',''))[:19]}"
                        with st.expander(label):
                            st.markdown(f'<span class="snap-severity-badge ssb-normal">NORMAL · {posture.upper()}</span>', unsafe_allow_html=True)
                            if img_path.lower().endswith(".mp4"):
                                st.video(img_path)
                            else:
                                st.image(img_path, use_container_width=True)
                            st.caption(str(r.get("message", "")))

            with g2:
                st.markdown("""
<div style="font-size:12px; color:var(--muted); margin-bottom:12px;">
  A hazard was detected. Frames are saved as <b>evidence</b> for supervisor review.
  <b>CRITICAL</b> = fall/lying posture &nbsp;|&nbsp; <b>HIGH</b> = missing PPE &nbsp;|&nbsp; <b>MEDIUM</b> = idle too long.
</div>""", unsafe_allow_html=True)
                if fault_df.empty:
                    st.info("No fault snapshots yet — good news! Worker activity looks normal.")
                else:
                    for _, r in fault_df.head(24).iterrows():
                        img_path = str(r.get("image_path", ""))
                        if not img_path or not Path(img_path).exists():
                            continue
                        sev  = str(r.get("severity", ""))
                        itype = str(r.get("incident_type", ""))
                        sev_icon = "🔴" if sev == "CRITICAL" else "🟠" if sev == "HIGH" else "🟡"
                        label = f"{sev_icon} {sev}  ·  {itype}  ·  Track #{r.get('track_id')}  ·  {str(r.get('ts_utc',''))[:19]}"
                        with st.expander(label):
                            st.markdown(f'<span class="snap-severity-badge ssb-fault">{sev} · {itype.upper().replace("_"," ")}</span>', unsafe_allow_html=True)
                            if img_path.lower().endswith(".mp4"):
                                st.video(img_path)
                            else:
                                st.image(img_path, use_container_width=True)
                            st.caption(str(r.get("message", "")))

with tab_analytics:
    st.markdown('<div class="sec-eyebrow">// ANALYTICS & REPORTING</div>', unsafe_allow_html=True)
    if total_inc == 0:
        st.info("No incidents to analyze.")
    else:
        al, ar = st.columns(2)
        with al:
            st.markdown("### Incidents by Severity")
            if db_stats.get("by_severity"):
                sev_df = pd.DataFrame(list(db_stats["by_severity"].items()), columns=["Severity", "Count"])
                
                fig = px.pie(
                    sev_df, values="Count", names="Severity", hole=0.5,
                    color="Severity",
                    color_discrete_map={
                        "CRITICAL": "#FF2D55", "HIGH": "#FF9500", 
                        "MEDIUM": "#FFCC00", "INFO": "#00D4FF"
                    }
                )
                fig.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=10, r=10)
                )
                st.plotly_chart(fig, use_container_width=True)
        with ar:
            st.markdown("### Incidents by Type")
            if db_stats.get("by_type"):
                type_df = pd.DataFrame(list(db_stats["by_type"].items()), columns=["Type", "Count"])
                
                fig2 = px.bar(
                    type_df, x="Type", y="Count", text="Count",
                    color="Type",
                    color_discrete_sequence=["#2B6CFF", "#00D4FF", "#8A2BE2"]
                )
                fig2.update_traces(textposition="outside", marker_line_width=0)
                fig2.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="Count",
                    showlegend=False, margin=dict(t=20, b=20, l=10, r=10)
                )
                st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        # CSV Export and Timeline
        rows_all = fetch_recent(DB_PATH, limit=10000, owner_username=st.session_state.get("username")) if Path(DB_PATH).exists() else []
        if rows_all:
            df_all = pd.DataFrame(rows_all)
            
            # --- Timeline Chart ---
            df_all['ts_utc'] = pd.to_datetime(df_all['ts_utc'])
            df_time = df_all.set_index('ts_utc').resample('H').size().reset_index(name='Count')
            if not df_time.empty:
                st.markdown("### Incident Frequency Over Time")
                fig3 = px.area(
                    df_time, x="ts_utc", y="Count",
                    color_discrete_sequence=["#00D4FF"],
                    markers=True
                )
                fig3.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", 
                    plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Time", yaxis_title="Incidents",
                    margin=dict(t=20, b=40, l=10, r=10)
                )
                fig3.update_traces(fill='tozeroy', line=dict(width=3))
                st.plotly_chart(fig3, use_container_width=True)
            
            st.markdown("---")
            csv_data = df_all.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Full Incident Report (CSV)",
                data=csv_data,
                file_name=f"halo_safety_report_{_time.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary",
            )