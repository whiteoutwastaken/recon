"use client";

import { cn } from "@/lib/utils";
import type { Competitor, AgentStatus } from "@/app/page";
import { ChevronLeft, ChevronRight, RefreshCw, Zap, FileAudio, Building2 } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface SidebarProps {
  competitors: Competitor[];
  selectedCompetitor: string | null;
  onSelectCompetitor: (id: string | null) => void;
  onRefresh: () => void;
  onDetectPatterns: () => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  agentStatus: AgentStatus;
}

const sentimentColors = {
  positive: "bg-foreground/60",
  neutral: "bg-muted-foreground",
  negative: "bg-destructive",
};

export function Sidebar({ competitors, selectedCompetitor, onSelectCompetitor, onRefresh, onDetectPatterns, collapsed, onCollapsedChange, agentStatus }: SidebarProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <aside className={cn("fixed left-0 top-16 z-40 h-[calc(100vh-64px)] bg-sidebar border-r border-sidebar-border transition-all duration-300 ease-out flex flex-col", collapsed ? "w-[72px]" : "w-[260px]")}>
        {/* Competitors list */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className={cn("flex items-center justify-between mb-6", collapsed && "justify-center")}>
            {!collapsed && (
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                Competitors
                <span className="px-1.5 py-0.5 rounded-md bg-secondary text-xs font-medium">{competitors.length}</span>
              </span>
            )}
            {collapsed && <Building2 className="w-5 h-5 text-muted-foreground" />}
          </div>

          <button
            onClick={() => onSelectCompetitor(null)}
            className={cn("w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-all duration-200 mb-4 relative", selectedCompetitor === null ? "bg-sidebar-accent text-sidebar-foreground" : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50")}
          >
            {selectedCompetitor === null && <span className="absolute left-0 w-1 h-6 rounded-r-full bg-foreground/80" />}
            <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold">All</span>
            </div>
            {!collapsed && <span>All competitors</span>}
          </button>

          <div className="space-y-2">
            {competitors.map((competitor) => (
              <button
                key={competitor.id}
                onClick={() => onSelectCompetitor(competitor.id)}
                className={cn("w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition-all duration-200 group relative", selectedCompetitor === competitor.id ? "bg-sidebar-accent text-sidebar-foreground" : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50")}
              >
                {selectedCompetitor === competitor.id && <span className="absolute left-0 w-1 h-6 rounded-r-full bg-foreground/80" />}
                <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center shrink-0 text-xs font-semibold group-hover:bg-secondary/80 transition-colors">
                  {competitor.name.charAt(0)}
                </div>
                {!collapsed && (
                  <div className="flex-1 text-left min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{competitor.name}</span>
                      <span className={cn("w-2 h-2 rounded-full shrink-0", sentimentColors[competitor.sentiment])} />
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{competitor.description}</p>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Quick actions */}
        <div className="px-4 py-4 border-t border-sidebar-border">
          <div className={cn("flex items-center gap-2", collapsed ? "flex-col" : "justify-center")}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={onRefresh} className="p-2.5 rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-all duration-200">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top"><p>Run full refresh</p></TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={onDetectPatterns} className="p-2.5 rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-all duration-200">
                  <Zap className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top"><p>Detect patterns</p></TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="p-2.5 rounded-lg bg-foreground text-background hover:bg-foreground/90 transition-all duration-200">
                  <FileAudio className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top"><p>Generate briefing</p></TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Collapse */}
        <div className="px-4 py-4 border-t border-sidebar-border">
          <button onClick={() => onCollapsedChange(!collapsed)} className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50 transition-all duration-200">
            {collapsed ? <ChevronRight className="w-5 h-5" /> : <><ChevronLeft className="w-5 h-5" /><span>Collapse</span></>}
          </button>
        </div>
      </aside>
    </TooltipProvider>
  );
}