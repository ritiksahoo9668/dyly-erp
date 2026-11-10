import { useCallback, useRef, useState } from "react";
import {
  useCreateCompanyMutation,
  useCreateUnitMutation,
  useDeactivateCompanyMutation,
  useGetCompaniesQuery,
  useImportCompaniesMutation,
  useUpdateCompanyMutation,
  useValidateCompaniesMutation,
} from "@/app/store/api";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import { NameMasterPage, type NameMasterApiHooks } from "@/modules/master/shared/NameMasterPage";
import type { NameMasterListParams, NameMasterRecord } from "@/types/nameMaster";
import { AddUnitsModal } from "./AddUnitsModal";
import { CompanyFormUnits } from "./CompanyFormUnits";
import { CompanyUnits } from "./CompanyUnits";
import { CompanyUnitsCell } from "./CompanyUnitsCell";
import { createCompanyUnits } from "./createCompanyUnits";

// Units can change from Unit Master (form or Excel import), so never show a cached Company list.
function useCompanyListQuery(params: NameMasterListParams | void) {
  return useGetCompaniesQuery(params, { refetchOnMountOrArgChange: true });
}

const hooks = {
  useListQuery: useCompanyListQuery,
  useCreateMutation: useCreateCompanyMutation,
  useUpdateMutation: useUpdateCompanyMutation,
  useDeleteMutation: useDeactivateCompanyMutation,
  useImportMutation: useImportCompaniesMutation,
  useValidateMutation: useValidateCompaniesMutation,
} as unknown as NameMasterApiHooks;

export function CompanyPage() {
  const [createUnit] = useCreateUnitMutation();
  const { canCreate: canCreateUnit } = useMasterPermissions("unit");
  const [addUnitsFor, setAddUnitsFor] = useState<NameMasterRecord | null>(null);
  const pendingUnitsRef = useRef<string[]>([]);

  const onPendingUnitsChange = useCallback((names: string[]) => {
    pendingUnitsRef.current = names;
  }, []);

  async function saveCompanyUnits(company: NameMasterRecord) {
    const names = pendingUnitsRef.current;
    pendingUnitsRef.current = [];
    if (!names.length) return null;
    const error = await createCompanyUnits(createUnit, company.id, names);
    return error ? `Company saved. ${error}` : null;
  }

  return (
    <>
      <NameMasterPage
        config={{
          title: "Company",
          singular: "Company",
          plural: "companies",
          nameLabel: "Company Name",
          description: "Manage companies. Each Unit belongs to one Company.",
          resource: "companies",
          templateFilename: "company_template.xlsx",
          hooks,
          showStatusFilter: true,
          extraColumns: [
            {
              header: "Associated Units",
              render: (company) => <CompanyUnitsCell company={company} />,
            },
          ],
          extraActions: canCreateUnit
            ? [
                {
                  label: "Add Unit",
                  visible: (company) => company.is_active,
                  onSelect: setAddUnitsFor,
                },
              ]
            : [],
          formSection: canCreateUnit
            ? {
                render: (company) => (
                  <CompanyFormUnits
                    key={company?.id ?? "new"}
                    company={company}
                    onChange={onPendingUnitsChange}
                  />
                ),
                onSaved: saveCompanyUnits,
              }
            : undefined,
          renderViewDetails: (company) => <CompanyUnits companyId={company.id} />,
        }}
      />
      {addUnitsFor ? (
        <AddUnitsModal company={addUnitsFor} onClose={() => setAddUnitsFor(null)} />
      ) : null}
    </>
  );
}
