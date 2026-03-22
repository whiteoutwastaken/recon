"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { Competitor } from "@/app/page";
import { ExternalLink } from "lucide-react";
import { fetchIntel } from "@/lib/api";

export function IntelFeed({ competitor }: { competitor: Competitor }) {
  const [intel, setIntel] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchIntel(competitor.id)
      .then(setIntel)
      .catch(() => setIntel([]))
      .finally(() => setLoading(false));
  }, [competitor.id]);

  return (
    <div className="bg-card border border-border rounded-xl p-5 h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Intel Feed</h3>
          <p className="text-sm text-muted-foreground mt-0.5">Latest news & analysis</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1 -mr-1">
        {loading && Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 bg-secondary/30 rounded-lg animate-pulse" />
        ))}

        {!loading && intel.length === 0 && (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">No intel articles yet</div>
        )}

        {!loading && intel.map((item, index) => (
          <a
            key={item.id}
            href={item.source_url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 border border-transparent hover:border-border transition-all duration-200 group animate-in fade-in slide-in-from-right-2"
            style={{ animationDelay: `${index * 50}ms`, animationFillMode: "both" }}
          >
            <div className="flex items-start justify-between gap-2 mb-1">
              <h4 className="text-sm font-medium text-foreground group-hover:text-foreground/80 transition-colors line-clamp-2">{item.title}</h4>
              <ExternalLink className="w-3.5 h-3.5 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
              <span>{item.date}</span>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{item.description}</p>
            <div className="flex items-center justify-between">
              <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium", (item.sentiment_score||0) > 0.3 ? "bg-foreground/10 text-foreground" : (item.sentiment_score||0) < -0.3 ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground")}>
                {(item.sentiment_score||0) > 0 ? "+" : ""}{Number(item.sentiment_score||0).toFixed(1)}
              </span>
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className={cn("w-1 h-1 rounded-full", i < (item.importance_score||0) ? "bg-foreground" : "bg-border")} />
                ))}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}