"use client";

import { useEffect, useState } from "react";
import type { Competitor } from "@/app/page";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { fetchMetrics, fetchTrendProjection } from "@/lib/api";

type MetricKey = "hiring_velocity" | "news_volume" | "sentiment" | "headcount";

const metricLabels: Record<MetricKey, string> = {
  hiring_velocity: "Hiring Velocity",
  news_volume: "News Volume",
  sentiment: "Sentiment Score",
  headcount: "Headcount",
};

export function TrendChart({ competitor }: { competitor: Competitor }) {
  const [metric, setMetric] = useState<MetricKey>("hiring_velocity");
  const [chartData, setChartData] = useState<any[]>([]);
  const [insight, setInsight] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchMetrics(competitor.id).catch(() => ({})),
      fetchTrendProjection(competitor.id, metric).catch(() => null),
    ]).then(([metrics, trend]) => {
      const series: { date: string; value: number }[] = metrics[metric] || [];
      
      if (trend && trend.projected) {
        // Merge historical + projected from trend agent
        const historical = (trend.historical || series.map((d: any) => d.value)).map((v: number, i: number) => ({
          month: series[i]?.date?.slice(0, 7) || `M${i}`,
          actual: v,
        }));
        const projMonths: string[] = trend.projected_months || [];
        const projected = (trend.projected || []).map((v: number, i: number) => ({
          month: projMonths[i] || `P+${i + 1}`,
          projected: v,
          lower: trend.confidence_lower?.[i],
          upper: trend.confidence_upper?.[i],
        }));
        setChartData([...historical, ...projected]);
        setInsight(trend.interpretation || "");
      } else {
        // Fallback: just show historical, compute simple projection
        const values = series.map((d: any) => d.value);
        const n = values.length;
        const xm = (n - 1) / 2;
        const ym = values.reduce((a: number, b: number) => a + b, 0) / (n || 1);
        const slope = values.reduce((s: number, y: number, i: number) => s + (i - xm) * (y - ym), 0) /
          (values.reduce((s: number, _: number, i: number) => s + (i - xm) ** 2, 0) || 1);
        const ic = ym - slope * xm;

        const historical = series.map((d: any) => ({ month: d.date?.slice(0, 7), actual: d.value }));
        const projected = [1, 2, 3].map((j) => ({
          month: `P+${j}`,
          projected: +(ic + slope * (n + j - 1)).toFixed(2),
        }));
        setChartData([...historical, ...projected]);
        setInsight("");
      }
      setLoading(false);
    });
  }, [competitor.id, metric]);

  const isSentiment = metric === "sentiment";
  const fmt = (v: number) => isSentiment ? v.toFixed(2) : v.toFixed(0);

  return (
    <div className="bg-card border border-border rounded-xl p-5 h-full animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-base font-semibold text-foreground">Trend Analysis</h3>
          <p className="text-sm text-muted-foreground mt-0.5">Historical data with projections</p>
        </div>
        <select value={metric} onChange={(e) => setMetric(e.target.value as MetricKey)} className="h-9 px-3 rounded-lg bg-secondary border border-border text-sm text-foreground focus:outline-none transition-all">
          {Object.entries(metricLabels).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="h-[220px] bg-secondary/30 rounded-lg animate-pulse" />
      ) : chartData.length === 0 ? (
        <div className="h-[220px] flex items-center justify-center text-muted-foreground text-sm">No data yet</div>
      ) : (
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.75 0 0)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="oklch(0.75 0 0)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.22 0.005 260)" vertical={false} />
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} dy={10} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickFormatter={fmt} dx={-10} domain={isSentiment ? [0, 1] : undefined} />
              <Tooltip contentStyle={{ backgroundColor: "oklch(0.12 0.005 260)", border: "1px solid oklch(0.22 0.005 260)", borderRadius: "8px", fontSize: "12px" }} labelStyle={{ color: "oklch(0.95 0 0)", fontWeight: 600 }} formatter={(v: number) => [fmt(v), ""]} />
              <Area type="monotone" dataKey="actual" stroke="oklch(0.75 0 0)" strokeWidth={2} fill="url(#actualGrad)" dot={{ fill: "oklch(0.75 0 0)", r: 3 }} />
              <Area type="monotone" dataKey="projected" stroke="oklch(0.55 0 0)" strokeWidth={2} strokeDasharray="5 5" fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="flex items-center gap-6 mt-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2"><div className="w-8 h-0.5 bg-foreground/70" /><span>Actual</span></div>
        <div className="flex items-center gap-2"><div className="w-8 h-0.5 bg-muted-foreground" style={{ backgroundImage: "repeating-linear-gradient(90deg, oklch(0.55 0 0) 0 4px, transparent 4px 8px)" }} /><span>Projected</span></div>
      </div>

      {insight && (
        <div className="mt-4 p-3 rounded-lg bg-secondary/50 border border-border">
          <p className="text-xs text-muted-foreground leading-relaxed">{insight}</p>
        </div>
      )}
    </div>
  );
}