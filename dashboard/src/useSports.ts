import { useCallback, useEffect, useState } from "react";
import type { User } from "firebase/auth";
import { doc, getDocFromServer } from "firebase/firestore";
import { db } from "./firebase";
import {
  sportsHistorySchema,
  sportsLatestSchema,
  type SportsHistory,
  type SportsLatest,
} from "./sportsModel";

/** Reads dfs/latest and dfs/history once the Sports workspace is opened. */
export function useSports(user: User | null, enabled: boolean) {
  const [latest, setLatest] = useState<SportsLatest | null>(null),
    [history, setHistory] = useState<SportsHistory | null>(null),
    [errors, setErrors] = useState<string[]>([]),
    [loading, setLoading] = useState(false),
    [tick, setTick] = useState(0);
  useEffect(() => {
    setLatest(null);
    setHistory(null);
    setErrors([]);
  }, [user]);
  useEffect(() => {
    if (!user || !db || !enabled) return;
    let disposed = false;
    setLoading(true);
    Promise.allSettled(
      (["latest", "history"] as const).map(async (name) => {
        const snapshot = await getDocFromServer(doc(db!, "dfs", name));
        if (!snapshot.exists()) throw new Error("missing");
        const raw = snapshot.data().payload;
        if (typeof raw !== "string" || raw.length > 750000)
          throw new Error("schema");
        const payload = JSON.parse(raw);
        return name === "latest"
          ? sportsLatestSchema.parse(payload)
          : sportsHistorySchema.parse(payload);
      }),
    ).then((results) => {
      if (disposed) return;
      const next: string[] = [];
      results.forEach((r, i) => {
        const label = i === 0 ? "Sports summary" : "Player history";
        if (r.status === "fulfilled") {
          if (i === 0) setLatest(r.value as SportsLatest);
          else setHistory(r.value as SportsHistory);
        } else
          next.push(
            `${label} is unavailable (${r.reason instanceof Error && r.reason.message === "missing" ? "not published yet" : "unreadable"}).`,
          );
      });
      setErrors(next);
      setLoading(false);
    });
    return () => {
      disposed = true;
    };
  }, [user, enabled, tick]);
  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { latest, history, errors, loading, refresh };
}
