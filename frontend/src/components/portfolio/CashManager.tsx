import { useState } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../../api/client";

interface Props {
  onUpdate: () => void;
}

export default function CashManager({ onUpdate }: Props) {
  const { getToken } = useAuth();
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsedAmount = parseFloat(amount);
  const isValid = !isNaN(parsedAmount) && parsedAmount > 0;

  const handleCashAction = async (action: "deposit" | "withdraw") => {
    if (!isValid) return;
    setLoading(true);
    setError(null);
    try {
      await apiFetch("/api/v1/portfolio/cash", getToken, {
        method: "PATCH",
        body: JSON.stringify({ action, amount: parsedAmount }),
      });
      setAmount("");
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update cash");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-end gap-2 mb-4">
      {error && (
        <span className="text-red-400 text-xs font-mono">{error}</span>
      )}
      <input
        type="number"
        min="0"
        step="0.01"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        placeholder="$0.00"
        className="w-28 px-2 py-1.5 bg-[#161b22] border border-gray-700 rounded text-xs font-mono text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-400"
      />
      <button
        type="button"
        onClick={() => handleCashAction("deposit")}
        disabled={!isValid || loading}
        className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-green-400 hover:border-green-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      >
        DEPOSIT
      </button>
      <button
        type="button"
        onClick={() => handleCashAction("withdraw")}
        disabled={!isValid || loading}
        className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-red-400 hover:border-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      >
        WITHDRAW
      </button>
    </div>
  );
}
