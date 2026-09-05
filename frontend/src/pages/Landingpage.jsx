
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import LanguageSwitcher from '../components/LanguageSwitcher.jsx'
import opxShot from '../assets/opx.png'
import brainShot from '../assets/brain.png'

const solutionIcons = ['🤖', '🌐', '🔗', '📈']

const Landingpage = () => {
  const { t } = useTranslation('pages')
  const solutionItems = t('landingpage.solutions.items', { returnObjects: true })

  return (
    <div className="lp-root">
      <style>{`
        .lp-root {
          width: 100%;
          margin: 0;
          padding: 0;
          position: relative;
          overflow-x: hidden;
          box-sizing: border-box;
          background: linear-gradient(180deg, #050915 0%, #0a1230 28%, #060a1c 55%, #080d22 78%, #060a1c 100%);
        }

        .lp-hero {
          min-height: 640px;
          width: 100%;
          padding: 110px 24px 60px;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          box-sizing: border-box;
        }

        .lp-swirl {
          position: absolute;
          inset: 0;
          z-index: 0;
          pointer-events: none;
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

        .lp-floaters {
          position: absolute;
          inset: 0;
          z-index: 2;
          pointer-events: none;
        }
        .lp-float {
          position: absolute;
          display: flex;
          align-items: center;
          gap: 8px;
          animation: floatBob ease-in-out infinite;
        }
        @keyframes floatBob {
          0%, 100% { transform: translateY(0) rotate(var(--tilt-a, -3deg)); }
          50% { transform: translateY(-16px) rotate(var(--tilt-b, 3deg)); }
        }
        .lp-float-spin {
          animation: floatSpin linear infinite;
        }
        @keyframes floatSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .float-icon-circle {
          width: 44px;
          height: 44px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          color: #fff;
          font-size: 18px;
          box-shadow: 0 12px 28px rgba(110,90,255,0.4);
        }
        .float-avatar-circle {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #ffb37a, #ff7ab8);
          color: #fff;
          font-weight: 700;
          font-size: 18px;
          border: 3px solid rgba(255,255,255,0.5);
          box-shadow: 0 12px 28px rgba(0,0,0,0.35);
        }
        .float-pill {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 999px;
          background: rgba(255,255,255,0.9);
          color: #1a1a2e;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
          box-shadow: 0 14px 30px rgba(0,0,0,0.35);
        }
        .float-pill .mini-avatars {
          display: flex;
        }
        .float-pill .mini-avatars span {
          width: 22px;
          height: 22px;
          border-radius: 50%;
          border: 2px solid #fff;
          margin-left: -8px;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          color: #fff;
        }
        .float-pill .mini-avatars span:first-child { margin-left: 0; }
        .float-card {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          border-radius: 16px;
          background: rgba(20,22,45,0.85);
          border: 1px solid rgba(255,255,255,0.12);
          color: #fff;
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
          box-shadow: 0 16px 32px rgba(0,0,0,0.4);
          backdrop-filter: blur(6px);
        }
        .float-card .stars { color: #ffc84a; font-size: 13px; letter-spacing: 1px; }
        .float-card .chat-avatar {
          width: 26px;
          height: 26px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          flex: 0 0 auto;
        }
        .float-capsule-shape {
          width: 26px;
          height: 64px;
          border-radius: 999px;
          background: linear-gradient(180deg, #ffffff 0%, #cfd2ff 100%);
          box-shadow: 0 14px 30px rgba(0,0,0,0.3);
        }

        .float-check { top: 10%; left: 10%; }
        .float-trusted { top: 8%; left: 58%; }
        .float-capsule { top: 4%; right: 10%; }
        .float-send { top: 46%; right: 6%; }
        .float-avatar { top: 42%; left: 5%; }
        .float-chat { bottom: 14%; right: 8%; }
        .float-stars { bottom: 16%; left: 7%; }

        @media (max-width: 1100px) {
          .lp-floaters { display: none; }
        }

        @keyframes fadeInUp {
          0% { opacity: 0; transform: translateY(28px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        .fade-in-up {
          opacity: 0;
          animation: fadeInUp 0.9s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }

        .lp-features {
          width: 100%;
          max-width: 1180px;
          margin: 0 auto;
          padding: 30px 24px 110px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 18px;
          position: relative;
          z-index: 1;
        }

        .features-heading {
          margin: 8px 0 0;
          text-align: center;
          font-size: 40px;
          line-height: 1.25;
          font-weight: 800;
          color: #fff;
          max-width: 640px;
        }
        .features-heading .accent {
          background: linear-gradient(90deg, #ffffff 0%, #c9b8ff 45%, #8fa0ff 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .features-subtitle {
          margin: 0;
          max-width: 520px;
          text-align: center;
          color: rgba(215,220,245,0.7);
          font-size: 15px;
          line-height: 1.6;
        }

        .features-grid {
          width: 100%;
          margin-top: 56px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 48px;
          align-items: center;
        }

        .feature-text-col {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 18px;
          text-align: left;
        }

        .feature-tag {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          border-radius: 999px;
          border: 1px solid rgba(140,150,255,0.35);
          background: rgba(120,110,255,0.12);
          color: #b9c0ff;
          font-size: 11.5px;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        .feature-tag .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #8f5bff;
          display: inline-block;
        }

        .feature-title {
          margin: 0;
          font-size: 34px;
          line-height: 1.25;
          font-weight: 800;
          color: #fff;
        }
        .feature-title .highlight {
          background: linear-gradient(90deg, #a98bff 0%, #8fa0ff 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .feature-desc {
          margin: 0;
          max-width: 420px;
          color: rgba(215,220,245,0.7);
          font-size: 15px;
          line-height: 1.75;
        }

        .feature-mockup-wrap {
          position: relative;
          width: 100%;
          max-width: 440px;
          margin: 0 auto;
          min-height: 400px;
          display: flex;
          align-items: center;
        }

        .mockup-chat-panel {
          position: relative;
          width: 100%;
          background: rgba(18,20,42,0.75);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 24px;
          padding: 22px;
          backdrop-filter: blur(10px);
          box-shadow: 0 30px 70px rgba(20,10,60,0.5);
          display: flex;
          flex-direction: column;
          gap: 14px;
          animation: floatBob 7s ease-in-out infinite;
        }

        .mockup-bubble-user {
          align-self: flex-end;
          max-width: 80%;
          background: linear-gradient(90deg, #6a5bff 0%, #8f5bff 100%);
          color: #fff;
          font-size: 12.5px;
          font-weight: 600;
          line-height: 1.5;
          padding: 12px 16px;
          border-radius: 16px 16px 4px 16px;
        }

        .mockup-bubble-ai {
          align-self: flex-start;
          max-width: 92%;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.08);
          color: rgba(230,232,250,0.9);
          font-size: 12.5px;
          line-height: 1.55;
          padding: 12px 16px;
          border-radius: 16px 16px 16px 4px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .mockup-meeting-row {
          display: flex;
          align-items: center;
          gap: 10px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 12px;
          padding: 8px 12px;
        }
        .mockup-meeting-row .meeting-icon {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          flex: 0 0 auto;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          color: #fff;
        }
        .mockup-meeting-row .meeting-label { font-size: 12px; font-weight: 600; color: #fff; }

        .mockup-ai-tag {
          align-self: flex-start;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 700;
          color: #b9c0ff;
          background: rgba(120,110,255,0.15);
          border-radius: 999px;
          padding: 4px 10px;
        }

        .mockup-floating-icon {
          position: absolute;
          top: -18px;
          left: -18px;
          z-index: 3;
          animation: floatBob 6s ease-in-out infinite;
          animation-delay: 0.3s;
        }

        .mockup-popup-card {
          position: absolute;
          right: -14px;
          bottom: -32px;
          width: 250px;
          z-index: 2;
          background: rgba(14,16,34,0.92);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 18px;
          padding: 16px;
          box-shadow: 0 24px 60px rgba(0,0,0,0.55);
          backdrop-filter: blur(10px);
          animation: floatBob 6.5s ease-in-out infinite;
          animation-delay: 0.6s;
        }
        .popup-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }
        .popup-header .title { font-size: 12.5px; font-weight: 700; color: #fff; }
        .popup-header .close {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: rgba(255,255,255,0.08);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          color: rgba(255,255,255,0.6);
        }
        .popup-row {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 0;
          font-size: 11.5px;
          color: rgba(220,222,245,0.85);
        }
        .popup-row .popup-icon { width: 18px; text-align: center; opacity: 0.85; }
        .popup-row .popup-label { color: rgba(200,203,235,0.55); min-width: 62px; }
        .popup-actions { display: flex; gap: 8px; margin-top: 12px; }
        .popup-btn {
          flex: 1;
          text-align: center;
          padding: 8px 0;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 700;
        }
        .popup-btn.outline { border: 1px solid rgba(255,255,255,0.2); color: #fff; background: transparent; }
        .popup-btn.filled { background: linear-gradient(90deg, #6a5bff 0%, #8f5bff 100%); color: #fff; }

        @media (max-width: 900px) {
          .features-grid { grid-template-columns: 1fr; gap: 72px; }
          .feature-text-col { align-items: center; text-align: center; }
          .feature-desc { max-width: 460px; }
          .feature-mockup-wrap { max-width: 380px; min-height: 360px; }
        }

        @media (max-width: 720px) {
          .features-heading { font-size: 30px; }
          .feature-title { font-size: 26px; }
          .lp-features { padding: 20px 20px 70px; }
          .lp-hero { padding: 90px 20px 40px; min-height: auto; }
        }

        .lp-solutions {
          width: 100%;
          max-width: 1180px;
          margin: 0 auto;
          padding: 30px 24px 120px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 18px;
          position: relative;
          z-index: 1;
        }

        .solutions-heading {
          margin: 8px 0 0;
          text-align: center;
          font-size: 40px;
          line-height: 1.25;
          font-weight: 800;
          color: #fff;
          max-width: 640px;
        }

        .solutions-subtitle {
          margin: 0;
          max-width: 520px;
          text-align: center;
          color: rgba(215,220,245,0.7);
          font-size: 15px;
          line-height: 1.6;
        }

        .solutions-grid {
          width: 100%;
          margin-top: 48px;
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 20px;
          align-items: stretch;
        }

        .solution-card {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 16px;
          padding: 24px;
          border-radius: 20px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          cursor: default;
          transition: background .3s ease, border-color .3s ease, transform .3s ease, box-shadow .3s ease;
        }

        .solution-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.12);
          color: #b9c0ff;
          transition: background .3s ease, border-color .3s ease, color .3s ease;
        }

        .solution-title {
          margin: 0;
          font-size: 16px;
          font-weight: 700;
          color: #fff;
          line-height: 1.4;
        }

        .solution-desc {
          margin: 0;
          font-size: 13.5px;
          line-height: 1.6;
          color: rgba(225,228,250,0.75);
          transition: color .3s ease;
        }

        .solution-arrow {
          position: absolute;
          top: 24px;
          right: 24px;
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: rgba(255,255,255,0.16);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-size: 14px;
          opacity: 0;
          transform: translate(-4px, 4px) scale(0.8);
          transition: opacity .25s ease, transform .25s ease;
        }

        .solution-card:hover,
        .solution-card:focus-within {
          background: linear-gradient(150deg, #7a5bff 0%, #8f5bff 55%, #a86bff 100%);
          border-color: transparent;
          transform: translateY(-4px);
          box-shadow: 0 24px 50px rgba(110,90,255,0.35);
        }
        .solution-card:hover .solution-icon,
        .solution-card:focus-within .solution-icon {
          background: rgba(255,255,255,0.16);
          border-color: rgba(255,255,255,0.3);
          color: #fff;
        }
        .solution-card:hover .solution-desc,
        .solution-card:focus-within .solution-desc {
          color: rgba(255,255,255,0.88);
        }
        .solution-card:hover .solution-arrow,
        .solution-card:focus-within .solution-arrow {
          opacity: 1;
          transform: translate(0, 0) scale(1);
        }

        @media (max-width: 900px) {
          .solutions-grid { grid-template-columns: 1fr 1fr; }
        }

        @media (max-width: 560px) {
          .solutions-grid { grid-template-columns: 1fr; }
          .solutions-heading { font-size: 30px; }
        }

        .lp-final-cta {
          position: relative;
          width: 100%;
          padding: 100px 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          z-index: 1;
        }
        .final-cta-grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(140,150,255,0.14) 1px, transparent 1px),
            linear-gradient(90deg, rgba(140,150,255,0.14) 1px, transparent 1px);
          background-size: 44px 44px;
          -webkit-mask-image: radial-gradient(ellipse 60% 100% at 50% 50%, #000 0%, transparent 75%);
          mask-image: radial-gradient(ellipse 60% 100% at 50% 50%, #000 0%, transparent 75%);
        }
        .final-cta-glow {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 520px;
          height: 320px;
          background: radial-gradient(ellipse at center, rgba(120,100,255,0.35) 0%, rgba(90,70,220,0.15) 45%, transparent 75%);
          filter: blur(40px);
          pointer-events: none;
        }
        .final-cta-content {
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 20px;
          max-width: 640px;
        }
        .final-cta-icon {
          width: 56px;
          height: 56px;
          border-radius: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          box-shadow: 0 16px 36px rgba(110,90,255,0.45);
          color: #fff;
          font-size: 22px;
        }
        .final-cta-title {
          margin: 0;
          font-size: 40px;
          line-height: 1.25;
          font-weight: 800;
          color: #fff;
        }
        .final-cta-subtitle {
          margin: 0;
          max-width: 480px;
          color: rgba(215,220,245,0.7);
          font-size: 15px;
          line-height: 1.6;
        }
        @media (max-width: 720px) {
          .lp-final-cta { padding: 70px 20px; }
          .final-cta-title { font-size: 28px; }
        }

        .lp-story {
          position: relative;
          width: 100%;
          max-width: 1180px;
          margin: 0 auto;
          padding: 20px 24px 110px;
          z-index: 1;
        }

        .story-grid {
          display: grid;
          grid-template-columns: 0.85fr 1.15fr;
          gap: 56px;
          align-items: center;
        }

        .story-content {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 22px;
          text-align: left;
        }

        .story-kicker {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 11.5px;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #b9c0ff;
        }
        .story-kicker::before {
          content: '';
          width: 8px;
          height: 8px;
          border-radius: 2px;
          background: linear-gradient(135deg, #6a5bff, #8f5bff);
          display: inline-block;
        }

        .story-quote {
          margin: 0;
          font-size: 28px;
          line-height: 1.45;
          font-weight: 700;
          color: #fff;
          max-width: 460px;
        }

        .story-author {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .story-author-name { font-size: 14px; font-weight: 700; color: #fff; }
        .story-author-role { font-size: 13px; color: rgba(215,220,245,0.6); }

        .story-media {
          position: relative;
        }
        .story-media-frame {
          position: relative;
          width: 100%;
          min-height: 540px;
        }
        .story-shot {
          position: absolute;
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,0.14);
          box-shadow: 0 30px 60px rgba(0,0,0,0.5);
        }
        .story-shot-back {
          top: 0;
          right: 0;
          width: 96%;
          animation: storyFloatBack 8s ease-in-out infinite;
        }
        .story-shot-front {
          bottom: -10px;
          left: -10px;
          width: 82%;
          animation: storyFloatFront 7s ease-in-out infinite;
          animation-delay: 0.4s;
        }
        @keyframes storyFloatBack {
          0%, 100% { transform: translateY(0) rotate(4deg); }
          50% { transform: translateY(-14px) rotate(4deg); }
        }
        @keyframes storyFloatFront {
          0%, 100% { transform: translateY(0) rotate(-4deg); }
          50% { transform: translateY(-18px) rotate(-4deg); }
        }

        .story-stats {
          margin-top: 56px;
          display: flex;
          justify-content: space-around;
          gap: 24px;
          padding-top: 40px;
          border-top: 1px solid rgba(255,255,255,0.08);
        }
        .story-stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
        }
        .story-stat-value {
          font-size: 34px;
          font-weight: 800;
          color: #fff;
        }
        .story-stat-label {
          font-size: 12.5px;
          color: rgba(215,220,245,0.6);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          text-align: center;
        }

        @media (max-width: 900px) {
          .story-grid { grid-template-columns: 1fr; gap: 72px; }
          .story-content { align-items: center; text-align: center; }
          .story-quote { max-width: 480px; }
          .story-media-frame { max-width: 480px; margin: 0 auto; min-height: 420px; }
        }

        @media (max-width: 560px) {
          .story-quote { font-size: 22px; }
          .story-stats { flex-direction: column; align-items: center; gap: 28px; }
        }

        .lp-footer {
          position: relative;
          width: 100%;
          max-width: 1180px;
          margin: 0 auto;
          padding: 0 24px 32px;
          z-index: 1;
        }

        .footer-top {
          display: grid;
          grid-template-columns: 1.4fr 1fr 1fr 1fr;
          gap: 40px;
          padding: 48px 0 40px;
          border-top: 1px solid rgba(255,255,255,0.08);
        }

        .footer-brand {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .footer-logo {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 17px;
          font-weight: 800;
          color: #fff;
          letter-spacing: -0.01em;
        }
        .footer-logo .spark { color: #9aa5ff; font-size: 15px; }

        .footer-tagline {
          margin: 0;
          max-width: 280px;
          color: rgba(215,220,245,0.6);
          font-size: 13.5px;
          line-height: 1.6;
        }

        .footer-col {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 14px;
        }

        .footer-col h4 {
          margin: 0;
          font-size: 14px;
          font-weight: 700;
          color: #fff;
        }

        .footer-link,
        .footer-text {
          font-size: 13.5px;
          line-height: 1.5;
          color: rgba(215,220,245,0.65);
          text-decoration: none;
          background: none;
          border: none;
          padding: 0;
          cursor: default;
        }
        a.footer-link {
          cursor: pointer;
          transition: color .18s ease;
        }
        a.footer-link:hover {
          color: #fff;
        }

        .footer-bottom {
          display: flex;
          align-items: center;
          justify-content: center;
          padding-top: 24px;
          border-top: 1px solid rgba(255,255,255,0.06);
        }

        .footer-copyright {
          margin: 0;
          color: rgba(215,220,245,0.5);
          font-size: 12.5px;
        }

        @media (max-width: 900px) {
          .footer-top { grid-template-columns: 1fr 1fr; row-gap: 36px; }
        }

        @media (max-width: 560px) {
          .footer-top { grid-template-columns: 1fr; }
        }
      `}</style>

      <section className="lp-hero">
      <div className="lp-swirl" aria-hidden="true" />
      <div className="glow-top" />

      <div className="lp-floaters" aria-hidden="true">
        <div className="lp-float float-check" style={{ animationDuration: '6s' }}>
          <div className="float-icon-circle lp-float-spin" style={{ animationDuration: '14s' }}>✓</div>
        </div>

        <div className="lp-float float-trusted" style={{ animationDuration: '7.5s', animationDelay: '0.4s' }}>
          <div className="float-pill">
            <span className="mini-avatars">
              <span>A</span>
              <span>B</span>
              <span>C</span>
            </span>
            {t('landingpage.floatTrusted')}
          </div>
        </div>

        <div className="lp-float float-capsule" style={{ animationDuration: '8s', animationDelay: '0.8s' }}>
          <div className="float-capsule-shape lp-float-spin" style={{ animationDuration: '20s' }} />
        </div>

        <div className="lp-float float-send" style={{ animationDuration: '6.5s', animationDelay: '1.2s' }}>
          <div className="float-icon-circle lp-float-spin" style={{ animationDuration: '16s' }}>✦</div>
        </div>

        <div className="lp-float float-avatar" style={{ animationDuration: '7s', animationDelay: '0.6s' }}>
          <div className="float-avatar-circle">JD</div>
        </div>

        <div className="lp-float float-chat" style={{ animationDuration: '7.2s', animationDelay: '1s' }}>
          <div className="float-card">
            <span className="chat-avatar" />
            {t('landingpage.floatTestimonial')}
          </div>
        </div>

        <div className="lp-float float-stars" style={{ animationDuration: '6.8s', animationDelay: '0.2s' }}>
          <div className="float-card">
            <span className="stars">★★★★★</span>
            {t('landingpage.floatRating')}
          </div>
        </div>
      </div>

      <div className="lp-nav">
        <LanguageSwitcher
          sx={{
            width: 'auto',
            py: '10px',
            px: '20px',
            fontSize: 14,
            borderColor: 'rgba(255,255,255,0.25)',
          }}
        />
        <Link to="/login" className="nav-button">{t('landingpage.signIn')}</Link>
        <Link to="/register" className="nav-button secondary">{t('landingpage.signUp')}</Link>
      </div>

      <div className="lp-content">
        <div className="lp-badge">
          <span className="spark">✦</span>
          {t('landingpage.badge')}
          <span className="spark">✦</span>
        </div>

        <h1 className="lp-title">
          <span className="accent">{t('landingpage.titleLine1')}<br />{t('landingpage.titleLine2')}</span>
        </h1>

        <p className="lp-subtitle">
          {t('landingpage.subtitle')}
        </p>

        <Link to="/register" className="lp-cta">{t('landingpage.cta')}</Link>

        <div className="lp-logos" aria-hidden="true">
          <div className="lp-logos-track">
            <div className="logo-item"><span className="logo-icon">◐</span>DataFlow</div>
            <div className="logo-item"><span className="logo-icon">✦</span>Request</div>
            <div className="logo-item"><span className="logo-icon">◈</span>workkflow</div>
            <div className="logo-item"><span className="logo-icon">▦</span>Automation</div>
            <div className="logo-item"><span className="logo-icon">✛</span>Scheduling</div>
            <div className="logo-item"><span className="logo-icon">◐</span>DataFlow</div>
            <div className="logo-item"><span className="logo-icon">✦</span>Request</div>
            <div className="logo-item"><span className="logo-icon">◈</span>workkflow</div>
            <div className="logo-item"><span className="logo-icon">▦</span>Automation</div>
            <div className="logo-item"><span className="logo-icon">✛</span>Scheduling</div>
          </div>
        </div>
      </div>
      </section>

      <section className="lp-features" id="features">
        <div className="lp-badge fade-in-up" style={{ animationDelay: '0.05s' }}>
          <span className="spark">✦</span>
          {t('landingpage.features.badge')}
        </div>

        <h2 className="features-heading fade-in-up" style={{ animationDelay: '0.15s' }}>
          <span className="accent">{t('landingpage.features.titleLine1')}<br />{t('landingpage.features.titleLine2')}</span>
        </h2>

        <p className="features-subtitle fade-in-up" style={{ animationDelay: '0.25s' }}>
          {t('landingpage.features.subtitle')}
        </p>

        <div className="features-grid">
          <div className="feature-text-col fade-in-up" style={{ animationDelay: '0.35s' }}>
            <div className="feature-tag">
              <span className="dot" />
              {t('landingpage.features.tag')}
            </div>

            <h3 className="feature-title">
              {t('landingpage.features.headingPre')}{' '}
              <span className="highlight">{t('landingpage.features.headingHighlight')}</span>
              <br />
              {t('landingpage.features.headingPost')}
            </h3>

            <p className="feature-desc">
              {t('landingpage.features.description')}
            </p>
          </div>

          <div className="feature-mockup-wrap fade-in-up" style={{ animationDelay: '0.45s' }} aria-hidden="true">
            <div className="mockup-floating-icon">
              <div className="float-icon-circle lp-float-spin" style={{ animationDuration: '18s' }}>✦</div>
            </div>

            <div className="mockup-chat-panel">
              <div className="mockup-bubble-user">
                {t('landingpage.features.chatQuestion')}
              </div>

              <div className="mockup-bubble-ai">
                {t('landingpage.features.chatAnswer')}
                <div className="mockup-meeting-row">
                  <span className="meeting-icon">✓</span>
                  <span className="meeting-label">{t('landingpage.features.meetingWithAndrew')}</span>
                </div>
                <span className="mockup-ai-tag">✦ {t('landingpage.features.aiSuggestion')}</span>
              </div>
            </div>

            <div className="mockup-popup-card">
              <div className="popup-header">
                <span className="title">{t('landingpage.features.popupTitle')}</span>
                <span className="close">✕</span>
              </div>

              <div className="popup-row">
                <span className="popup-icon">🕑</span>
                <span className="popup-label">{t('landingpage.features.timeAndDate')}</span>
                <span>{t('landingpage.features.dateValue')}</span>
              </div>
              <div className="popup-row">
                <span className="popup-icon">👤</span>
                <span className="popup-label">{t('landingpage.features.guests')}</span>
                <span>{t('landingpage.features.guestName')}</span>
              </div>
              <div className="popup-row">
                <span className="popup-icon">📍</span>
                <span className="popup-label">{t('landingpage.features.location')}</span>
                <span>{t('landingpage.features.locationValue')}</span>
              </div>
              <div className="popup-row">
                <span className="popup-icon">🎥</span>
                <span className="popup-label">{t('landingpage.features.platform')}</span>
                <span>{t('landingpage.features.platformValue')}</span>
              </div>

              <div className="popup-actions">
                <span className="popup-btn outline">{t('landingpage.features.reschedule')}</span>
                <span className="popup-btn filled">{t('landingpage.features.joinMeeting')}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-solutions">
        <h2 className="solutions-heading fade-in-up" style={{ animationDelay: '0.05s' }}>
          {t('landingpage.solutions.titleLine1')}<br />{t('landingpage.solutions.titleLine2')}
        </h2>

        <p className="solutions-subtitle fade-in-up" style={{ animationDelay: '0.15s' }}>
          {t('landingpage.solutions.subtitle')}
        </p>

        <div className="solutions-grid">
          {solutionIcons.map((icon, index) => {
            const item = solutionItems[index] || {}
            return (
              <div
                key={item.title || index}
                className="solution-card fade-in-up"
                style={{ animationDelay: `${0.25 + index * 0.1}s` }}
                tabIndex={0}
              >
                <span className="solution-arrow">↗</span>
                <span className="solution-icon">{icon}</span>
                <h3 className="solution-title">{item.title}</h3>
                <p className="solution-desc">{item.description}</p>
              </div>
            )
          })}
        </div>
      </section>

      <section className="lp-story">
        <div className="story-grid">
          <div className="story-content fade-in-up">
            <span className="story-kicker">{t('landingpage.story.kicker')}</span>
            <blockquote className="story-quote">&ldquo;{t('landingpage.story.quote')}&rdquo;</blockquote>
            <div className="story-author">
              <span className="story-author-name">{t('landingpage.story.authorName')}</span>
              <span className="story-author-role">{t('landingpage.story.authorRole')}</span>
            </div>
          </div>

          <div className="story-media fade-in-up" style={{ animationDelay: '0.15s' }} aria-hidden="true">
            <div className="story-media-frame">
              <img src={brainShot} alt="" className="story-shot story-shot-back" />
              <img src={opxShot} alt="" className="story-shot story-shot-front" />
            </div>
          </div>
        </div>

        <div className="story-stats">
          <div className="story-stat">
            <span className="story-stat-value">{t('landingpage.story.stat1Value')}</span>
            <span className="story-stat-label">{t('landingpage.story.stat1Label')}</span>
          </div>
          <div className="story-stat">
            <span className="story-stat-value">{t('landingpage.story.stat2Value')}</span>
            <span className="story-stat-label">{t('landingpage.story.stat2Label')}</span>
          </div>
          <div className="story-stat">
            <span className="story-stat-value">{t('landingpage.story.stat3Value')}</span>
            <span className="story-stat-label">{t('landingpage.story.stat3Label')}</span>
          </div>
        </div>
      </section>

      <section className="lp-final-cta">
        <div className="final-cta-grid" aria-hidden="true" />
        <div className="final-cta-glow" aria-hidden="true" />

        <div className="final-cta-content fade-in-up">
          <div className="final-cta-icon" aria-hidden="true">✦</div>

          <h2 className="final-cta-title">
            {t('landingpage.finalCta.titleLine1')}<br />{t('landingpage.finalCta.titleLine2')}
          </h2>

          <p className="final-cta-subtitle">
            {t('landingpage.finalCta.subtitle')}
          </p>

          <Link to="/register" className="lp-cta">{t('landingpage.finalCta.cta')} →</Link>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="footer-top">
          <div className="footer-brand">
            <div className="footer-logo">
              <span className="spark">✦</span>
              BRAINOPX
            </div>
            <p className="footer-tagline">{t('landingpage.footer.tagline')}</p>
          </div>

          <div className="footer-col">
            <h4>{t('landingpage.footer.product.title')}</h4>
            <a className="footer-link" href="#features">{t('landingpage.footer.product.features')}</a>
            <Link className="footer-link" to="/dashboard/ai-assistant">{t('landingpage.footer.product.aiAssistant')}</Link>
            <Link className="footer-link" to="/dashboard/tasks">{t('landingpage.footer.product.taskManagement')}</Link>
            <Link className="footer-link" to="/dashboard/request">{t('landingpage.footer.product.configurationRequests')}</Link>
          </div>

          <div className="footer-col">
            <h4>{t('landingpage.footer.resources.title')}</h4>
            <span className="footer-text">{t('landingpage.footer.resources.helpCenter')}</span>
            <span className="footer-text">{t('landingpage.footer.resources.documentation')}</span>
            <span className="footer-text">{t('landingpage.footer.resources.contact')}</span>
            <span className="footer-text">{t('landingpage.footer.resources.community')}</span>
          </div>

          <div className="footer-col">
            <h4>{t('landingpage.footer.company.title')}</h4>
            <span className="footer-text">{t('landingpage.footer.company.about')}</span>
            <span className="footer-text">{t('landingpage.footer.company.terms')}</span>
            <span className="footer-text">{t('landingpage.footer.company.privacy')}</span>
          </div>
        </div>

        <div className="footer-bottom">
          <p className="footer-copyright">
            {t('landingpage.footer.copyright', { year: new Date().getFullYear() })}
          </p>
        </div>
      </footer>
    </div>
  )
}

export default Landingpage
