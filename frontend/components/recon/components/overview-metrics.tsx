"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { Competitor } from "@/app/page";
import { TrendingUp, TrendingDown, Building2, Newspaper, Smile, Users, AlertTriangle, Zap } from "lucide-react";
import { fetchMetrics, fetchPatterns } from "@/lib/api";

export function OverviewMetrics({ competitors }: { competitors: Competitor[] }) {
  const [totals, setTotals] = useState({ articles: 0, sentiment: 0, hiring: 0, patterns: 0, alerts: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!competitors.length) { setLoading(false); return; }
    Promise.all([
      ...competitors.map((c) => fetchMetrics(c.id).catch(() => ({}))),
      fetchPatterns().catch(() => []),
    ]).then((results) => {
      const patterns = results[results.length - 1] as any[];
      const metricsArr = results.slice(0, competitors.length) as Record<string, any[]>[];
      
      let totalArticles = 0, totalSentiment = 0, sentimentCount = 0, totalHiring = 0;
      for (const m of metricsArr) {
        const nv = m.news_volume || [];
        if (nv.length) totalArticles += nv[nv.length - 1].value;
        const se = m.sentiment || [];
        if (se.length) { totalSentiment += se[se.length - 1].value; sentimentCount++; }
        const hv = m.hiring_velocity || [];
        if (hv.length) totalHiring += hv[hv.length - 1].value;
      }
      setTotals({
        articles: Math.round(totalArticles),
        sentiment: sentimentCount ? +(totalSentiment / sentimentCount).toFixed(2) : 0,
        hiring: Math.round(totalHiring),
        patterns: patterns.length,
        alerts: patterns.filter((p: any) => (p.confidence || 0) >= 0.8).length,
      });
      setLoading(false);
    });
  }, [competitors]);

  if (loading) return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-24 bg-secondary/30 rounded-xl animate-pulse" />)}
    </div>
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard title="Competitors Tracked" value={`${competitors.length}`} change="" trend="neutral" icon={Building2} delay={0} />
      <MetricCard title="Total Articles" value={`${totals.articles}`} change="" trend="neutral" icon={Newspaper} delay={1} />
      <MetricCard title="Avg Sentiment" value={`${totals.sentiment}`} change="" trend={totals.sentiment >= 0.5 ? "up" : "down"} icon={Smile} delay={2} />
      <MetricCard title="Hiring Signals" value={`${totals.hiring}`} change="" trend="up" icon={Users} delay={3} />
      <MetricCard title="Active Patterns" value={`${totals.patterns}`} change="" trend="neutral" icon={Zap} delay={4} />
      <MetricCard title="Critical Alerts" value={`${totals.alerts}`} change="" trend="alert" icon={AlertTriangle} isAlert delay={5} />
    </div>
  );
}

function MetricCard({ title, value, change, trend, icon: Icon, isAlert = false, delay = 0 }: any) {
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
        <span className={cn("text-xl font-bold tracking-tight", isAlert && Number(value) > 0 ? "text-destructive" : "text-foreground")}>{value}</span>
        {change && (
          <div className={cn("flex items-center gap-0.5 text-xs font-medium mt-0.5", trend === "up" && "text-foreground/70", trend === "down" && "text-destructive", trend === "neutral" && "text-muted-foreground")}>
            {trend === "up" && <TrendingUp className="w-3 h-3" />}
            {trend === "down" && <TrendingDown className="w-3 h-3" />}
            <span>{change}</span>
          </div>
        )}
      </div>
    </div>
  );
}