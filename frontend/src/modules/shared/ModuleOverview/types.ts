import type { ReactNode } from "react";

export type TrendTone = "up" | "down";

export type ModuleKpiAccent = "blue" | "orange" | "purple" | "green" | "red" | "navy";

export type ModuleKpi = {
  id: string;
  label: string;
  value: string;
  trend: string;
  tone: TrendTone;
  accent: ModuleKpiAccent;
  icon: ReactNode;
  spark: number[];
};

export type ModuleHeroAction = {
  id: string;
  label: string;
  primary?: boolean;
  icon: ReactNode;
};

export type ModuleActivity = {
  id: string;
  code: string;
  label: string;
  module: string;
  moduleTone: ModuleKpiAccent;
  time: string;
  status: string;
  statusTone: "blue" | "orange" | "green" | "red";
};

export type ModuleTrendPoint = {
  month: string;
  value: number;
};

export type ModuleTrendSummary = {
  id: string;
  label: string;
  value: string;
  trend: string;
  tone: TrendTone;
};

/** Shared shell config used by every module/submodule overview page. */
export type ModuleOverviewConfig = {
  title: string;
  description: string;
  badgeIcon: ReactNode;
  actions: ModuleHeroAction[];
  kpis: ModuleKpi[];
  activitiesTitle: string;
  activities: ModuleActivity[];
  trendTitle: string;
  trendRangeLabel?: string;
  trend: ModuleTrendPoint[];
  trendSummary: ModuleTrendSummary[];
};
