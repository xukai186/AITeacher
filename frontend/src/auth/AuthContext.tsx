import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { fetchMe, login as apiLogin, Me } from "@/api/auth";
import { loadToken, setToken } from "@/api/client";

type AuthState =
  | { status: "loading" }
  | { status: "anon" }
  | { status: "authed"; me: Me };

type Ctx = {
  state: AuthState;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
};

const AuthCtx = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    const token = loadToken();
    if (!token) {
      setState({ status: "anon" });
      return;
    }
    fetchMe()
      .then((me) => setState({ status: "authed", me }))
      .catch(() => {
        setToken(null);
        setState({ status: "anon" });
      });
  }, []);

  const login = async (email: string, password: string) => {
    const { access_token } = await apiLogin({ email, password });
    setToken(access_token);
    const me = await fetchMe();
    setState({ status: "authed", me });
    return me;
  };

  const logout = () => {
    setToken(null);
    setState({ status: "anon" });
  };

  return <AuthCtx.Provider value={{ state, login, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Ctx {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
