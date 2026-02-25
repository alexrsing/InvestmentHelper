import type { ETFPosition } from "../../types";
import ETFRow from "./ETFRow";

interface Props {
  positions: ETFPosition[];
  onSelectETF: (ticker: string) => void;
}

export default function ETFList({ positions, onSelectETF }: Props) {
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
        <ETFRow key={pos.ticker} position={pos} onClick={onSelectETF} />
      ))}
    </div>
  );
}
