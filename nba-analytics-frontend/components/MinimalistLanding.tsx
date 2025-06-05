"use client";

import React from 'react';
import { WaitlistForm } from '@/components/landing/WaitlistForm';
import { Logo } from '@/components/layout/Logo';
import { ArrowRight } from 'lucide-react';

export function MinimalistLanding() {
  return (
    <div className="min-h-screen bg-black text-white overflow-hidden relative">
      {/* Animated geometric grid background */}
      <div className="absolute inset-0 opacity-5">
        <div 
          className="absolute inset-0 bg-repeat animate-pulse" 
          style={{
            backgroundImage: `
              linear-gradient(90deg, rgba(59, 130, 246, 0.1) 1px, transparent 1px),
              linear-gradient(rgba(59, 130, 246, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
            animation: 'moveGrid 20s linear infinite'
          }}
        />
      </div>
      
      {/* Animated floating particles background */}
      <div className="absolute inset-0">
        {/* Multiple layers of animated particles */}
        <div className="absolute inset-0">
          {/* Layer 1 - Small particles */}
          {Array.from({ length: 25 }).map((_, i) => (
            <div
              key={`small-${i}`}
              className="absolute w-1 h-1 bg-blue-400/40 rounded-full"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animation: `twinkle ${2 + Math.random() * 3}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 5}s`,
              }}
            />
          ))}
          
          {/* Layer 2 - Medium particles */}
          {Array.from({ length: 15 }).map((_, i) => (
            <div
              key={`medium-${i}`}
              className="absolute w-2 h-2 bg-purple-400/25 rounded-full"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animation: `float ${8 + Math.random() * 6}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 10}s`,
              }}
            />
          ))}
          
          {/* Layer 3 - Large floating orbs */}
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={`large-${i}`}
              className="absolute w-4 h-4 bg-gradient-to-r from-blue-400/10 to-purple-400/10 rounded-full blur-sm"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animation: `floatSlow ${15 + Math.random() * 10}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 12}s`,
              }}
            />
          ))}
        </div>
        
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900/20 via-transparent to-black/40"></div>
      </div>

      <div className="relative z-10 h-screen flex flex-col">
        {/* Clean Navigation */}
        <nav className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <Logo href="/" iconSize={6} textSize="lg" />
            <div className="hidden md:flex space-x-8 text-sm text-gray-400">
              <a href="#" className="hover:text-white transition-colors duration-200">Agent Tasks</a>
              <a href="#" className="hover:text-white transition-colors duration-200">Automation</a>
              <a href="#" className="hover:text-white transition-colors duration-200">Research</a>
            </div>
            <div>
              <button className="text-sm border border-gray-600 rounded-lg px-4 py-2 hover:border-gray-500 transition-colors duration-200">
                Sign in
              </button>
            </div>
          </div>
        </nav>

        {/* Hero content - centered and clean */}
        <div className="container mx-auto px-6 flex-1 flex items-center justify-center">
          <div className="text-center max-w-5xl mx-auto">
            <h1 className="text-5xl md:text-6xl lg:text-8xl font-thin tracking-tight mb-8 leading-[0.9]">
              Your autonomous
              <span className="block font-normal bg-gradient-to-r from-blue-400 via-purple-400 to-blue-500 bg-clip-text text-transparent">
                NBA research
              </span>
              <span className="block text-gray-400 text-3xl md:text-4xl lg:text-5xl mt-4 font-extralight">
                agent
              </span>
            </h1>
            
            <p className="text-gray-300 text-lg md:text-xl mb-12 max-w-2xl mx-auto font-light leading-relaxed">
              Delegate scouting, data collection, and model training to an AI agent that works 24/7. Stop doing manual research—start automating it.
            </p>
            
            <div className="flex flex-col items-center gap-6">
              <WaitlistForm />
              <a href="#" className="flex items-center text-gray-400 hover:text-white transition-colors duration-200 group text-sm">
                See what tasks you can delegate
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform duration-200" />
              </a>
            </div>
          </div>
        </div>
        
        {/* Agent capabilities */}
        <div className="container mx-auto px-6 pb-12">
          <div className="flex justify-center items-center space-x-12 text-center text-gray-500 text-sm">
            <div>
              <span className="text-2xl font-light text-white block">Scout</span>
              <span className="text-xs">Players automatically</span>
            </div>
            <div className="w-px h-8 bg-gray-700"></div>
            <div>
              <span className="text-2xl font-light text-white block">Train</span>
              <span className="text-xs">Models hands-free</span>
            </div>
            <div className="w-px h-8 bg-gray-700"></div>
            <div>
              <span className="text-2xl font-light text-white block">Research</span>
              <span className="text-xs">While you sleep</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Custom CSS animations */}
      <style jsx>{`
        @keyframes float {
          0%, 100% {
            transform: translateY(0px) translateX(0px);
            opacity: 0.3;
          }
          25% {
            transform: translateY(-20px) translateX(10px);
            opacity: 0.7;
          }
          50% {
            transform: translateY(-10px) translateX(-8px);
            opacity: 0.4;
          }
          75% {
            transform: translateY(-25px) translateX(15px);
            opacity: 0.6;
          }
        }
        
        @keyframes floatSlow {
          0%, 100% {
            transform: translateY(0px) translateX(0px) scale(1);
            opacity: 0.1;
          }
          33% {
            transform: translateY(-40px) translateX(25px) scale(1.2);
            opacity: 0.3;
          }
          66% {
            transform: translateY(-20px) translateX(-15px) scale(0.8);
            opacity: 0.2;
          }
        }
        
        @keyframes twinkle {
          0%, 100% {
            opacity: 0.2;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.2);
          }
        }
        
        @keyframes moveGrid {
          0% {
            transform: translate(0, 0);
          }
          100% {
            transform: translate(50px, 50px);
          }
        }
      `}</style>
    </div>
  );
}