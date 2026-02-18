import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const navLinks = [
  { to: '/', label: 'Portfolio' },
  { to: '/trading', label: 'Trading' },
];

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-gray-900 no-underline">
            <span className="text-blue-600">Investment</span>Helper
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            {isAuthenticated &&
              navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`text-sm font-medium no-underline transition-colors ${
                    location.pathname === link.to
                      ? 'text-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            {isAuthenticated ? (
              <div className="flex items-center gap-4">
                <span className="text-sm text-gray-500">{user?.username || user?.email}</span>
                <button
                  onClick={logout}
                  className="text-sm text-gray-600 hover:text-red-600 transition-colors bg-transparent border-none cursor-pointer p-0"
                >
                  Logout
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="text-sm font-medium text-blue-600 no-underline hover:text-blue-800"
              >
                Login
              </Link>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden bg-transparent border-none cursor-pointer p-2"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden pb-4 border-t border-gray-100 pt-2">
            {isAuthenticated &&
              navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className={`block py-2 text-sm font-medium no-underline ${
                    location.pathname === link.to
                      ? 'text-blue-600'
                      : 'text-gray-600'
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            {isAuthenticated ? (
              <button
                onClick={() => { logout(); setMenuOpen(false); }}
                className="block w-full text-left py-2 text-sm text-gray-600 hover:text-red-600 bg-transparent border-none cursor-pointer p-0"
              >
                Logout ({user?.username || user?.email})
              </button>
            ) : (
              <Link
                to="/login"
                onClick={() => setMenuOpen(false)}
                className="block py-2 text-sm font-medium text-blue-600 no-underline"
              >
                Login
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
