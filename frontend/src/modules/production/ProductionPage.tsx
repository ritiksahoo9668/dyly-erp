import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { productionOverviewConfig } from "@/modules/production/overviewData";
import { ModuleOverview } from "@/modules/shared/ModuleOverview";

export function ProductionPage() {
  useDocumentTitle("Production");
  return <ModuleOverview config={productionOverviewConfig} />;
}
