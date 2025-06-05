"use client";

import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Mail, CheckCircle, Loader2 } from 'lucide-react';

export function WaitlistForm({ className }: { className?: string }) {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!email || !/.+@.+\..+/.test(email)) {
      setError('Please enter a valid email address.');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || result.message || 'Submission failed.');
      }
      
      setSubmitted(true);
      setEmail(''); 
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className={`text-center p-6 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 backdrop-blur-sm animate-in fade-in zoom-in-95 duration-500 ${className}`}>
        <CheckCircle className="h-8 w-8 text-green-400 mx-auto mb-3" />
        <p className="font-medium text-lg mb-1">You're on the list!</p>
        <p className="text-sm text-green-400/80 font-light">We'll notify you when Dime launches.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={`w-full max-w-md space-y-4 ${className}`}>
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Mail className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <Input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
            aria-label="Email address for waitlist"
            className="pl-12 h-12 text-base bg-white/5 backdrop-blur-sm border-gray-700 rounded-lg placeholder:text-gray-400 focus:bg-white/10 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-300 text-white disabled:opacity-50"
          />
        </div>
        <Button 
          type="submit" 
          size="lg"
          disabled={loading}
          className="h-12 px-8 text-base bg-white text-black font-medium rounded-lg hover:bg-gray-100 transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
        >
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            'Join waitlist'
          )}
        </Button>
      </div>
      {error && (
        <p className="text-sm text-red-400 text-left animate-in fade-in slide-in-from-top-2 duration-300">
          {error}
        </p>
      )}
    </form>
  );
}