import {
  useCreateFacilityMutation,
  useDeactivateFacilityMutation,
  useGetFacilitiesQuery,
  useImportFacilitiesMutation,
  useUpdateFacilityMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetFacilitiesQuery,
  useCreateMutation: useCreateFacilityMutation,
  useUpdateMutation: useUpdateFacilityMutation,
  useDeleteMutation: useDeactivateFacilityMutation,
  useImportMutation: useImportFacilitiesMutation,
} as unknown as NameMasterApiHooks;

export function FacilityPage() {
  return (
    <NameMasterPage
      config={{
        title: "Facility",
        singular: "Facility",
        plural: "facilities",
        nameLabel: "Facility Name",
        description: "Manage facilities for DYLY ERP.",
        resource: "facilities",
        templateFilename: "facility_template.xlsx",
        hooks,
      }}
    />
  );
}
