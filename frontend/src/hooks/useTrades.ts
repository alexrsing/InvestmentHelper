import { useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { TradeRequest, TradeResponse } from "../types";

export function useTrades() {
  const { getToken } = useAuth();
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submitTrade = async (request: TradeRequest): Promise<TradeResponse> => {
    setSubmitting(request.ticker);
    setError(null);
    try {
      const result = await apiFetch<TradeResponse>(
        "/api/v1/portfolio/trade",
        getToken,
        {
          method: "POST",
          body: JSON.stringify(request),
        }
      );
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Trade failed";
      setError(msg);
      throw e;
    } finally {
      setSubmitting(null);
    }
  };

  return { submitTrade, submitting, error };
}
