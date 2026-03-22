"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Search, Mic, RefreshCw } from "lucide-react";
import Image from "next/image";

interface TopBarProps {
  searchQuery: string;
  onSearch: (query: string) => void;
  isSearching: boolean;
  searchProgress: string;
  onRefresh: () => void;
  onVoiceClick: () => void;
}

export function TopBar({
  searchQuery,
  onSearch,
  isSearching,
  searchProgress,
  onRefresh,
  onVoiceClick,
}: TopBarProps) {
  const [inputValue, setInputValue] = useState(searchQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(inputValue);
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-border bg-background/95 backdrop-blur-sm flex items-center justify-between px-6">
      {/* Left: Logo */}
      <div className="flex items-center gap-3 min-w-[200px]">
        <div className="w-9 h-9 rounded-lg bg-white flex items-center justify-center overflow-hidden">
          <Image
            src="/logo.png"
            alt="Recon Logo"
            width={32}
            height={32}
            className="object-cover"
          />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-bold text-lg text-foreground tracking-tight">RECON</span>
          <span className="text-xs text-muted-foreground hidden sm:inline">agentic competitive intelligence</span>
        </div>
      </div>

      {/* Center: Search */}
      <div className="flex-1 max-w-2xl mx-8">
        <form onSubmit={handleSubmit} className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Enter a market: AI foundation models, autonomous vehicles, CRM software..."
            className="w-full h-11 pl-12 pr-4 rounded-xl bg-secondary border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-accent transition-all duration-200"
          />
          {isSearching && (
            <div className="absolute inset-x-0 -bottom-8 flex items-center justify-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-foreground border-t-transparent animate-spin" />
              <span className="text-xs text-foreground font-medium">{searchProgress}</span>
            </div>
          )}
        </form>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3 min-w-[200px] justify-end">
        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isSearching}
          className={cn(
            "w-10 h-10 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-all duration-200",
            isSearching && "animate-spin text-foreground"
          )}
          title="Refresh data"
        >
          <RefreshCw className="w-5 h-5" />
        </button>

        {/* Voice agent button */}
        <button
          onClick={onVoiceClick}
          className="relative w-10 h-10 flex items-center justify-center rounded-full bg-foreground text-background hover:bg-foreground/90 transition-all duration-200 group"
          title="Talk to Recon"
        >
          <Mic className="w-5 h-5" />
          <span className="absolute inset-0 rounded-full bg-foreground/50 animate-ping opacity-30 group-hover:opacity-50" />
        </button>
      </div>
    </header>
  );
}
