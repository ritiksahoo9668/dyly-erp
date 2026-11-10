import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { AuthUser } from "@/types/auth";

const ACCESS_KEY = "dyly_access";
const REFRESH_KEY = "dyly_refresh";
const USER_KEY = "dyly_user";
const REMEMBER_KEY = "dyly_remember";

function readItem(key: string): string | null {
  return localStorage.getItem(key) ?? sessionStorage.getItem(key);
}

function clearAuthStorage() {
  for (const store of [localStorage, sessionStorage]) {
    store.removeItem(ACCESS_KEY);
    store.removeItem(REFRESH_KEY);
    store.removeItem(USER_KEY);
    store.removeItem(REMEMBER_KEY);
  }
}

function writeCredentials(
  store: Storage,
  payload: { access: string; refresh: string; user: AuthUser },
  remember: boolean,
) {
  clearAuthStorage();
  store.setItem(ACCESS_KEY, payload.access);
  store.setItem(REFRESH_KEY, payload.refresh);
  store.setItem(USER_KEY, JSON.stringify(payload.user));
  store.setItem(REMEMBER_KEY, remember ? "1" : "0");
}

function activeStore(): Storage {
  if (sessionStorage.getItem(ACCESS_KEY)) return sessionStorage;
  return localStorage;
}

function readStoredUser(): AuthUser | null {
  try {
    const raw = readItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
};

const initialState: AuthState = {
  accessToken: readItem(ACCESS_KEY),
  refreshToken: readItem(REFRESH_KEY),
  user: readStoredUser(),
};

type CredentialsPayload = {
  access: string;
  refresh: string;
  user: AuthUser;
  rememberMe?: boolean;
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials(state, action: PayloadAction<CredentialsPayload>) {
      const remember = action.payload.rememberMe ?? true;
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
      state.user = action.payload.user;
      writeCredentials(remember ? localStorage : sessionStorage, action.payload, remember);
    },
    setUser(state, action: PayloadAction<AuthUser>) {
      state.user = action.payload;
      activeStore().setItem(USER_KEY, JSON.stringify(action.payload));
    },
    logout(state) {
      state.accessToken = null;
      state.refreshToken = null;
      state.user = null;
      clearAuthStorage();
    },
  },
});

export const { setCredentials, setUser, logout } = authSlice.actions;
export const authReducer = authSlice.reducer;

export const selectIsAuthenticated = (state: { auth: AuthState }) =>
  Boolean(state.auth.accessToken);
export const selectAuthUser = (state: { auth: AuthState }) => state.auth.user;
export const selectAccessToken = (state: { auth: AuthState }) => state.auth.accessToken;
