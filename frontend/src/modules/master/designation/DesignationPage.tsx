import {
  useCreateDesignationMutation,
  useDeactivateDesignationMutation,
  useGetDesignationsQuery,
  useImportDesignationsMutation,
  useUpdateDesignationMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetDesignationsQuery,
  useCreateMutation: useCreateDesignationMutation,
  useUpdateMutation: useUpdateDesignationMutation,
  useDeleteMutation: useDeactivateDesignationMutation,
  useImportMutation: useImportDesignationsMutation,
} as unknown as NameMasterApiHooks;

export function DesignationPage() {
  return (
    <NameMasterPage
      config={{
        title: "Designation",
        singular: "Designation",
        plural: "designations",
        nameLabel: "Designation Name",
        description: "Manage designations for DYLY ERP.",
        resource: "designations",
        templateFilename: "designation_template.xlsx",
        hooks,
      }}
    />
  );
}
