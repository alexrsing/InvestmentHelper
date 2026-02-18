import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [tokenInput, setTokenInput] = useState('');
  const [error, setError] = useState('');
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = tokenInput.trim();
    if (!trimmed) {
      setError('Please paste a JWT token');
      return;
    }
    // Basic JWT format check (3 dot-separated parts)
    if (trimmed.split('.').length !== 3) {
      setError('Invalid token format — expected a JWT (3 dot-separated parts)');
      return;
    }
    login(trimmed);
    navigate('/', { replace: true });
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-lg border border-gray-200 p-6 sm:p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Login</h1>
          <p className="text-sm text-gray-500 mb-6">
            Login endpoint coming soon. For development, paste a JWT token below.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-1">
                Dev Token
              </label>
              <textarea
                id="token"
                rows={4}
                value={tokenInput}
                onChange={(e) => {
                  setTokenInput(e.target.value);
                  setError('');
                }}
                placeholder="Paste JWT token here..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
            >
              Sign In with Token
            </button>
          </form>

          <div className="mt-6 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500">
              Generate a token via the backend:
            </p>
            <code className="text-xs text-gray-700 break-all block mt-1">
              python -c "from app.core.security import create_access_token; print(create_access_token({'{'}\"sub\": \"user1\", \"email\": \"dev@test.com\", \"username\": \"dev\"{'}'}))"
            </code>
          </div>
        </div>
      </div>
    </div>
  );
}
