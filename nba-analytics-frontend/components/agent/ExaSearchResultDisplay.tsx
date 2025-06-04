"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Separator } from '@/components/ui/separator';
import { 
  ExternalLink, 
  Calendar, 
  Star, 
  Globe, 
  Search, 
  ChevronDown, 
  ChevronUp,
  TrendingUp,
  Zap,
  Clock
} from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ExaSearchResult {
  rank: number;
  title: string;
  url: string;
  domain?: string;
  published_date?: string;
  score?: number;
  text?: string;
  nba_relevance_score?: number;
}

export interface ExaSearchData {
  query?: string;
  original_query?: string;
  enhanced_query?: string;
  num_results?: number;
  category?: string;
  search_type?: string;
  domains_searched?: string[];
  results: ExaSearchResult[];
  error?: string;
}

interface ExaSearchResultDisplayProps {
  data: ExaSearchData;
  toolName: string;
  isError?: boolean;
}

const SearchResultCard: React.FC<{ result: ExaSearchResult; index: number }> = ({ result, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), index * 150);
    return () => clearTimeout(timer);
  }, [index]);

  const formatDate = (dateString?: string) => {
    if (!dateString) return null;
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  const getDomainFavicon = (domain?: string) => {
    if (!domain) return null;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;
  };

  const getScoreColor = (score?: number) => {
    if (!score) return 'text-muted-foreground';
    if (score > 0.7) return 'text-green-600 dark:text-green-400';
    if (score > 0.4) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  const getRelevanceColor = (relevanceScore?: number) => {
    if (!relevanceScore) return 'text-muted-foreground';
    if (relevanceScore >= 5) return 'text-blue-600 dark:text-blue-400';
    if (relevanceScore >= 3) return 'text-purple-600 dark:text-purple-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  return (
    <Card className={cn(
      "transition-all duration-300 hover:shadow-md border-l-4",
      "border-l-blue-500/30 hover:border-l-blue-500",
      isVisible ? "animate-fade-in-up opacity-100" : "opacity-0 translate-y-4"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="secondary" className="text-xs">
                #{result.rank}
              </Badge>
              {result.domain && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <img 
                    src={getDomainFavicon(result.domain)} 
                    alt="" 
                    className="w-4 h-4"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                  <Globe className="w-3 h-3" />
                  <span className="font-medium">{result.domain}</span>
                </div>
              )}
            </div>
            <h3 className="text-sm font-semibold leading-tight text-foreground line-clamp-2 mb-2">
              {result.title}
            </h3>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {result.published_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  <span>{formatDate(result.published_date)}</span>
                </div>
              )}
              {result.score && (
                <div className="flex items-center gap-1">
                  <Star className={cn("w-3 h-3", getScoreColor(result.score))} />
                  <span className={getScoreColor(result.score)}>
                    {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
              )}
              {result.nba_relevance_score && (
                <div className="flex items-center gap-1">
                  <TrendingUp className={cn("w-3 h-3", getRelevanceColor(result.nba_relevance_score))} />
                  <span className={getRelevanceColor(result.nba_relevance_score)}>
                    NBA: {result.nba_relevance_score}
                  </span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              asChild
              className="h-8 px-3 text-xs"
            >
              <a 
                href={result.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-1.5"
              >
                <ExternalLink className="w-3 h-3" />
                Visit
              </a>
            </Button>
          </div>
        </div>
      </CardHeader>
      
      {result.text && (
        <CardContent className="pt-0">
          <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
            <CollapsibleTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm" 
                className="w-full justify-between text-xs h-8 px-2"
              >
                <span className="flex items-center gap-1.5">
                  <Zap className="w-3 h-3" />
                  {isExpanded ? 'Hide content' : 'Show content preview'}
                </span>
                {isExpanded ? 
                  <ChevronUp className="w-3 h-3" /> : 
                  <ChevronDown className="w-3 h-3" />
                }
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="animate-collapsible-down mt-2">
              <div className="bg-muted/30 rounded-lg p-3 border">
                <p className="text-xs leading-relaxed text-muted-foreground line-clamp-6">
                  {result.text}
                </p>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </CardContent>
      )}
    </Card>
  );
};

export const ExaSearchResultDisplay: React.FC<ExaSearchResultDisplayProps> = ({ 
  data, 
  toolName, 
  isError = false 
}) => {
  const [isMetaExpanded, setIsMetaExpanded] = useState(false);

  if (isError || data.error) {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-950/30 p-4">
        <div className="flex items-center gap-2 text-red-700 dark:text-red-400 mb-2">
          <Search className="w-4 h-4" />
          <span className="font-semibold">Search Error</span>
        </div>
        <p className="text-sm text-red-600 dark:text-red-300">
          {data.error || 'Failed to perform search'}
        </p>
      </div>
    );
  }

  if (!data.results || data.results.length === 0) {
    return (
      <div className="rounded-lg border border-yellow-200 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-950/30 p-4">
        <div className="flex items-center gap-2 text-yellow-700 dark:text-yellow-400 mb-2">
          <Search className="w-4 h-4" />
          <span className="font-semibold">No Results</span>
        </div>
        <p className="text-sm text-yellow-600 dark:text-yellow-300">
          No search results found for "{data.query || data.original_query}"
        </p>
      </div>
    );
  }

  const isNBASearch = toolName === 'exa_nba_search';
  const searchIcon = isNBASearch ? TrendingUp : Globe;
  const searchLabel = isNBASearch ? 'NBA Search Results' : 'Web Search Results';
  const themeColor = isNBASearch ? 'blue' : 'green';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className={cn(
        "rounded-lg border p-4",
        themeColor === 'blue' 
          ? "border-blue-200 dark:border-blue-700 bg-gradient-to-r from-blue-50 to-blue-50/80 dark:from-blue-950/40 dark:to-blue-900/20"
          : "border-green-200 dark:border-green-700 bg-gradient-to-r from-green-50 to-green-50/80 dark:from-green-950/40 dark:to-green-900/20"
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "p-2 rounded-lg",
              themeColor === 'blue' 
                ? "bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300"
                : "bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300"
            )}>
              {React.createElement(searchIcon, { className: "w-5 h-5" })}
            </div>
            <div>
              <h3 className={cn(
                "font-semibold text-sm",
                themeColor === 'blue' 
                  ? "text-blue-800 dark:text-blue-200"
                  : "text-green-800 dark:text-green-200"
              )}>
                {searchLabel}
              </h3>
              <p className="text-xs text-muted-foreground">
                {data.results.length} result{data.results.length !== 1 ? 's' : ''} found
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {data.query || data.original_query}
            </Badge>
            {data.results.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsMetaExpanded(!isMetaExpanded)}
                className="h-7 px-2 text-xs"
              >
                Details
                {isMetaExpanded ? 
                  <ChevronUp className="w-3 h-3 ml-1" /> : 
                  <ChevronDown className="w-3 h-3 ml-1" />
                }
              </Button>
            )}
          </div>
        </div>

        {/* Search Metadata */}
        <Collapsible open={isMetaExpanded} onOpenChange={setIsMetaExpanded}>
          <CollapsibleContent className="animate-collapsible-down">
            <Separator className="my-3" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {data.enhanced_query && data.enhanced_query !== data.original_query && (
                <div>
                  <span className="font-medium text-muted-foreground">Enhanced Query:</span>
                  <p className="mt-1 font-mono bg-background/50 rounded px-2 py-1">
                    {data.enhanced_query}
                  </p>
                </div>
              )}
              {data.search_type && (
                <div>
                  <span className="font-medium text-muted-foreground">Search Type:</span>
                  <p className="mt-1 capitalize">{data.search_type}</p>
                </div>
              )}
              {data.domains_searched && data.domains_searched.length > 0 && (
                <div className="md:col-span-2">
                  <span className="font-medium text-muted-foreground">Domains Searched:</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {data.domains_searched.map((domain) => (
                      <Badge key={domain} variant="secondary" className="text-xs">
                        {domain}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      {/* Results */}
      <div className="space-y-3">
        {data.results.map((result, index) => (
          <SearchResultCard 
            key={`${result.url}-${index}`} 
            result={result} 
            index={index} 
          />
        ))}
      </div>

      {/* Footer */}
      {data.results.length > 0 && (
        <div className="flex items-center justify-center pt-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="w-3 h-3" />
            <span>Results powered by Exa AI</span>
          </div>
        </div>
      )}
    </div>
  );
};