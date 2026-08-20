import React, { createContext, useContext, useState, useEffect } from 'react'
import { login as loginRequest } from '../services/Authenticationservice.js'

const AuthContext = createContext(null)

const TOKEN_STORAGE_KEY = 'brainopx_token'
const USER_STORAGE_KEY = 'brainopx_user'

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