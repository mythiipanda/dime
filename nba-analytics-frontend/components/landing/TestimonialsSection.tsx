"use client";

import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Quote } from 'lucide-react'; // Using a quote icon

// Single featured testimonial
const featuredTestimonial = {
  quote: "This app has completely transformed how I manage my tasks. With its smart reminders and automated workflows, I'm accomplishing more in less time. It's been a game-changer for my productivity!",
  name: "Emma Johnson",
  position: "Project Manager, Tech Solutions Inc.",
  avatarSrc: "/img/placeholder/avatar-emma.jpg", // Replace with actual path or use a generic icon
  avatarFallback: "EJ",
};

export function TestimonialsSection() {
  return (
    // Dark theme background
    <section id="testimonials" className="py-16 md:py-24 bg-gray-950"> 
      <div className="container mx-auto max-w-4xl px-4">
        <div className="text-center mb-12 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
          {/* Light text */}
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
            How Our Users Enhance Their Analysis
          </h2>
        </div>

        {/* Dark theme card */}
        <div className="bg-gradient-to-br from-gray-800/60 via-gray-900/50 to-blue-900/40 backdrop-blur-md p-8 md:p-12 rounded-xl shadow-xl border border-white/10 animate-in fade-in-0 slide-in-from-bottom-5 duration-500 delay-100">
          <div className="flex flex-col items-center text-center">
            {/* Accent color icon */}
            <Quote className="h-10 w-10 text-cyan-400 mb-6" /> 
            {/* Light text */}
            <p className="text-xl md:text-2xl font-medium text-gray-200 leading-relaxed mb-8">
              &ldquo;{featuredTestimonial.quote}&rdquo;
            </p>
            <div className="flex items-center">
              {/* Adjusted avatar for dark */}
              <Avatar className="h-12 w-12 mr-4 border-2 border-blue-400/50">
                <AvatarImage src={featuredTestimonial.avatarSrc} alt={featuredTestimonial.name} />
                {/* Darker fallback */}
                <AvatarFallback className="bg-gray-700 text-gray-300">{featuredTestimonial.avatarFallback}</AvatarFallback>
              </Avatar>
              <div>
                {/* Light text */}
                <p className="font-semibold text-white">{featuredTestimonial.name}</p>
                <p className="text-sm text-gray-400">{featuredTestimonial.position}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}