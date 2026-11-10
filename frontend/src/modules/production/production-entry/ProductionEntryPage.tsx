import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { productionOverviewConfig } from "@/modules/production/overviewData";
import {
  createSubmoduleOverviewConfig,
  ModuleOverview,
} from "@/modules/shared/ModuleOverview";

const config = createSubmoduleOverviewConfig(productionOverviewConfig, {
  title: "Production Entry",
  description: "Record heat-wise and shift-wise production output entries.",
});

export function ProductionEntryPage() {
  useDocumentTitle("Production · Production Entry");
  return <ModuleOverview config={config} />;
}
