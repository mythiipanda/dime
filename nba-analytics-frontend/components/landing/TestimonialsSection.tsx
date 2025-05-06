"use client";

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { StarIcon } from 'lucide-react'; // Assuming StarIcon for ratings
import { cn } from '@/lib/utils'; // Import cn

interface Testimonial {
  id: number;
  quote: string;
  name: string;
  position: string;
  avatarSrc?: string;
  avatarFallback: string;
  rating: number; // e.g., 1-5
}

const testimonialsData: Testimonial[] = [
  {
    id: 1,
    quote: "Dime has revolutionized how I analyze game performance. The AI insights are a game-changer!",
    name: "Alex Chen",
    position: "Lead Analyst, Pro Team",
    avatarSrc: "/avatars/alex.png", // Placeholder path
    avatarFallback: "AC",
    rating: 5,
  },
  {
    id: 2,
    quote: "The depth of data and the intuitive interface make Dime an indispensable tool for any serious basketball enthusiast.",
    name: "Maria Rodriguez",
    position: "Fantasy League Champion",
    avatarSrc: "/avatars/maria.png", // Placeholder path
    avatarFallback: "MR",
    rating: 5,
  },
  {
    id: 3,
    quote: "Finally, a platform that combines comprehensive stats with actionable AI predictions. Highly recommended!",
    name: "Sam 'The Statman' Miller",
    position: "Sports Bettor & Podcaster",
    avatarSrc: "/avatars/sam.png", // Placeholder path
    avatarFallback: "SM",
    rating: 4,
  },
];

const StarRating = ({ rating }: { rating: number }) => {
  return (
    <div className="flex items-center">
      {[...Array(5)].map((_, index) => (
        <StarIcon
          key={index}
          className={`h-5 w-5 ${index < rating ? 'text-yellow-400 fill-yellow-400' : 'text-muted-foreground/50'}`}
        />
      ))}
    </div>
  );
};

export function TestimonialsSection() {
  return (
    <section id="testimonials" className="py-24 md:py-32 bg-background/70 text-foreground">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-4">
            Trusted by <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Professionals & Fans</span>
          </h2>
          <p className="text-lg leading-8 text-muted-foreground max-w-2xl mx-auto">
            Hear what our users are saying about Dime.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {testimonialsData.map((testimonial, index) => ( // Added index for animation delay
            <Card key={testimonial.id} className={cn(
              "flex flex-col shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105", // Added hover:scale-105 and transition-all
              "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
            )} style={{ animationDelay: `${index * 100}ms` }}>
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar>
                      <AvatarImage src={testimonial.avatarSrc} alt={testimonial.name} />
                      <AvatarFallback>{testimonial.avatarFallback}</AvatarFallback>
                    </Avatar>
                    <div>
                      <CardTitle className="text-lg">{testimonial.name}</CardTitle>
                      <CardDescription className="text-xs">{testimonial.position}</CardDescription>
                    </div>
                  </div>
                  <StarRating rating={testimonial.rating} />
                </div>
              </CardHeader>
              <CardContent className="flex-grow">
                <p className="text-sm text-foreground/90 leading-relaxed italic">
                  &ldquo;{testimonial.quote}&rdquo;
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}