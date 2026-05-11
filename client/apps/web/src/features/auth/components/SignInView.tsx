import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth.js';

export function SignInView() {
  const { requestMagicLink, verifyMagicLink } = useAuth();
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [step, setStep] = useState<'email' | 'token'>('email');
  const [error, setError] = useState<string | null>(null);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const resp = await requestMagicLink.mutateAsync(email);
      if (resp.dev_token) {
        setToken(resp.dev_token);
      }
      setStep('token');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send magic link');
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await verifyMagicLink.mutateAsync({ email, token });
      window.location.href = '/';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid token');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Baseflo</h1>
          <p className="mt-2 text-sm text-gray-400">
            {step === 'email' ? 'Enter your email to sign in' : 'Enter your magic link token'}
          </p>
        </div>

        {step === 'email' ? (
          <form onSubmit={handleRequest} className="space-y-4">
            <input
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-gray-600"
            />
            <button
              type="submit"
              disabled={requestMagicLink.isPending}
              className="w-full rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-950 hover:bg-gray-100 disabled:opacity-50"
            >
              {requestMagicLink.isPending ? 'Sending…' : 'Send Magic Link'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerify} className="space-y-4">
            <div className="rounded-lg border border-yellow-900/50 bg-yellow-950/30 p-3 text-xs text-yellow-200">
              For MVP, the token is shown below. Copy it and paste above.
            </div>
            <input
              type="text"
              required
              placeholder="Paste token here"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-gray-600"
            />
            <button
              type="submit"
              disabled={verifyMagicLink.isPending}
              className="w-full rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-950 hover:bg-gray-100 disabled:opacity-50"
            >
              {verifyMagicLink.isPending ? 'Verifying…' : 'Verify & Sign In'}
            </button>
            <button
              type="button"
              onClick={() => setStep('email')}
              className="w-full text-center text-xs text-gray-500 hover:text-gray-300"
            >
              Use a different email
            </button>
          </form>
        )}

        {error && (
          <div className="rounded-lg bg-red-950/50 p-3 text-xs text-red-300">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
