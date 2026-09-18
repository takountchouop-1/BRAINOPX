import React, { createContext, useContext, useState, useEffect } from 'react'
import { login as loginRequest, adminLogin as adminLoginRequest, userLogin as userLoginRequest } from '../services/Authenticationservice.js'
import i18n, { LANGUAGE_STORAGE_KEY, SUPPORTED_LANGUAGES } from '../i18n/index.js'

const AuthContext = createContext(null)

const TOKEN_STORAGE_KEY = 'brainopx_token'
const USER_STORAGE_KEY = 'brainopx_user'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [isInitializing, setIsInitializing] = useState(true)

  // On first load, restore any previously saved session from localStorage.
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY)
    const storedUser = localStorage.getItem(USER_STORAGE_KEY)

    if (storedToken && storedUser) {
      try {
        setToken(storedToken)
        setUser(JSON.parse(storedUser))
      } catch {
        localStorage.removeItem(TOKEN_STORAGE_KEY)
        localStorage.removeItem(USER_STORAGE_KEY)
      }
    }
    setIsInitializing(false)
  }, [])

  // The signed-in user's saved `language` is the source of truth once
  // there is a session — keep the UI (and localStorage, so a guest
  // screen briefly shown after logout stays consistent) following it
  // whenever it changes, rather than syncing it separately at every
  // call site that can set `user`.
  useEffect(() => {
    if (user?.language && SUPPORTED_LANGUAGES.includes(user.language)) {
      i18n.changeLanguage(user.language)
      localStorage.setItem(LANGUAGE_STORAGE_KEY, user.language)
    }
  }, [user?.language])

  const login = async ({ email, password }) => {
    const result = await loginRequest({ email, password })
    
    //  Debug - log what the backend returns
    console.log('Login response from backend:', result)
    
    //  Check different possible token field names
    const token = result.access_token || result.token || result.accessToken
    const userData = {
    ...result.user,
    profile_picture: result.user?.profile_picture || null
  }
  setToken(token)
  setUser(userData)
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData))
  return result
}

  // Admin portal sign-in: hits /api/auth/admin-login, which rejects any
  // account that is neither admin nor specialist. The session is only
  // persisted once the backend has already confirmed the role.
  const loginAdmin = async ({ email, password }) => {
    const result = await adminLoginRequest({ email, password })

    const token = result.access_token || result.token || result.accessToken
    const userData = {
      ...result.user,
      profile_picture: result.user?.profile_picture || null,
    }

    setToken(token)
    setUser(userData)
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData))
    return result
  }

  // User-only sign-in: hits /api/auth/user-login, which rejects any
  // administrator account. A normal member/specialist session is only
  // persisted once the backend has confirmed the account is not an admin.
  const loginUser = async ({ email, password }) => {
    const result = await userLoginRequest({ email, password })

    const token = result.access_token || result.token || result.accessToken
    const userData = {
      ...result.user,
      profile_picture: result.user?.profile_picture || null,
    }

    setToken(token)
    setUser(userData)
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData))
    return result
  }

  // Used after the Google OAuth redirect: the backend already issued a
  // normal BRAINOPX access token, we just need to fetch who it belongs
  // to and persist the session the same way the password flow does.
  const loginWithToken = async (accessToken) => {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })

    if (!response.ok) {
      throw new Error('Unable to complete Google sign-in.')
    }

    const userData = await response.json()
    setToken(accessToken)
    setUser(userData)
    localStorage.setItem(TOKEN_STORAGE_KEY, accessToken)
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData))
    return userData
  }

  const updateUser = (updatedData) => {
    setUser((prevUser) => {
      const merged = { ...prevUser, ...updatedData }
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(merged))
      return merged
    })
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(USER_STORAGE_KEY)
  }

  const value = {
    token,
    user,
    isAuthenticated: !!token,
    isInitializing,
    login,
    loginWithToken,
    loginAdmin,
    loginUser,
    updateUser,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}