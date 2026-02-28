import { useState, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { Research } from "../types";

export function useResearch() {
  const { getToken } = useAuth();
  const [researching, setResearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const triggerResearch = useCallback(async () => {
    setResearching(true);
    setError(null);
    try {
      await apiFetch<Research[]>("/api/v1/portfolio/research", getToken, {
        method: "POST",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research failed");
    } finally {
      setResearching(false);
    }
  }, [getToken]);

  return { researching, error, triggerResearch };
}
