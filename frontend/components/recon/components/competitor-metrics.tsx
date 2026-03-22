"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { Competitor } from "@/app/page";
import { TrendingUp, TrendingDown, Users, Newspaper, Smile, Package, Banknote, AlertTriangle } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { fetchMetrics, fetchPatterns } from "@/lib/api";

interface CompetitorMetricsProps {
  competitor: Competitor;
}

export function CompetitorMetrics({ competitor }: CompetitorMetricsProps) {
  const [metrics, setMetrics] = useState<Record<string, { date: string; value: number }[]>>({});
  const [patternCount, setPatternCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchMetrics(competitor.id).catch(() => ({})),
      fetchPatterns(competitor.id).catch(() => []),
    ]).then(([m, p]) => {
      setMetrics(m);
      setPatternCount(Array.isArray(p) ? p.length : 0);
      setLoading(false);
    });
  }, [competitor.id]);

  const getSeries = (key: string) => metrics[key] || [];

  const getLatest = (key: string) => {
    const s = getSeries(key);
    return s.length ? s[s.length - 1].value : null;
  };

  const getDelta = (key: string) => {
    const s = getSeries(key);
    if (s.length < 2) return null;
    const latest = s[s.length - 1].value;
    const prev = s[s.length - 2].value;
    return prev !== 0 ? ((latest - prev) / Math.abs(prev)) * 100 : 0;
  };

  const sparkline = (key: string) => getSeries(key).map((d) => ({ value: d.value }));

  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-xl p-4 h-24 animate-pulse" />
        ))}
      </div>
    );
  }

  const hv = getLatest("hiring_velocity");
  const hvDelta = getDelta("hiring_velocity");
  const nv = getLatest("news_volume");
  const nvDelta = getDelta("news_volume");
  const se = getLatest("sentiment");
  const seDelta = getDelta("sentiment");
  const fn = getLatest("funding");

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard title="Hiring Velocity" value={hv !== null ? `${Math.round(hv)}/mo` : "—"} change={hvDelta !== null ? `${hvDelta > 0 ? "+" : ""}${hvDelta.toFixed(0)}%` : ""} trend={hvDelta !== null ? (hvDelta > 0 ? "up" : "down") : "neutral"} icon={Users} sparkline={sparkline("hiring_velocity")} delay={0} />
      <MetricCard title="News Volume" value={nv !== null ? `${Math.round(nv)}` : "—"} change={nvDelta !== null ? `${nvDelta > 0 ? "+" : ""}${nvDelta.toFixed(0)}%` : ""} trend={nvDelta !== null ? (nvDelta > 0 ? "up" : "down") : "neutral"} icon={Newspaper} sparkline={sparkline("news_volume")} delay={1} />
      <MetricCard title="Sentiment" value={se !== null ? se.toFixed(2) : "—"} change={seDelta !== null ? `${seDelta > 0 ? "+" : ""}${seDelta.toFixed(2)}` : ""} trend={seDelta !== null ? (seDelta > 0 ? "up" : "down") : "neutral"} icon={Smile} sparkline={sparkline("sentiment")} sentimentValue={se ?? undefined} delay={2} />
      <MetricCard title="Total Funding" value={fn !== null ? `$${(fn / 1e9).toFixed(1)}B` : "—"} change="" trend="neutral" icon={Banknote} delay={4} />
      <MetricCard title="Active Alerts" value={`${patternCount}`} change="" trend="alert" icon={AlertTriangle} isAlert delay={5} />
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral" | "alert";
  icon: React.ElementType;
  sparkline?: { value: number }[];
  sentimentValue?: number;
  isAlert?: boolean;
  delay?: number;
}

function MetricCard({ title, value, change, trend, icon: Icon, sparkline = [], sentimentValue, isAlert = false, delay = 0 }: MetricCardProps) {
  const getSentimentColor = (val: number) => val >= 0.6 ? "text-foreground" : val >= 0.3 ? "text-muted-foreground" : "text-destructive";

  return (
    <div className="group relative bg-card border border-border rounded-xl p-4 hover:border-foreground/30 transition-all duration-300 overflow-hidden animate-in fade-in slide-in-from-bottom-4" style={{ animationDelay: `${delay * 80}ms`, animationFillMode: "both" }}>
      <div className="absolute inset-0 bg-gradient-to-br from-foreground/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <div className="relative">
        <div className="flex items-start justify-between mb-2">
          <span className="text-xs text-muted-foreground font-medium">{title}</span>
          <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center transition-colors duration-300", isAlert ? "bg-destructive/10" : "bg-secondary group-hover:bg-foreground/10")}>
            <Icon className={cn("w-3.5 h-3.5 transition-colors duration-300", isAlert ? "text-destructive" : "text-muted-foreground group-hover:text-foreground")} />
          </div>
        </div>
        <div className="flex items-end justify-between">
          <div>
            <span className={cn("text-xl font-bold tracking-tight", sentimentValue !== undefined ? getSentimentColor(sentimentValue) : isAlert && Number(value) > 0 ? "text-destructive" : "text-foreground")}>{value}</span>
            {change && (
              <div className={cn("flex items-center gap-0.5 text-xs font-medium mt-0.5", trend === "up" && "text-foreground/70", trend === "down" && "text-destructive", trend === "neutral" && "text-muted-foreground")}>
                {trend === "up" && <TrendingUp className="w-3 h-3" />}
                {trend === "down" && <TrendingDown className="w-3 h-3" />}
                <span>{change}</span>
              </div>
            )}
          </div>
          {sparkline.length > 0 && (
            <div className="w-16 h-8">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sparkline}>
                  <defs>
                    <linearGradient id={`sg-${title}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.75 0 0)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="oklch(0.75 0 0)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="value" stroke="oklch(0.75 0 0)" strokeWidth={1.5} fill={`url(#sg-${title})`} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}