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
      <div className={`text-center p-6 rounded-lg bg-green-50 border border-green-200 text-green-800 animate-in fade-in zoom-in-95 duration-500 ${className}`}>
        <CheckCircle className="h-8 w-8 text-green-600 mx-auto mb-3" />
        <p className="font-medium text-lg mb-1">You're on the list!</p>
        <p className="text-sm text-green-600 font-normal">We'll notify you when Dime launches.</p>
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
            className="pl-12 h-12 text-base bg-white border-gray-300 rounded-lg placeholder:text-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-300 text-gray-900 disabled:opacity-50 disabled:bg-gray-50"
          />
        </div>
        <Button
          type="submit"
          size="lg"
          disabled={loading}
          className="h-12 px-8 text-base bg-gray-900 text-white font-medium rounded-lg hover:bg-gray-800 transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
        >
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            'Join waitlist'
          )}
        </Button>
      </div>
      {error && (
        <p className="text-sm text-red-600 text-left animate-in fade-in slide-in-from-top-2 duration-300">
          {error}
        </p>
      )}
    </form>
  );
}