import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { productionOverviewConfig } from "@/modules/production/overviewData";
import {
  createSubmoduleOverviewConfig,
  ModuleOverview,
} from "@/modules/shared/ModuleOverview";

const config = createSubmoduleOverviewConfig(productionOverviewConfig, {
  title: "Feed & Consumption",
  description: "Track material feed charges and consumption against production plans.",
});

export function FeedConsumptionPage() {
  useDocumentTitle("Production · Feed & Consumption");
  return <ModuleOverview config={config} />;
}
