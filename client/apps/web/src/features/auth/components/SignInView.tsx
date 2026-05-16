import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth.js';

export function SignInView({ redirectTo = '/workspace/business' }: { redirectTo?: string }) {
  const { requestMagicLink, verifyMagicLink } = useAuth();
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [step, setStep] = useState<'email' | 'token'>('email');
  const [error, setError] = useState<string | null>(null);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await requestMagicLink.mutateAsync(email);
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
      window.location.assign(resolveSafeRedirect(redirectTo));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid token');
    }
  };

  return (
    <div className="flex min-h-screen bg-[#f4f1ea] text-[#1a1a1a] font-serif selection:bg-[#d95d39]/30">
      
      {/* Left Column */}
      <div className="hidden lg:flex flex-1 border-r-2 border-black/20 p-12 flex-col justify-between max-w-[60%]">
        
        <div className="max-w-[700px] mx-auto w-full">
          {/* Top Row */}
          <div className="flex justify-between items-baseline mb-16 border-b border-black/20 pb-4">
            <div className="text-3xl font-bold italic tracking-tight">baseflo<span className="text-[#d95d39]">.</span></div>
            <div className="text-[11px] font-sans tracking-[0.2em] text-black/50 uppercase font-semibold">EDITION · SIGN-IN DESK</div>
          </div>

          {/* Headline */}
          <div className="grid grid-cols-3 gap-8 text-[10px] font-sans tracking-widest text-black/50 uppercase mb-6">
            <div>EST. ON<br/>CONNECT</div>
            <div>FOR FOUNDERS, OPERATORS<br/>& TEAMS</div>
            <div>ONE<br/>DECISION</div>
          </div>
          <h1 className="text-7xl xl:text-8xl font-bold tracking-tight mb-4">Welcome back<span className="text-[#d95d39]">.</span></h1>
          <p className="text-xl italic text-black/70 mb-10 pb-10 border-b-2 border-black/80">
            "Your edition is waiting. Sign in and we'll file it."
          </p>

          {/* Columns */}
          <div className="grid grid-cols-2 gap-12">
            
            {/* From the editor */}
            <div>
              <div className="text-[#d95d39] text-[10px] font-sans tracking-widest font-semibold uppercase mb-3">FROM THE EDITOR</div>
              <h2 className="text-[22px] font-bold leading-tight mb-4 tracking-tight">An operating brief — filed by your data, not your team.</h2>
              <div className="text-[15px] leading-relaxed text-black/80 mb-5">
                <span className="float-left text-5xl font-bold leading-[0.8] mr-2 mt-1">B</span>
                aseflo connects to the tools you already use, learns the shape of your business, and files a brief every morning. Headlines you can act on. Reasoning beneath each one. One-click moves that close the loop.
              </div>
              <p className="text-[15px] leading-relaxed text-black/80 mb-8">
                No dashboards to build. No templates to pick. No "AI employee" cosplay.
              </p>
              
              <div className="border-l-2 border-[#d95d39] pl-4 py-1">
                <p className="text-[15px] italic text-black/90 mb-2">"Not a dashboard. Not a copilot. The state layer your business actually runs on."</p>
                <div className="text-[9px] font-sans font-bold tracking-widest text-black/40 uppercase">— THE BASEFLO STANCE</div>
              </div>
            </div>
            
            {/* In today's edition */}
            <div>
              <div className="text-[#d95d39] text-[10px] font-sans tracking-widest font-semibold uppercase mb-3">IN TODAY'S EDITION</div>
              <h3 className="text-lg font-bold leading-tight mb-6">A sample of what's waiting once you sign in:</h3>
              
              <div className="mb-5">
                <h4 className="font-bold text-[15px] mb-1 leading-snug">Bangalore quietly outpaces Mumbai 3-to-1</h4>
                <div className="text-xs italic text-black/50">delivery speed · cross-source · high confidence</div>
              </div>
              <div className="mb-5">
                <h4 className="font-bold text-[15px] mb-1 leading-snug">Forty-seven people read your emails but never buy</h4>
                <div className="text-xs italic text-black/50">engaged-dormant cohort · ₹1.13L LTV</div>
              </div>
              <div className="mb-5">
                <h4 className="font-bold text-[15px] mb-1 leading-snug">Five SKUs will run out before reorder lands</h4>
                <div className="text-xs italic text-black/50">8 days of cover · 14d lead time · urgent</div>
              </div>
            </div>

          </div>
        </div>

        {/* Footer */}
        <div className="max-w-[700px] mx-auto w-full text-[11px] font-sans text-black/50 flex gap-4 mt-16 pt-4 border-t border-black/10">
          <span>© Baseflo, 2026</span>
          <span>·</span>
          <a href="/" className="hover:text-black border-b border-black/20 pb-0.5">&larr; back to landing</a>
          <span>·</span>
        </div>
      </div>
      
      {/* Right Column */}
      <div className="flex-1 p-6 md:p-12 flex flex-col items-center justify-center relative bg-[#f4f1ea]">
        
        <div className="relative w-full max-w-[420px]">
          
          {/* Passwordless sticker */}
          <div className="absolute -top-6 -right-6 md:-right-8 rotate-6 bg-[#f4f1ea] border border-[#d95d39] px-4 py-2 shadow-sm z-10 hidden sm:block">
            <div className="text-[#d95d39] font-serif italic text-lg leading-none">passwordless</div>
            <div className="text-[9px] font-sans text-black/60 uppercase tracking-wide mt-1">no password, ever</div>
          </div>

          <div className="bg-white border-2 border-black/80 shadow-[6px_6px_0px_rgba(0,0,0,0.15)] p-8 sm:p-10 relative z-0">
            <div className="text-center mb-8">
              <div className="text-[10px] font-sans font-semibold tracking-[0.2em] text-black/40 uppercase mb-3">SIGN IN TO BASEFLO</div>
              <h2 className="text-[40px] font-bold tracking-tight mb-2">Sign in</h2>
              <p className="text-[15px] italic text-black/60">We'll send a magic link to your inbox.</p>
              <div className="border-b-4 border-black/20 w-full mt-6"></div>
            </div>

            {step === 'email' ? (
              <form onSubmit={handleRequest} className="space-y-6">
                <div>
                  <label htmlFor="signin-email" className="block text-[10px] font-sans font-semibold tracking-widest text-black/50 uppercase mb-2">WORK EMAIL</label>
                  <input 
                    id="signin-email"
                    type="email" 
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@company.com" 
                    className="w-full border-2 border-black/80 bg-[#f8f6f0] px-4 py-3.5 text-[15px] font-serif italic placeholder:text-black/40 outline-none focus:border-[#d95d39]"
                  />
                </div>
                <button 
                  type="submit"
                  disabled={requestMagicLink.isPending}
                  className="w-full bg-[#d95d39] text-white font-sans font-bold py-3.5 border-2 border-black/80 shadow-[3px_3px_0px_rgba(0,0,0,1)] hover:translate-y-[1px] hover:shadow-[2px_2px_0px_rgba(0,0,0,1)] transition-all flex justify-center items-center gap-2"
                >
                  {requestMagicLink.isPending ? 'sending...' : 'send magic link ➔'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerify} className="space-y-6">
                <div className="bg-[#f8f6f0] border border-[#d95d39]/40 p-4 text-[13px] italic text-black/70">
                  Check your email for the magic link. <br/>
                  <span className="text-[11px] text-black/50">Paste the token from the sign-in email below.</span>
                </div>
                <div>
                  <label htmlFor="signin-token" className="block text-[10px] font-sans font-semibold tracking-widest text-black/50 uppercase mb-2">MAGIC TOKEN</label>
                  <input 
                    id="signin-token"
                    type="text" 
                    required
                    value={token}
                    onChange={e => setToken(e.target.value)}
                    placeholder="Paste token here" 
                    className="w-full border-2 border-black/80 bg-[#f8f6f0] px-4 py-3.5 text-[15px] font-mono placeholder:text-black/40 outline-none focus:border-[#d95d39]"
                  />
                </div>
                <button 
                  type="submit"
                  disabled={verifyMagicLink.isPending}
                  className="w-full bg-[#d95d39] text-white font-sans font-bold py-3.5 border-2 border-black/80 shadow-[3px_3px_0px_rgba(0,0,0,1)] hover:translate-y-[1px] hover:shadow-[2px_2px_0px_rgba(0,0,0,1)] transition-all flex justify-center items-center gap-2"
                >
                  {verifyMagicLink.isPending ? 'verifying...' : 'verify & sign in ➔'}
                </button>
                <button type="button" onClick={() => setStep('email')} className="w-full text-center text-xs text-black/50 hover:text-black/80 italic">
                  Use a different email
                </button>
              </form>
            )}

            {error && (
              <div className="mt-4 border border-red-800/40 bg-red-50 p-3 text-xs text-red-800">
                {error}
              </div>
            )}

            <div className="mt-10 text-center">
              <p className="text-[13px] text-black/60 leading-relaxed mb-4">
                New to Baseflo? <span className="text-[#d95d39]">enter your email above</span> — we'll create your workspace when the link is clicked.
              </p>
              <p className="text-[11px] italic text-black/50 leading-relaxed">
                By continuing you agree to Baseflo terms and privacy notice.<br/>
                Sessions are encrypted & expire after 30 days of inactivity.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function resolveSafeRedirect(value: string): string {
  const fallback = '/workspace/business';
  const allowedPrefixes = ['/workspace', '/connectors', '/connections'];

  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return fallback;

    const path = `${url.pathname}${url.search}${url.hash}`;
    return allowedPrefixes.some((prefix) => url.pathname === prefix || url.pathname.startsWith(`${prefix}/`))
      ? path
      : fallback;
  } catch {
    return fallback;
  }
}
