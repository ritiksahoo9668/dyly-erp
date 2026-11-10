import {
  useCreateMaterialCategoryMutation,
  useDeactivateMaterialCategoryMutation,
  useGetMaterialCategoriesQuery,
  useImportMaterialCategoriesMutation,
  useUpdateMaterialCategoryMutation,
} from "@/app/store/api";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";

const hooks = {
  useListQuery: useGetMaterialCategoriesQuery,
  useCreateMutation: useCreateMaterialCategoryMutation,
  useUpdateMutation: useUpdateMaterialCategoryMutation,
  useDeleteMutation: useDeactivateMaterialCategoryMutation,
  useImportMutation: useImportMaterialCategoriesMutation,
} as unknown as NameMasterApiHooks;

export function MaterialCategoryPage() {
  return (
    <NameMasterPage
      config={{
        title: "Material Category",
        singular: "Category",
        plural: "categories",
        nameLabel: "Category Name",
        description: "Manage top-level material categories for DYLY ERP.",
        resource: "material-categories",
        templateFilename: "material_category_template.xlsx",
        hooks,
      }}
    />
  );
}
