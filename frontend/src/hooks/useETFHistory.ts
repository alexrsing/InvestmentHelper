import { useState, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { ETFHistoryResponse } from "../types";

export function useETFHistory() {
  const { getToken } = useAuth();
  const [data, setData] = useState<ETFHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(
    (ticker: string) => {
      setLoading(true);
      setError(null);
      setData(null);
      apiFetch<ETFHistoryResponse>(
        `/api/v1/etfs/${ticker}/history?limit=30`,
        getToken
      )
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [getToken]
  );

  return { data, loading, error, fetchHistory };
}
