import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/layout/Navbar";
import { useTradingRules } from "../hooks/useTradingRules";

export default function SettingsPage() {
  const { rules, loading, error, saveRules } = useTradingRules();
  const [maxPct, setMaxPct] = useState("");
  const [minPct, setMinPct] = useState("");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    if (rules) {
      setMaxPct(String(rules.max_position_pct));
      setMinPct(String(rules.min_position_pct));
    }
  }, [rules]);

  const handleSave = async () => {
    const maxValue = parseFloat(maxPct);
    const minValue = parseFloat(minPct);

    if (isNaN(maxValue) || maxValue < 1 || maxValue > 100) {
      setFeedback({ type: "error", message: "Max must be between 1 and 100" });
      return;
    }
    if (isNaN(minValue) || minValue < 0 || minValue > 100) {
      setFeedback({ type: "error", message: "Min must be between 0 and 100" });
      return;
    }
    if (minValue > 0 && minValue >= maxValue) {
      setFeedback({ type: "error", message: "Min must be less than max" });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      await saveRules({ max_position_pct: maxValue, min_position_pct: minValue });
      setFeedback({ type: "success", message: "Saved" });
    } catch (e) {
      setFeedback({
        type: "error",
        message: e instanceof Error ? e.message : "Failed to save",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <Link
            to="/"
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
          >
            &larr; Dashboard
          </Link>
          <h1 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
            Settings
          </h1>
        </div>

        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading settings...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">{error}</div>
        )}

        {rules && (
          <div className="border border-gray-800 rounded bg-[#161b22] p-6">
            <h2 className="text-green-400 font-mono font-bold text-sm uppercase tracking-wider mb-4">
              Trading Rules
            </h2>

            <div className="border-t border-gray-800 pt-4">
              <h3 className="text-gray-300 font-mono text-sm mb-1">
                Position Sizing
              </h3>
              <p className="text-gray-500 text-xs mb-4">
                Set min and max percentage of total portfolio value for a single
                position. Buy signals are suppressed when a position reaches
                the max limit. Sell signals are suppressed when a position is
                below the min limit.
              </p>

              <div className="flex items-center gap-3 flex-wrap">
                <label
                  htmlFor="min-position-pct"
                  className="text-xs text-gray-500 uppercase font-mono"
                >
                  Min Position
                </label>
                <div className="flex items-center gap-1">
                  <input
                    id="min-position-pct"
                    type="number"
                    min={0}
                    max={100}
                    step={0.5}
                    value={minPct}
                    onChange={(e) => {
                      setMinPct(e.target.value);
                      setFeedback(null);
                    }}
                    className="w-20 px-2 py-1.5 bg-[#0d1117] border border-gray-700 rounded text-gray-100 font-mono text-sm focus:border-green-400 focus:outline-none"
                  />
                  <span className="text-gray-500 font-mono text-sm">%</span>
                </div>

                <label
                  htmlFor="max-position-pct"
                  className="text-xs text-gray-500 uppercase font-mono"
                >
                  Max Position
                </label>
                <div className="flex items-center gap-1">
                  <input
                    id="max-position-pct"
                    type="number"
                    min={1}
                    max={100}
                    step={0.5}
                    value={maxPct}
                    onChange={(e) => {
                      setMaxPct(e.target.value);
                      setFeedback(null);
                    }}
                    className="w-20 px-2 py-1.5 bg-[#0d1117] border border-gray-700 rounded text-gray-100 font-mono text-sm focus:border-green-400 focus:outline-none"
                  />
                  <span className="text-gray-500 font-mono text-sm">%</span>
                </div>

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-green-400 hover:border-green-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? "SAVING..." : "SAVE"}
                </button>
                {feedback && (
                  <span
                    className={`text-xs font-mono ${
                      feedback.type === "success"
                        ? "text-green-400"
                        : "text-red-400"
                    }`}
                  >
                    {feedback.message}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
