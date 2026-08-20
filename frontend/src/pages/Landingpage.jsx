import React from 'react'
import { Link } from 'react-router-dom'

const Landingpage = () => {

  return (
    <div className="lp-root">
      <style>{`
        .lp-root {
          min-height: 100vh;
          width: 100%;
          margin: 0;
          padding: 24px;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          box-sizing: border-box;
          background: linear-gradient(180deg, #050915 0%, #0a1230 45%, #060a1c 100%);
        }

        .lp-swirl {
          position: absolute;
          inset: 0;
          z-index: 0;
          pointer-events: none;
          overflow: hidden;
        }
        .lp-swirl::before,
        .lp-swirl::after {
          content: '';
          position: absolute;
          border-radius: 50%;
          filter: blur(60px);
        }
        .lp-swirl::before {
          width: 900px;
          height: 900px;
          right: -320px;
          bottom: -420px;
          background: radial-gradient(circle at 40% 40%, rgba(90,120,255,0.55) 0%, rgba(60,70,220,0.35) 35%, rgba(20,20,60,0.05) 70%, transparent 100%);
          animation: swirlDrift 16s ease-in-out infinite;
        }
        .lp-swirl::after {
          width: 700px;
          height: 700px;
          right: -180px;
          bottom: -300px;
          background: radial-gradient(circle at 60% 30%, rgba(140,160,255,0.35) 0%, rgba(80,90,240,0.2) 40%, transparent 75%);
          animation: swirlDrift 16s ease-in-out infinite reverse;
        }
        @keyframes swirlDrift {
          0% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-30px, -20px) scale(1.06); }
          100% { transform: translate(0, 0) scale(1); }
        }

        .glow-top {
          position: absolute;
          top: 0;
          left: 50%;
          transform: translateX(-50%);
          width: 90%;
          height: 260px;
          pointer-events: none;
          background: radial-gradient(circle at top center, rgba(130,150,255,0.28) 0%, rgba(90,100,255,0.16) 22%, rgba(255,255,255,0.02) 55%, transparent 100%);
          filter: blur(72px);
          z-index: 0;
        }

        .lp-nav { position:absolute; top:24px; right:24px; display:flex; gap:12px; z-index:20; }
        .nav-button { padding:10px 20px; border-radius:999px; border:1px solid rgba(255,255,255,0.25); color:#fff; font-weight:600; font-size:14px; cursor:pointer; text-decoration:none; transition: transform .18s ease, background .18s ease, box-shadow .18s ease, border-color .18s ease; background: rgba(255,255,255,0.06); }
        .nav-button.secondary { background: rgba(255,255,255,0.14); }
        .nav-button:hover { background: rgba(255,255,255,0.22); border-color: rgba(255,255,255,0.5); box-shadow: 0 12px 30px rgba(110,130,255,0.25); transform: translateY(-1px); }

        .lp-content { width:100%; max-width:820px; display:flex; flex-direction:column; align-items:center; text-align:center; gap:22px; position:relative; z-index:1; }

        .lp-badge {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          padding: 8px 20px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.18);
          background: rgba(255,255,255,0.06);
          color: #d9ddff;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.02em;
        }
        .lp-badge .spark { color: #9aa5ff; font-size: 14px; }

        .lp-title {
          margin: 0;
          padding: 0;
          width: 100%;
          font-size: 52px;
          line-height: 1.15;
          font-weight: 800;
          color: #ffffff;
          letter-spacing: -0.01em;
        }
        .lp-title .accent {
          background: linear-gradient(90deg, #ffffff 0%, #c9b8ff 45%, #8fa0ff 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          display: inline-block;
          opacity: 0;
          animation: titleReveal 1s cubic-bezier(0.22, 1, 0.36, 1) 0.15s forwards;
        }
        @keyframes titleReveal {
          0% { opacity: 0; transform: translateY(18px); }
          100% { opacity: 1; transform: translateY(0); }
        }

        .lp-subtitle {
          margin: 0;
          max-width: 560px;
          color: rgba(215,220,245,0.75);
          font-size: 16px;
          line-height: 1.6;
          font-weight: 400;
        }

        .lp-cta {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 14px 28px;
          border-radius: 999px;
          background: linear-gradient(90deg, #6a5bff 0%, #8f5bff 100%);
          color: #fff;
          font-weight: 700;
          font-size: 15px;
          text-decoration: none;
          box-shadow: 0 12px 30px rgba(110,90,255,0.35);
          transition: transform .18s ease, box-shadow .18s ease;
        }
        .lp-cta:hover { transform: translateY(-2px); box-shadow: 0 16px 36px rgba(110,90,255,0.45); }

        .lp-logos {
          width: 100%;
          max-width: 100vw;
          margin-top: 32px;
          overflow: hidden;
          -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 18%, #000 82%, transparent 100%);
          mask-image: linear-gradient(90deg, transparent 0%, #000 18%, #000 82%, transparent 100%);
        }
        .lp-logos-track {
          display: flex;
          align-items: center;
          gap: 14px;
          width: max-content;
          animation: logosScroll 32s linear infinite;
          will-change: transform;
          backface-visibility: hidden;
        }
        @keyframes logosScroll {
          0% { transform: translate3d(0, 0, 0); }
          100% { transform: translate3d(-50%, 0, 0); }
        }
        .logo-item {
          flex: 0 0 auto;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 18px;
          border-radius: 999px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.08);
          color: rgba(225,228,250,0.85);
          font-size: 14px;
          font-weight: 600;
        }
        .logo-icon {
          width: 20px;
          height: 20px;
          border-radius: 6px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          color: #fff;
        }

        @media (max-width: 720px) {
          .lp-title { font-size: 34px; }
          .lp-subtitle { font-size: 14px; }
          .lp-logos-track { gap: 10px; }
          .logo-item { padding: 8px 14px; font-size: 13px; }
        }
      `}</style>

      <div className="lp-swirl" aria-hidden="true" />
      <div className="glow-top" />

      <div className="lp-nav">
        <Link to="/login" className="nav-button">Sign In</Link>
        <Link to="/register" className="nav-button secondary">Sign Up</Link>
      </div>

      <div className="lp-content">
        <div className="lp-badge">
          <span className="spark">✦</span>
          Intelligent Automation
          <span className="spark">✦</span>
        </div>

        <h1 className="lp-title">
          <span className="accent">An Intelligent BrainOpx<br />for Automating Tasks</span>
        </h1>

        <p className="lp-subtitle">
          Experience seamless efficiency with our Brainopx solution, powered by integrated automation for streamlined operations and enhanced productivity.
        </p>

        <Link to="/register" className="lp-cta">Start my trial →</Link>

        <div className="lp-logos" aria-hidden="true">
          <div className="lp-logos-track">
            <div className="logo-item"><span className="logo-icon">◐</span>DataFlow</div>
            <div className="logo-item"><span className="logo-icon">✦</span>CloudPeak</div>
            <div className="logo-item"><span className="logo-icon">◈</span>AgileSphere</div>
            <div className="logo-item"><span className="logo-icon">▦</span>TechVista</div>
            <div className="logo-item"><span className="logo-icon">✛</span>NexusSync</div>
            <div className="logo-item"><span className="logo-icon">◐</span>DataFlow</div>
            <div className="logo-item"><span className="logo-icon">✦</span>CloudPeak</div>
            <div className="logo-item"><span className="logo-icon">◈</span>AgileSphere</div>
            <div className="logo-item"><span className="logo-icon">▦</span>TechVista</div>
            <div className="logo-item"><span className="logo-icon">✛</span>NexusSync</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Landingpage
