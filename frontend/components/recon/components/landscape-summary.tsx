"use client";

import { useEffect, useState } from "react";
import type { Competitor } from "@/app/page";
import { Sparkles, Clock, RefreshCw } from "lucide-react";
import { fetchBriefing, queryAgent } from "@/lib/api";

export function LandscapeSummary({ competitors }: { competitors: Competitor[] }) {
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("Loading...");

  const load = async () => {
    setLoading(true);
    try {
      // Try briefing endpoint first (uses real data), fall back to agent query
      const data = await fetchBriefing();
      setSummary(data.text || data.response || "");
      setLastUpdated("Just now");
    } catch {
      try {
        const data = await queryAgent("Give me a comprehensive competitive landscape summary covering all tracked competitors — key trends, patterns, and strategic predictions.");
        setSummary(data.answer || "");
        setLastUpdated("Just now");
      } catch {
        setSummary("Could not generate summary. Make sure the backend is running.");
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    if (competitors.length) load();
    else setLoading(false);
  }, [competitors.length]);

  return (
    <div className="bg-card border border-border rounded-xl p-6 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-300">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">Competitive Landscape Summary</h3>
            <p className="text-sm text-muted-foreground">AI-generated executive briefing</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            {lastUpdated}
          </div>
          <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-secondary text-foreground hover:bg-secondary/80 transition-all disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-4 bg-secondary/40 rounded animate-pulse" style={{ width: `${85 + Math.random() * 15}%` }} />
          ))}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
          {summary || "No data available yet. Run an ingest to populate competitor data."}
        </div>
      )}
    </div>
  );
}