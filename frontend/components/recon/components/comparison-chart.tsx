"use client";

import { useEffect, useState } from "react";
import type { Competitor } from "@/app/page";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { fetchMetrics } from "@/lib/api";

type MetricType = "hiring_velocity" | "news_volume" | "sentiment";
const metricLabels: Record<MetricType, string> = {
  hiring_velocity: "Hiring Velocity",
  news_volume: "News Volume",
  sentiment: "Sentiment Score",
};

const competitorColors = ["oklch(0.7 0.18 160)", "oklch(0.65 0.18 30)", "oklch(0.7 0.18 220)", "oklch(0.65 0.18 260)", "oklch(0.7 0.18 55)"];

export function ComparisonChart({ competitors }: { competitors: Competitor[] }) {
  const [metric, setMetric] = useState<MetricType>("hiring_velocity");
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!competitors.length) { setLoading(false); return; }
    setLoading(true);
    Promise.all(competitors.map((c) => fetchMetrics(c.id).catch(() => ({})))).then((allMetrics) => {
      // Build unified date index
      const dateSet = new Set<string>();
      allMetrics.forEach((m: any) => (m[metric] || []).forEach((d: any) => dateSet.add(d.date)));
      const dates = Array.from(dateSet).sort();

      const data = dates.map((date) => {
        const row: any = { date: date.slice(0, 7) };
        competitors.forEach((c, i) => {
          const series: any[] = allMetrics[i][metric] || [];
          const point = series.find((d: any) => d.date === date);
          if (point) row[c.name] = point.value;
        });
        return row;
      });
      setChartData(data);
      setLoading(false);
    });
  }, [competitors, metric]);

  const fmt = (v: number) => metric === "sentiment" ? v.toFixed(2) : v.toFixed(0);

  return (
    <div className="bg-card border border-border rounded-xl p-5 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-base font-semibold text-foreground">Competitor Comparison</h3>
          <p className="text-sm text-muted-foreground mt-0.5">12-month trend comparison across all competitors</p>
        </div>
        <select value={metric} onChange={(e) => setMetric(e.target.value as MetricType)} className="h-9 px-3 rounded-lg bg-secondary border border-border text-sm text-foreground focus:outline-none transition-all">
          {Object.entries(metricLabels).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <div className="h-[320px]">
        {loading ? (
          <div className="h-full bg-secondary/30 rounded-lg animate-pulse" />
        ) : chartData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">No data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.22 0.005 260)" vertical={false} />
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} dy={10} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickFormatter={fmt} dx={-10} domain={metric === "sentiment" ? [0, 1] : undefined} />
              <Tooltip contentStyle={{ backgroundColor: "oklch(0.12 0.005 260)", border: "1px solid oklch(0.22 0.005 260)", borderRadius: "8px", fontSize: "12px" }} labelStyle={{ color: "oklch(0.95 0 0)", fontWeight: 600 }} formatter={(v: number) => [fmt(v), ""]} />
              <Legend wrapperStyle={{ paddingTop: 20 }} iconType="circle" iconSize={8} />
              {competitors.map((c, i) => (
                <Line key={c.id} type="monotone" dataKey={c.name} stroke={competitorColors[i % competitorColors.length]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}