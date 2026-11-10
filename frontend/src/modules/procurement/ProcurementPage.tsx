import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { procurementOverviewConfig } from "@/modules/procurement/overviewData";
import { ModuleOverview } from "@/modules/shared/ModuleOverview";

export function ProcurementPage() {
  useDocumentTitle("Procurement");
  return <ModuleOverview config={procurementOverviewConfig} />;
}
