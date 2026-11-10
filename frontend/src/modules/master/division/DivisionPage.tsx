import {
  useCreateDivisionMutation,
  useDeactivateDivisionMutation,
  useGetDivisionsQuery,
  useImportDivisionsMutation,
  useUpdateDivisionMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetDivisionsQuery,
  useCreateMutation: useCreateDivisionMutation,
  useUpdateMutation: useUpdateDivisionMutation,
  useDeleteMutation: useDeactivateDivisionMutation,
  useImportMutation: useImportDivisionsMutation,
} as unknown as NameMasterApiHooks;

export function DivisionPage() {
  return (
    <NameMasterPage
      config={{
        title: "Division",
        singular: "Division",
        plural: "divisions",
        nameLabel: "Division Name",
        description: "Manage business divisions for DYLY ERP.",
        resource: "divisions",
        templateFilename: "division_template.xlsx",
        hooks,
      }}
    />
  );
}
