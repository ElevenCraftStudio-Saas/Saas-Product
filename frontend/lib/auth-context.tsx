'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  type User,
  type ConfirmationResult,
} from 'firebase/auth';
import { auth, googleProvider, firebaseConfigured } from '@/lib/firebase';

function ensureAuth() {
  if (!auth) {
    throw new Error(
      'Firebase not configured. Add NEXT_PUBLIC_FIREBASE_API_KEY and NEXT_PUBLIC_FIREBASE_APP_ID to frontend/.env.local.'
    );
  }
  return auth;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signInEmail: (email: string, password: string) => Promise<void>;
  signUpEmail: (email: string, password: string) => Promise<void>;
  signInGoogle: () => Promise<void>;
  startPhoneSignIn: (phone: string, recaptcha: RecaptchaVerifier) => Promise<ConfirmationResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!auth) {
      setLoading(false); // Firebase not configured — stop loading, no user.
      return;
    }
    const unsub = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsub;
  }, []);

  const value: AuthContextValue = {
    user,
    loading,
    signInEmail: async (email, password) => {
      await signInWithEmailAndPassword(ensureAuth(), email, password);
    },
    signUpEmail: async (email, password) => {
      await createUserWithEmailAndPassword(ensureAuth(), email, password);
    },
    signInGoogle: async () => {
      await signInWithPopup(ensureAuth(), googleProvider!);
    },
    startPhoneSignIn: (phone, recaptcha) =>
      signInWithPhoneNumber(ensureAuth(), phone, recaptcha),
    signOut: async () => {
      if (auth) await fbSignOut(auth);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
