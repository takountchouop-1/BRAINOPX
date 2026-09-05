import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext.jsx'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const initialsOf = (fullName) =>
  fullName
    ? fullName.split(' ').filter(Boolean).slice(0, 2)
        .map((part) => part[0].toUpperCase()).join('')
    : '?'

// Shown right after a successful sign-up, before the user lands in the
// dashboard. Reuses Landingpage.jsx's dark gradient/swirl background so
// the register -> success -> dashboard flow doesn't jump between
// unrelated visual styles.
const RegisterSuccess = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const { t } = useTranslation('pages')
  // Register.jsx signs the account in before navigating here, so `user`
  // is already populated — fall back to the nav-state name for the rare
  // case the auto sign-in failed.
  const fullName = user?.full_name || location.state?.fullName || ''
  const profileUrl = user?.profile_picture
    ? `${API_BASE_URL}/uploads/profiles/${user.profile_picture}`
    : null

  return (
    <div className="rs-root">
      <style>{`
        .rs-root {
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

        .rs-swirl {
          position: absolute;
          inset: 0;
          z-index: 0;
          pointer-events: none;
          overflow: hidden;
        }
        .rs-swirl::before,
        .rs-swirl::after {
          content: '';
          position: absolute;
          border-radius: 50%;
          filter: blur(60px);
        }
        .rs-swirl::before {
          width: 900px;
          height: 900px;
          right: -320px;
          bottom: -420px;
          background: radial-gradient(circle at 40% 40%, rgba(90,120,255,0.55) 0%, rgba(60,70,220,0.35) 35%, rgba(20,20,60,0.05) 70%, transparent 100%);
          animation: rsSwirlDrift 16s ease-in-out infinite;
        }
        .rs-swirl::after {
          width: 700px;
          height: 700px;
          right: -180px;
          bottom: -300px;
          background: radial-gradient(circle at 60% 30%, rgba(140,160,255,0.35) 0%, rgba(80,90,240,0.2) 40%, transparent 75%);
          animation: rsSwirlDrift 16s ease-in-out infinite reverse;
        }
        @keyframes rsSwirlDrift {
          0% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-30px, -20px) scale(1.06); }
          100% { transform: translate(0, 0) scale(1); }
        }

        .rs-glow-top {
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

        .rs-content {
          width: 100%;
          max-width: 560px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 20px;
          position: relative;
          z-index: 1;
        }

        .rs-check {
          width: 76px;
          height: 76px;
          border-radius: 50%;
          display: grid;
          place-items: center;
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.18);
          box-shadow: 0 12px 30px rgba(110,90,255,0.35);
        }

        .rs-badge {
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

        .rs-profile {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
        }

        .rs-avatar {
          width: 68px;
          height: 68px;
          border-radius: 50%;
          overflow: hidden;
          display: grid;
          place-items: center;
          background: linear-gradient(135deg, #6a5bff 0%, #8f5bff 100%);
          color: #ffffff;
          font-weight: 700;
          font-size: 24px;
          letter-spacing: 0.02em;
          border: 2px solid rgba(255,255,255,0.25);
          box-shadow: 0 12px 30px rgba(110,90,255,0.35);
        }
        .rs-avatar img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .rs-profile-name {
          color: #ffffff;
          font-weight: 700;
          font-size: 16px;
        }

        .rs-title {
          margin: 0;
          padding: 0;
          width: 100%;
          font-size: 36px;
          line-height: 1.2;
          font-weight: 800;
          color: #ffffff;
          letter-spacing: -0.01em;
        }

        .rs-subtitle {
          margin: 0;
          max-width: 460px;
          color: rgba(215,220,245,0.75);
          font-size: 16px;
          line-height: 1.6;
          font-weight: 400;
        }

        .rs-next {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 14px 32px;
          border: none;
          border-radius: 999px;
          background: linear-gradient(90deg, #6a5bff 0%, #8f5bff 100%);
          color: #fff;
          font-weight: 700;
          font-size: 15px;
          cursor: pointer;
          text-decoration: none;
          box-shadow: 0 12px 30px rgba(110,90,255,0.35);
          transition: transform .18s ease, box-shadow .18s ease;
          margin-top: 8px;
        }
        .rs-next:hover { transform: translateY(-2px); box-shadow: 0 16px 36px rgba(110,90,255,0.45); }

        @media (max-width: 720px) {
          .rs-title { font-size: 28px; }
          .rs-subtitle { font-size: 14px; }
        }
      `}</style>

      <div className="rs-swirl" aria-hidden="true" />
      <div className="rs-glow-top" />

      <div className="rs-content">
        <div className="rs-check">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
            <path d="M20 6L9 17l-5-5" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <div className="rs-badge">
          <span>✦</span>
          {t('registerSuccess.accountCreated')}
          <span>✦</span>
        </div>

        <h1 className="rs-title">
          {fullName ? t('registerSuccess.welcomeName', { name: fullName }) : t('registerSuccess.welcomeDefault')}
        </h1>

        {fullName && (
          <div className="rs-profile">
            <div className="rs-avatar">
              {profileUrl ? (
                <img src={profileUrl} alt={fullName} />
              ) : (
                initialsOf(fullName)
              )}
            </div>
            <span className="rs-profile-name">{fullName}</span>
          </div>
        )}

        <p className="rs-subtitle">
          {t('registerSuccess.subtitle')}
        </p>

        <button type="button" className="rs-next" onClick={() => navigate('/dashboard', { replace: true })}>
          {t('registerSuccess.next')}
        </button>
      </div>
    </div>
  )
}

export default RegisterSuccess
