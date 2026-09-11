import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { doc, getDocFromServer } from "firebase/firestore";
import { auth, db } from "./firebase";
import {
  homeSchema,
  serverSchema,
  type HomeData,
  type ServerData,
} from "./model";
export function useDashboard() {
  const [user, setUser] = useState<User | null>(null),
    [authLoading, setAuthLoading] = useState(!!auth);
  const [server, setServer] = useState<ServerData | null>(null),
    [home, setHome] = useState<HomeData | null>(null);
  const [errors, setErrors] = useState<string[]>([]),
    [loading, setLoading] = useState(false),
    [refresh, setRefresh] = useState(0);
  useEffect(
    () =>
      auth
        ? onAuthStateChanged(auth, (u) => {
            setServer(null);
            setHome(null);
            setErrors([]);
            setUser(u);
            setAuthLoading(false);
          })
        : undefined,
    [],
  );
  useEffect(() => {
    if (!user || !db) return;
    let disposed = false,
      busy = false;
    async function load() {
      if (busy || document.hidden) return;
      busy = true;
      setLoading(true);
      const results = await Promise.allSettled(
        ["server", "home"].map(async (source) => {
          const snapshot = await getDocFromServer(
            doc(db!, "dashboard", source),
          );
          if (!snapshot.exists()) throw new Error("missing");
          const raw = snapshot.data().payload;
          if (typeof raw !== "string" || raw.length > 750000)
            throw new Error("schema");
          const payload = JSON.parse(raw);
          return source === "server"
            ? serverSchema.parse(payload)
            : homeSchema.parse(payload);
        }),
      );
      if (!disposed) {
        const nextErrors: string[] = [];
        results.forEach((r, i) => {
          const name = i === 0 ? "Server" : "Home";
          if (r.status === "fulfilled") {
            if (i === 0) setServer(r.value as ServerData);
            else setHome(r.value as HomeData);
          } else {
            const code = r.reason?.code;
            if (code === "permission-denied") {
              if (i === 0) setServer(null);
              else setHome(null);
            }
            nextErrors.push(
              code === "permission-denied"
                ? `${name}: access denied. Verify your email and ask the project owner to grant access.`
                : `${name}: update unavailable. Any displayed data is the last successful read.`,
            );
          }
        });
        setErrors(nextErrors);
        setLoading(false);
      }
      busy = false;
    }
    void load();
    const timer = setInterval(() => void load(), 60000);
    const visible = () => void load();
    document.addEventListener("visibilitychange", visible);
    return () => {
      disposed = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [user, refresh]);
  return {
    user,
    authLoading,
    server,
    home,
    errors,
    loading,
    refresh: () => setRefresh((n) => n + 1),
  };
}
