import { UserButton } from "@clerk/clerk-react";
import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-[#0d1117]">
      <div className="flex items-center gap-2">
        <Link to="/" className="text-green-400 font-mono font-bold text-lg tracking-wider hover:text-green-300 transition-colors">
          INVESTMENT HELPER
        </Link>
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/trades"
          className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
        >
          Trades
        </Link>
        <Link
          to="/settings"
          className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
        >
          Settings
        </Link>
        <UserButton
          appearance={{
            elements: { avatarBox: "w-8 h-8" },
          }}
        />
      </div>
    </nav>
  );
}
