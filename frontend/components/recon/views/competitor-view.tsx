"use client";

import type { Competitor } from "@/app/page";
import { CompetitorMetrics } from "../components/competitor-metrics";
import { EventTimeline } from "../components/event-timeline";
import { TrendChart } from "../components/trend-chart";
import { IntelFeed } from "../components/intel-feed";
import { PatternAlerts } from "../components/pattern-alerts";

interface CompetitorViewProps {
  competitor: Competitor;
}

export function CompetitorView({ competitor }: CompetitorViewProps) {
  return (
    <div className="space-y-6">
      {/* Row 1: Metric cards */}
      <CompetitorMetrics competitor={competitor} />

      {/* Row 2: Event timeline */}
      <EventTimeline competitor={competitor} />

      {/* Row 3: Split columns */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3">
          <TrendChart competitor={competitor} />
        </div>
        <div className="lg:col-span-2">
          <IntelFeed competitor={competitor} />
        </div>
      </div>

      {/* Row 4: Pattern alerts */}
      <PatternAlerts competitor={competitor} />
    </div>
  );
}
