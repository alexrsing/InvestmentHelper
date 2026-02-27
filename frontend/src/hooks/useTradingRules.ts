import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { TradingRules } from "../types";

export function useTradingRules() {
  const { getToken } = useAuth();
  const [rules, setRules] = useState<TradingRules | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = useCallback(() => {
    setLoading(true);
    setError(null);
    apiFetch<TradingRules>("/api/v1/trading-rules", getToken)
      .then(setRules)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [getToken]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const saveRules = useCallback(
    async (update: Partial<TradingRules>) => {
      const res = await apiFetch<TradingRules>(
        "/api/v1/trading-rules",
        getToken,
        {
          method: "PUT",
          body: JSON.stringify(update),
        }
      );
      setRules(res);
      return res;
    },
    [getToken]
  );

  return { rules, loading, error, saveRules, refetch: fetchRules };
}
