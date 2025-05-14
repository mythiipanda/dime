"use client";

import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Mail } from 'lucide-react';

export function WaitlistForm({ className }: { className?: string }) {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setSubmitted(false);

    if (!email || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {
      setError('Please enter a valid email address.');
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
      
      if (result.message && result.message.includes('already on the waitlist')) {
        setSubmitted(true); 
        setError(''); 
      } else {
        setSubmitted(true);
      }
      setEmail(''); 
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.');
      setSubmitted(false); 
    }
  };

  if (submitted) {
    return (
      <div className={`text-center p-4 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 ${className}`}>
        <p className="font-semibold">Thanks for joining!</p>
        <p className="text-sm">We\'ll keep you updated on Dime.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={`w-full max-w-md space-y-3 ${className}`}>
      <div className="relative flex items-center">
        <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
        <Input
          type="email"
          placeholder="Enter your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          aria-label="Email address for waitlist"
          className="pl-10 h-12 text-base bg-gray-800/50 border-white/20 placeholder:text-gray-500 focus:bg-gray-800/70 focus:border-blue-400"
        />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button 
        type="submit" 
        size="lg"
        className="w-full h-12 text-base bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-semibold shadow-lg hover:shadow-cyan-500/30 transition-all duration-300 transform hover:scale-105"
      >
        Join Waitlist
      </Button>
    </form>
  );
} 