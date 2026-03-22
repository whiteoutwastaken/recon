"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { Competitor } from "@/app/page";
import { X } from "lucide-react";
import { fetchEvents } from "@/lib/api";

const months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"];

const eventTypeColors: Record<string, string> = {
  product_launch: "bg-foreground",
  funding: "bg-foreground/70",
  pricing_change: "bg-warning",
  hire_surge: "bg-foreground/50",
  controversy: "bg-destructive",
  news: "bg-muted-foreground",
  partnership: "bg-foreground/60",
  earnings: "bg-foreground/40",
};

const eventTypeLabels: Record<string, string> = {
  product_launch: "Product Launch",
  funding: "Funding",
  pricing_change: "Pricing Change",
  hire_surge: "Hiring Surge",
  controversy: "Controversy",
  news: "News",
  partnership: "Partnership",
  earnings: "Earnings",
};

export function EventTimeline({ competitor }: { competitor: Competitor }) {
  const [events, setEvents] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchEvents(competitor.id)
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [competitor.id]);

  const sorted = [...events].sort((a, b) => a.date.localeCompare(b.date));
  const minDate = sorted.length ? new Date(sorted[0].date).getTime() : 0;
  const maxDate = sorted.length ? new Date(sorted[sorted.length - 1].date).getTime() : 1;
  const range = maxDate - minDate || 1;

  const getLeft = (date: string) => ((new Date(date).getTime() - minDate) / range) * 96 + 2;

  return (
    <div className="bg-card border border-border rounded-xl p-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Event Timeline</h3>
          <p className="text-sm text-muted-foreground mt-0.5">12-month activity for {competitor.name}</p>
        </div>
      </div>

      {loading ? (
        <div className="h-24 bg-secondary/30 rounded-lg animate-pulse" />
      ) : events.length === 0 ? (
        <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">No events yet</div>
      ) : (
        <>
          <div className="relative h-24 mb-4">
            <div className="absolute left-0 right-0 top-1/2 h-px bg-border" />
            <div className="absolute left-0 right-0 bottom-0 flex justify-between text-xs text-muted-foreground">
              {months.map((m) => <span key={m} className="w-8 text-center">{m}</span>)}
            </div>
            {sorted.slice(0, 20).map((e) => {
              const left = getLeft(e.date);
              const colorClass = eventTypeColors[e.event_type] || "bg-muted-foreground";
              return (
                <button
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className={cn("absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full hover:scale-125 hover:ring-2 hover:ring-foreground/30 transition-all duration-200", colorClass)}
                  style={{ left: `${left}%` }}
                  title={e.title}
                />
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground border-t border-border pt-4">
            {Object.entries(eventTypeLabels).map(([type, label]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className={cn("w-2.5 h-2.5 rounded-full", eventTypeColors[type] || "bg-muted-foreground")} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {selected && (
        <div className="mt-4 p-4 rounded-lg bg-secondary/50 border border-border animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className={cn("w-2.5 h-2.5 rounded-full", eventTypeColors[selected.event_type] || "bg-muted-foreground")} />
                <span className="text-xs text-muted-foreground">{eventTypeLabels[selected.event_type] || selected.event_type}</span>
                <span className="text-xs text-muted-foreground">|</span>
                <span className="text-xs text-muted-foreground">{selected.date}</span>
              </div>
              <h4 className="text-sm font-semibold text-foreground">{selected.title}</h4>
            </div>
            <button onClick={() => setSelected(null)} className="p-1 rounded hover:bg-secondary transition-colors">
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
          <p className="text-sm text-muted-foreground mb-3">{selected.description}</p>
          <div className="flex items-center gap-3">
            {selected.source_url && <a href={selected.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent hover:underline">Source →</a>}
            <span className={cn("px-2 py-0.5 rounded-md text-xs font-medium", selected.sentiment_score > 0.3 ? "bg-foreground/10 text-foreground" : selected.sentiment_score < -0.3 ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground")}>
              {selected.sentiment_score > 0 ? "+" : ""}{Number(selected.sentiment_score).toFixed(1)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}