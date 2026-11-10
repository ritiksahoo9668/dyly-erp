import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { productionOverviewConfig } from "@/modules/production/overviewData";
import {
  createSubmoduleOverviewConfig,
  ModuleOverview,
} from "@/modules/shared/ModuleOverview";

const config = createSubmoduleOverviewConfig(productionOverviewConfig, {
  title: "Planning",
  description: "Plan production schedules, capacity, and shift-wise targets.",
});

export function ProductionPlanningPage() {
  useDocumentTitle("Production · Planning");
  return <ModuleOverview config={config} />;
}
