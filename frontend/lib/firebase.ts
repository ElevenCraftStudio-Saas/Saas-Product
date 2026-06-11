import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, type Auth } from 'firebase/auth';

// Config from Firebase Console > Project settings > Your apps > Web app.
// projectId/messagingSenderId/authDomain are known; apiKey + appId MUST be
// filled in .env.local (NEXT_PUBLIC_FIREBASE_*).
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain:
    process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || 'saas-139a7.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'saas-139a7',
  storageBucket:
    process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || 'saas-139a7.appspot.com',
  messagingSenderId:
    process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '982133588088',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// True only when the web app credentials are actually present.
export const firebaseConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.appId);

let auth: Auth | null = null;
let googleProvider: GoogleAuthProvider | null = null;

if (firebaseConfigured) {
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  auth = getAuth(app);
  googleProvider = new GoogleAuthProvider();
} else if (typeof window !== 'undefined') {
  console.warn(
    '[firebase] NEXT_PUBLIC_FIREBASE_API_KEY / APP_ID missing in .env.local — auth disabled.'
  );
}

export { auth, googleProvider };
