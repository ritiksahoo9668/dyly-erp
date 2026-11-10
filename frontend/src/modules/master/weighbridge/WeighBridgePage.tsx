import {
  useCreateWeighBridgeMutation,
  useDeactivateWeighBridgeMutation,
  useGetWeighBridgesQuery,
  useImportWeighBridgesMutation,
  useUpdateWeighBridgeMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetWeighBridgesQuery,
  useCreateMutation: useCreateWeighBridgeMutation,
  useUpdateMutation: useUpdateWeighBridgeMutation,
  useDeleteMutation: useDeactivateWeighBridgeMutation,
  useImportMutation: useImportWeighBridgesMutation,
} as unknown as NameMasterApiHooks;

export function WeighBridgePage() {
  return (
    <NameMasterPage
      config={{
        title: "WeighBridge",
        singular: "WeighBridge",
        plural: "weighbridges",
        nameLabel: "WeighBridge Name",
        description: "Manage weighbridges for DYLY ERP.",
        resource: "weighbridges",
        templateFilename: "weighbridge_template.xlsx",
        hooks,
      }}
    />
  );
}
