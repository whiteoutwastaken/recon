"use client";

import { useEffect, useState } from "react";
import type { Competitor } from "@/app/page";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from "recharts";
import { fetchCompare } from "@/lib/api";

const competitorColors = [
  "oklch(0.7 0.18 160)",
  "oklch(0.65 0.18 30)",
  "oklch(0.7 0.18 220)",
  "oklch(0.65 0.18 260)",
  "oklch(0.7 0.18 55)",
];

const DIMENSIONS = ["headcount", "hiring_velocity", "sentiment", "news_volume", "funding"];
const LABELS = ["Headcount", "Hiring", "Sentiment", "News", "Funding"];

export function RadarComparison({ competitors }: { competitors: Competitor[] }) {
  const [radarData, setRadarData] = useState<any[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!competitors.length) { setLoading(false); return; }
    setActive(competitors.slice(0, 3).map((c) => c.name));
    fetchCompare(competitors.map((c) => c.id))
      .then((data) => {
        // Normalize each metric to 0-100 across competitors
        const normalized: any[] = LABELS.map((label, di) => {
          const dim = DIMENSIONS[di];
          const row: any = { dimension: label };
          const vals = Object.values(data).map((d: any) => d.latest_metrics[dim] || 0);
          const max = Math.max(...vals, 1);
          Object.entries(data).forEach(([id, d]: any) => {
            const comp = competitors.find((c) => c.id === id);
            if (comp) row[comp.name] = +((d.latest_metrics[dim] || 0) / max * 100).toFixed(1);
          });
          return row;
        });
        setRadarData(normalized);
      })
      .catch(() => setRadarData([]))
      .finally(() => setLoading(false));
  }, [competitors]);

  const toggle = (name: string) => {
    setActive((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]);
  };

  return (
    <div className="bg-card border border-border rounded-xl p-5 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Competitive Landscape</h3>
          <p className="text-sm text-muted-foreground mt-0.5">Multi-dimensional comparison across key metrics</p>
        </div>
      </div>

      {/* Toggles */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {competitors.map((c, i) => {
          const isActive = active.includes(c.name);
          const color = competitorColors[i % competitorColors.length];
          return (
            <button key={c.id} onClick={() => toggle(c.name)} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${isActive ? "bg-secondary text-foreground border border-foreground/30" : "bg-secondary/50 text-muted-foreground border border-transparent hover:border-border"}`} style={{ borderColor: isActive ? color : undefined }}>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                {c.name}
              </span>
            </button>
          );
        })}
      </div>

      <div className="h-[350px]">
        {loading ? (
          <div className="h-full bg-secondary/30 rounded-lg animate-pulse" />
        ) : radarData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">No comparison data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
              <PolarGrid stroke="oklch(0.22 0.005 260)" />
              <PolarAngleAxis dataKey="dimension" tick={{ fill: "oklch(0.65 0 0)", fontSize: 12 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "oklch(0.5 0 0)", fontSize: 10 }} tickCount={5} />
              {competitors.filter((c) => active.includes(c.name)).map((c, i) => {
                const color = competitorColors[competitors.indexOf(c) % competitorColors.length];
                return (
                  <Radar key={c.id} name={c.name} dataKey={c.name} stroke={color} fill={color} fillOpacity={0.2} strokeWidth={2} />
                );
              })}
              <Legend wrapperStyle={{ paddingTop: 20 }} iconType="circle" iconSize={8} />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-5 gap-4 mt-4 pt-4 border-t border-border">
        {[["Headcount","Team size"],["Hiring","Velocity"],["Sentiment","Perception"],["News","Coverage"],["Funding","Capital"]].map(([d, s]) => (
          <div key={d} className="text-center">
            <span className="text-xs font-medium text-foreground">{d}</span>
            <p className="text-xs text-muted-foreground mt-0.5">{s}</p>
          </div>
        ))}
      </div>
    </div>
  );
}