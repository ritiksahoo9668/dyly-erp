import {
  useCreateDepartmentMutation,
  useDeactivateDepartmentMutation,
  useGetDepartmentsQuery,
  useImportDepartmentsMutation,
  useUpdateDepartmentMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetDepartmentsQuery,
  useCreateMutation: useCreateDepartmentMutation,
  useUpdateMutation: useUpdateDepartmentMutation,
  useDeleteMutation: useDeactivateDepartmentMutation,
  useImportMutation: useImportDepartmentsMutation,
} as unknown as NameMasterApiHooks;

export function DepartmentPage() {
  return (
    <NameMasterPage
      config={{
        title: "Department",
        singular: "Department",
        plural: "departments",
        nameLabel: "Department Name",
        description: "Manage departments for DYLY ERP.",
        resource: "departments",
        templateFilename: "department_template.xlsx",
        hooks,
      }}
    />
  );
}
