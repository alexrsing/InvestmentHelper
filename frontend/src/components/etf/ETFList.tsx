import type { ETFPosition } from "../../types";
import ETFRow from "./ETFRow";

interface Props {
  positions: ETFPosition[];
  onSelectETF: (ticker: string) => void;
  totalValue: number;
  maxPositionPct: number | null;
  minPositionPct: number | null;
}

export default function ETFList({ positions, onSelectETF, totalValue, maxPositionPct, minPositionPct }: Props) {
  if (positions.length === 0) {
    return (
      <div className="text-gray-500 font-mono text-center py-8">
        No positions found
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {positions.map((pos) => (
        <ETFRow
          key={pos.ticker}
          position={pos}
          onClick={onSelectETF}
          totalValue={totalValue}
          maxPositionPct={maxPositionPct}
          minPositionPct={minPositionPct}
        />
      ))}
    </div>
  );
}
