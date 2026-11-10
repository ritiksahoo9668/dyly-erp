import {
  type CSSProperties,
  type FormEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  downloadImportJobErrors,
  downloadNameMasterTemplate,
  useActivateMaterialMutation,
  useCreateMaterialMutation,
  useDeactivateMaterialMutation,
  useGetDepartmentsQuery,
  useGetDivisionsQuery,
  useGetMaterialCategoriesQuery,
  useGetMaterialGroupsQuery,
  useGetMaterialsQuery,
  useGetMaterialSubcategoriesQuery,
  useGetMaterialTypesQuery,
  useGetPlantsQuery,
  useGetPurchasingGroupsQuery,
  useGetStockYardsQuery,
  useGetUomsQuery,
  useImportMaterialsMutation,
  useLazyGetImportJobQuery,
  useLazyGetMaterialQuery,
  useUpdateMaterialMutation,
  useValidateMaterialsMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { CloseIcon, MoreIcon, SearchIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import styles from "@/modules/master/shared/NameMasterPage.module.css";
import catalogueStyles from "./MaterialPage.module.css";
import { MaterialCardMedia, MaterialImageDialog, MaterialImagePanel } from "./MaterialImage";
import type { ImportJob } from "@/types/nameMaster";
import type {
  MaterialImportPreview,
  MaterialListRecord,
  MaterialRecord,
  MaterialRef,
  MaterialWritePayload,
} from "@/types/material";
import type { MaterialGroupRecord } from "@/types/materialGroup";
import type { MaterialSubcategoryRecord } from "@/types/materialSubcategory";
import type { MaterialTypeRecord } from "@/types/materialType";
import type { PlantRecord } from "@/types/plant";
import type { PurchasingGroupRecord } from "@/types/purchasingGroup";
import type { StockYardRecord } from "@/types/stockYard";
import type { UomRecord } from "@/types/uom";
import type { NameMasterRecord } from "@/types/nameMaster";
import { extractApiError } from "@/utils/extractApiError";

type ModalMode = "create" | "edit" | "view" | "import" | null;
type StatusFilter = "all" | "active" | "inactive";
type Ordering =
  | "sap_code"
  | "-sap_code"
  | "item_name"
  | "-item_name"
  | "price"
  | "-price"
  | "created_at"
  | "-created_at"
  | "updated_at"
  | "-updated_at";

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);
const LOOKUP_PARAMS = { lookup: true, page_size: 500 } as const;
const TEXTAREA_STYLE: CSSProperties = {
  border: "1px solid var(--erp-border)",
  borderRadius: 10,
  padding: "10px 12px",
  background: "#f8fafc",
  fontFamily: "inherit",
  fontSize: "inherit",
  resize: "vertical",
  minHeight: 72,
  width: "100%",
};

type ConfirmDialog = { row: MaterialListRecord };
type NoticeDialog = { title: string; message: string };
type ActionMenuState = { row: MaterialListRecord; top: number; left: number };

type MaterialFormState = {
  item_name: string;
  item_description: string;
  descriptive_spec: string;
  technical_spec: string;
  document_type: string;
  store_code: string;
  division_id: number | "";
  material_category_id: number | "";
  material_subcategory_id: number | "";
  uom_id: number | "";
  stock_yard_id: number | "";
  department_id: number | "";
  hsn_sac_code: string;
  gst_percent: string;
  price: string;
  sap_code: string;
  plant_id: number | "";
  material_group_id: number | "";
  material_type_id: number | "";
  purchasing_group_id: number | "";
};

const EMPTY_FORM: MaterialFormState = {
  item_name: "",
  item_description: "",
  descriptive_spec: "",
  technical_spec: "",
  document_type: "",
  store_code: "",
  division_id: "",
  material_category_id: "",
  material_subcategory_id: "",
  uom_id: "",
  stock_yard_id: "",
  department_id: "",
  hsn_sac_code: "",
  gst_percent: "",
  price: "",
  sap_code: "",
  plant_id: "",
  material_group_id: "",
  material_type_id: "",
  purchasing_group_id: "",
};

function extractError(error: unknown): string {
  return extractApiError(error);
}

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatRef(ref: MaterialRef | null | undefined): string {
  if (!ref) return "—";
  if (ref.code) return `${ref.code} — ${ref.name}`;
  return ref.name;
}

function formatUomRef(ref: MaterialRef | null | undefined): string {
  if (!ref) return "—";
  if (ref.symbol) return ref.symbol;
  return ref.name;
}

function recordToForm(record: MaterialRecord): MaterialFormState {
  return {
    item_name: record.item_name,
    item_description: record.item_description,
    descriptive_spec: record.descriptive_spec,
    technical_spec: record.technical_spec,
    document_type: record.document_type,
    store_code: record.store_code,
    division_id: record.division?.id ?? "",
    material_category_id: record.material_category?.id ?? "",
    material_subcategory_id: record.material_subcategory?.id ?? "",
    uom_id: record.uom?.id ?? "",
    stock_yard_id: record.stock_yard?.id ?? "",
    department_id: record.department?.id ?? "",
    hsn_sac_code: record.hsn_sac_code,
    gst_percent: record.gst_percent,
    price: record.price,
    sap_code: record.sap_code,
    plant_id: record.plant?.id ?? "",
    material_group_id: record.material_group?.id ?? "",
    material_type_id: record.material_type?.id ?? "",
    purchasing_group_id: record.purchasing_group?.id ?? "",
  };
}

function buildPayload(form: MaterialFormState, isActive?: boolean): MaterialWritePayload {
  return {
    item_name: form.item_name.trim(),
    item_description: form.item_description.trim(),
    descriptive_spec: form.descriptive_spec.trim(),
    technical_spec: form.technical_spec.trim(),
    document_type: form.document_type.trim(),
    store_code: form.store_code.trim(),
    division_id: form.division_id === "" ? null : form.division_id,
    material_category_id: form.material_category_id as number,
    material_subcategory_id: form.material_subcategory_id as number,
    uom_id: form.uom_id as number,
    stock_yard_id: form.stock_yard_id as number,
    department_id: form.department_id as number,
    hsn_sac_code: form.hsn_sac_code.trim(),
    gst_percent: form.gst_percent.trim(),
    price: form.price.trim(),
    sap_code: form.sap_code.trim(),
    plant_id: form.plant_id as number,
    material_group_id: form.material_group_id as number,
    material_type_id: form.material_type_id as number,
    purchasing_group_id: form.purchasing_group_id as number,
    ...(isActive !== undefined ? { is_active: isActive } : {}),
  };
}

function validateForm(form: MaterialFormState): string | null {
  if (!form.item_name.trim()) return "Item Name is required.";
  if (!form.item_description.trim()) return "Item Description is required.";
  if (!form.descriptive_spec.trim()) return "Descriptive Spec is required.";
  if (!form.document_type.trim()) return "Document Type is required.";
  if (!form.store_code.trim()) return "Store Code is required.";
  if (form.material_category_id === "") return "Material Category is required.";
  if (form.material_subcategory_id === "") return "Material Sub Category is required.";
  if (form.uom_id === "") return "UOM is required.";
  if (form.stock_yard_id === "") return "Stock Yard is required.";
  if (form.department_id === "") return "Department is required.";
  if (!form.hsn_sac_code.trim()) return "HSN/SAC Code is required.";
  if (!form.gst_percent.trim()) return "GST % is required.";
  if (!form.price.trim()) return "Price is required.";
  if (!form.sap_code.trim()) return "SAP Code is required.";
  if (form.plant_id === "") return "Plant is required.";
  if (form.material_group_id === "") return "Material Group is required.";
  if (form.material_type_id === "") return "Material Type is required.";
  if (form.purchasing_group_id === "") return "Purchasing Group is required.";
  return null;
}

type SelectOption = { value: number; label: string };

function MasterSelect({
  id,
  label,
  value,
  onChange,
  options,
  disabled,
  required,
}: {
  id: string;
  label: string;
  value: number | "";
  onChange: (value: number | "") => void;
  options: SelectOption[];
  disabled?: boolean;
  required?: boolean;
}) {
  return (
    <div className={catalogueStyles.masterSelect}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value === "" ? "" : String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          onChange(raw === "" ? "" : Number(raw));
        }}
        disabled={disabled}
        required={required}
      >
        <option value="">Select…</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={catalogueStyles.formSection}>
      <h3 className={catalogueStyles.formSectionTitle}>{title}</h3>
      <div className={catalogueStyles.formGrid}>{children}</div>
    </section>
  );
}

function ViewDetailSection({
  title,
  columns = 2,
  children,
}: {
  title: string;
  columns?: 2 | 3;
  children: ReactNode;
}) {
  const gridClass =
    columns === 3 ? catalogueStyles.detailFieldGridThree : catalogueStyles.detailFieldGridTwo;
  return (
    <section className={catalogueStyles.detailSection}>
      <h3>{title}</h3>
      <div className={catalogueStyles.detailSectionBody}>
        <div className={gridClass}>{children}</div>
      </div>
    </section>
  );
}

function DetailField({
  label,
  value,
  wide,
  muted,
}: {
  label: string;
  value: ReactNode;
  wide?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      className={`${catalogueStyles.detailField} ${wide ? catalogueStyles.detailFieldWide : ""}`}
    >
      <span className={catalogueStyles.detailFieldLabel}>{label}</span>
      <div
        className={`${catalogueStyles.detailFieldValue} ${
          muted ? catalogueStyles.detailFieldValueMuted : ""
        }`}
      >
        {value || "—"}
      </div>
    </div>
  );
}

export function MaterialPage() {
  useDocumentTitle("Master · Material");
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("material-item");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [ordering, setOrdering] = useState<Ordering>("sap_code");
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [categoryFilter, setCategoryFilter] = useState<number | "">("");
  const [subcategoryFilter, setSubcategoryFilter] = useState<number | "">("");
  const [uomFilter, setUomFilter] = useState<number | "">("");
  const [materialTypeFilter, setMaterialTypeFilter] = useState<number | "">("");
  const [materialGroupFilter, setMaterialGroupFilter] = useState<number | "">("");
  const [purchasingGroupFilter, setPurchasingGroupFilter] = useState<number | "">("");
  const [plantFilter, setPlantFilter] = useState<number | "">("");
  const [stockYardFilter, setStockYardFilter] = useState<number | "">("");
  const [departmentFilter, setDepartmentFilter] = useState<number | "">("");
  const [divisionFilter, setDivisionFilter] = useState<number | "">("");

  const [modal, setModal] = useState<ModalMode>(null);
  const [detail, setDetail] = useState<MaterialRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form, setForm] = useState<MaterialFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<MaterialImportPreview | null>(null);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [errorDownloadBusy, setErrorDownloadBusy] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog | null>(null);
  const [noticeDialog, setNoticeDialog] = useState<NoticeDialog | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);
  const [cardImageTarget, setCardImageTarget] = useState<MaterialListRecord | null>(null);

  const queryArgs = useMemo(
    () => ({
      search,
      page,
      page_size: pageSize,
      ordering,
      is_active: statusFilter === "all" ? undefined : statusFilter === "active",
      material_category: typeof categoryFilter === "number" ? categoryFilter : undefined,
      material_subcategory: typeof subcategoryFilter === "number" ? subcategoryFilter : undefined,
      uom: typeof uomFilter === "number" ? uomFilter : undefined,
      material_type: typeof materialTypeFilter === "number" ? materialTypeFilter : undefined,
      material_group: typeof materialGroupFilter === "number" ? materialGroupFilter : undefined,
      purchasing_group: typeof purchasingGroupFilter === "number" ? purchasingGroupFilter : undefined,
      plant: typeof plantFilter === "number" ? plantFilter : undefined,
      stock_yard: typeof stockYardFilter === "number" ? stockYardFilter : undefined,
      department: typeof departmentFilter === "number" ? departmentFilter : undefined,
      division: typeof divisionFilter === "number" ? divisionFilter : undefined,
    }),
    [
      search,
      page,
      pageSize,
      ordering,
      statusFilter,
      categoryFilter,
      subcategoryFilter,
      uomFilter,
      materialTypeFilter,
      materialGroupFilter,
      purchasingGroupFilter,
      plantFilter,
      stockYardFilter,
      departmentFilter,
      divisionFilter,
    ],
  );

  const { data, isLoading, isFetching, isError, refetch } = useGetMaterialsQuery(queryArgs);
  const { data: divisionsData } = useGetDivisionsQuery(LOOKUP_PARAMS);
  const { data: departmentsData } = useGetDepartmentsQuery(LOOKUP_PARAMS);
  const { data: categoriesData } = useGetMaterialCategoriesQuery(LOOKUP_PARAMS);
  const listSubcategoryCategory =
    typeof categoryFilter === "number" ? categoryFilter : undefined;
  const { data: listSubcategoriesData } = useGetMaterialSubcategoriesQuery(
    { ...LOOKUP_PARAMS, category: listSubcategoryCategory },
    { skip: listSubcategoryCategory === undefined },
  );
  const formSubcategoryCategory =
    typeof form.material_category_id === "number" ? form.material_category_id : undefined;
  const { data: formSubcategoriesData } = useGetMaterialSubcategoriesQuery(
    { ...LOOKUP_PARAMS, category: formSubcategoryCategory },
    { skip: formSubcategoryCategory === undefined },
  );
  const { data: uomsData } = useGetUomsQuery(LOOKUP_PARAMS);
  const { data: stockYardsData } = useGetStockYardsQuery(LOOKUP_PARAMS);
  const { data: plantsData } = useGetPlantsQuery(LOOKUP_PARAMS);
  const { data: materialGroupsData } = useGetMaterialGroupsQuery(LOOKUP_PARAMS);
  const { data: materialTypesData } = useGetMaterialTypesQuery(LOOKUP_PARAMS);
  const { data: purchasingGroupsData } = useGetPurchasingGroupsQuery(LOOKUP_PARAMS);

  const [createRecord, createState] = useCreateMaterialMutation();
  const [updateRecord, updateState] = useUpdateMaterialMutation();
  const [deactivateRecord, deactivateState] = useDeactivateMaterialMutation();
  const [activateRecord, activateState] = useActivateMaterialMutation();
  const [validateImport, validateState] = useValidateMaterialsMutation();
  const [importRecords, importState] = useImportMaterialsMutation();
  const [fetchMaterial] = useLazyGetMaterialQuery();
  const [fetchImportJob] = useLazyGetImportJobQuery();

  const importBusy =
    validateState.isLoading ||
    importState.isLoading ||
    Boolean(importJob && !TERMINAL_JOB_STATUSES.has(importJob.status));

  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const rangeFrom = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeTo = Math.min(page * pageSize, totalCount);
  const saving = createState.isLoading || updateState.isLoading;

  const divisions = divisionsData?.results ?? [];
  const departments = departmentsData?.results ?? [];
  const categories = categoriesData?.results ?? [];
  const listSubcategories = listSubcategoriesData?.results ?? [];
  const formSubcategories = formSubcategoriesData?.results ?? [];
  const uoms = uomsData?.results ?? [];
  const stockYards = stockYardsData?.results ?? [];
  const plants = plantsData?.results ?? [];
  const materialGroups = materialGroupsData?.results ?? [];
  const materialTypes = materialTypesData?.results ?? [];
  const purchasingGroups = purchasingGroupsData?.results ?? [];

  const divisionOptions = useMemo(
    () => divisions.map((d: NameMasterRecord) => ({ value: d.id, label: d.name })),
    [divisions],
  );
  const departmentOptions = useMemo(
    () => departments.map((d: NameMasterRecord) => ({ value: d.id, label: d.name })),
    [departments],
  );
  const categoryOptions = useMemo(
    () => categories.map((c: NameMasterRecord) => ({ value: c.id, label: c.name })),
    [categories],
  );
  const uomOptions = useMemo(
    () => uoms.map((u: UomRecord) => ({ value: u.id, label: `${u.symbol} — ${u.name}` })),
    [uoms],
  );
  const stockYardOptions = useMemo(
    () =>
      stockYards.map((y: StockYardRecord) => ({
        value: y.id,
        label: `${y.storage_code} — ${y.name}`,
      })),
    [stockYards],
  );
  const plantOptions = useMemo(
    () =>
      plants.map((p: PlantRecord) => ({
        value: p.id,
        label: `${p.sap_plant_code} — ${p.name}`,
      })),
    [plants],
  );
  const materialGroupOptions = useMemo(
    () =>
      materialGroups.map((g: MaterialGroupRecord) => ({
        value: g.id,
        label: `${g.sap_material_group_code} — ${g.name}`,
      })),
    [materialGroups],
  );
  const materialTypeOptions = useMemo(
    () =>
      materialTypes.map((t: MaterialTypeRecord) => ({
        value: t.id,
        label: `${t.material_type_code} — ${t.erp_category_desc}`,
      })),
    [materialTypes],
  );
  const purchasingGroupOptions = useMemo(
    () =>
      purchasingGroups.map((g: PurchasingGroupRecord) => ({
        value: g.id,
        label: `${g.sap_purchase_group_code} — ${g.name}`,
      })),
    [purchasingGroups],
  );

  function subcategoryOptionsFor(records: MaterialSubcategoryRecord[]): SelectOption[] {
    return records.map((s) => ({ value: s.id, label: s.name }));
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [
    statusFilter,
    ordering,
    pageSize,
    categoryFilter,
    subcategoryFilter,
    uomFilter,
    materialTypeFilter,
    materialGroupFilter,
    purchasingGroupFilter,
    plantFilter,
    stockYardFilter,
    departmentFilter,
    divisionFilter,
  ]);

  useEffect(() => {
    setSubcategoryFilter("");
  }, [categoryFilter]);

  useEffect(() => {
    if (!actionMenu) return;
    function closeMenu() {
      setActionMenu(null);
    }
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (actionMenuRef.current?.contains(target)) return;
      if ((target as HTMLElement).closest?.("[data-action-trigger='true']")) return;
      closeMenu();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu();
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
    };
  }, [actionMenu]);

  useEffect(() => {
    if (!importJob || TERMINAL_JOB_STATUSES.has(importJob.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchImportJob(importJob.id).unwrap();
        if (!cancelled) {
          setImportJob(latest);
          if (TERMINAL_JOB_STATUSES.has(latest.status)) refetch();
        }
      } catch {
        // keep polling
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [importJob, fetchImportJob, refetch]);

  function patchForm(patch: Partial<MaterialFormState>) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  function onCategoryChange(value: number | "") {
    patchForm({ material_category_id: value, material_subcategory_id: "" });
  }

  function onStockYardChange(value: number | "") {
    if (value === "") {
      patchForm({ stock_yard_id: "" });
      return;
    }
    const yard = stockYards.find((y) => y.id === value);
    const code = yard?.storage_code ?? "";
    patchForm({ stock_yard_id: value, store_code: code || form.store_code });
  }

  function openCreate() {
    setDetail(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setModal("create");
  }

  async function loadDetail(id: number) {
    setDetailLoading(true);
    setDetail(null);
    try {
      const full = await fetchMaterial(id).unwrap();
      setDetail(full);
      return full;
    } catch (err) {
      setFormError(extractError(err));
      return null;
    } finally {
      setDetailLoading(false);
    }
  }

  async function openEdit(row: MaterialListRecord) {
    setFormError(null);
    setModal("edit");
    const full = await loadDetail(row.id);
    if (full) setForm(recordToForm(full));
  }

  async function openView(row: MaterialListRecord) {
    setFormError(null);
    setModal("view");
    await loadDetail(row.id);
  }

  function closeModal() {
    setModal(null);
    setDetail(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setImportJob(null);
    setImportPreview(null);
    setImportFile(null);
  }

  function showNotice(title: string, message: string) {
    setNoticeDialog({ title, message });
  }

  function toggleActionMenu(row: MaterialListRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 160;
    const gap = 6;
    const left = Math.min(Math.max(8, rect.right - menuWidth), window.innerWidth - menuWidth - 8);
    const openUp = rect.bottom + gap + menuHeight > window.innerHeight;
    const top = openUp
      ? Math.max(8, rect.top - menuHeight - gap)
      : Math.min(rect.bottom + gap, window.innerHeight - menuHeight - 8);
    setActionMenu({ row, top, left });
  }

  function runMenuAction(action: () => void) {
    setActionMenu(null);
    action();
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const validation = validateForm(form);
    if (validation) {
      setFormError(validation);
      return;
    }
    try {
      const body = buildPayload(form, detail?.is_active);
      if (modal === "create") {
        await createRecord(body).unwrap();
      } else if (modal === "edit" && detail) {
        await updateRecord({ id: detail.id, body }).unwrap();
      }
      closeModal();
    } catch (err) {
      setFormError(extractError(err));
    }
  }

  async function confirmDeactivate() {
    if (!confirmDialog) return;
    setConfirmBusy(true);
    try {
      await deactivateRecord(confirmDialog.row.id).unwrap();
      if (detail?.id === confirmDialog.row.id) closeModal();
      setConfirmDialog(null);
    } catch (err) {
      setConfirmDialog(null);
      showNotice("Action failed", extractError(err));
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onActivate(row: MaterialListRecord) {
    if (row.is_active) return;
    try {
      await activateRecord(row.id).unwrap();
    } catch (err) {
      showNotice("Action failed", extractError(err));
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("materials", "material_template.xlsx", accessToken);
    } catch {
      showNotice("Download failed", "Unable to download template.");
    } finally {
      setTemplateBusy(false);
    }
  }

  async function onFileSelected(file: File | null) {
    if (!file) return;
    setFormError(null);
    setImportPreview(null);
    setImportJob(null);
    setImportFile(file);
    setModal("import");
    try {
      const preview = await validateImport(file).unwrap();
      setImportPreview(preview);
    } catch (err) {
      setFormError(extractError(err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onConfirmImport() {
    if (!importFile) return;
    setFormError(null);
    try {
      const job = await importRecords(importFile).unwrap();
      setImportPreview(null);
      setImportJob(job);
    } catch (err) {
      setFormError(extractError(err));
    }
  }

  async function onDownloadErrors() {
    if (!importJob?.has_error_file) return;
    setErrorDownloadBusy(true);
    try {
      await downloadImportJobErrors(importJob.id, accessToken);
    } catch {
      showNotice("Download failed", "Unable to download error file.");
    } finally {
      setErrorDownloadBusy(false);
    }
  }

  const formModalOpen = modal === "create" || modal === "edit";

  return (
    <PageContainer>
      <div className={styles.page}>
        <div className={styles.toolbar}>
          <div className={styles.heading}>
            <h1>Material</h1>
            <p>Manage material master records for DYLY ERP.</p>
          </div>
          <div className={styles.actions}>
            {canUpload ? (
              <>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={onDownloadTemplate}
                  disabled={templateBusy}
                >
                  {templateBusy ? "Downloading…" : "Download Template"}
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => fileRef.current?.click()}
                  disabled={importBusy}
                >
                  Upload Excel
                </button>
              </>
            ) : null}
            {canCreate ? (
              <button type="button" className={styles.primaryBtn} onClick={openCreate}>
                Add Material
              </button>
            ) : null}
            <input
              ref={fileRef}
              className={styles.fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
            />
          </div>
        </div>

        <div className={catalogueStyles.summaryRow}>
          <div className={catalogueStyles.summaryCard}>
            <span className={catalogueStyles.summaryLabel}>Total Materials</span>
            <span className={catalogueStyles.summaryValue}>{totalCount}</span>
          </div>
        </div>

        <div className={catalogueStyles.searchRow}>
          <label className={styles.search}>
            <span className={styles.searchIcon} aria-hidden="true">
              <SearchIcon />
            </span>
            <input
              type="search"
              placeholder="Search materials…"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search materials"
            />
          </label>
          <button
            type="button"
            className={`${catalogueStyles.filtersToggle} ${
              filtersOpen ? catalogueStyles.filtersToggleActive : ""
            }`}
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((open) => !open)}
          >
            Filters
          </button>
          <select
            className={styles.filterSelect}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            aria-label="Filter by status"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <select
            className={styles.filterSelect}
            value={ordering}
            onChange={(event) => setOrdering(event.target.value as Ordering)}
            aria-label="Sort order"
          >
            <option value="sap_code">SAP Code (A–Z)</option>
            <option value="-sap_code">SAP Code (Z–A)</option>
            <option value="item_name">Item Name (A–Z)</option>
            <option value="-item_name">Item Name (Z–A)</option>
            <option value="price">Price (Low–High)</option>
            <option value="-price">Price (High–Low)</option>
            <option value="-created_at">Created (Newest)</option>
            <option value="created_at">Created (Oldest)</option>
            <option value="-updated_at">Updated (Newest)</option>
            <option value="updated_at">Updated (Oldest)</option>
          </select>
          <select
            className={styles.filterSelect}
            value={pageSize}
            onChange={(event) => setPageSize(Number(event.target.value))}
            aria-label="Page size"
          >
            <option value={20}>20 / page</option>
            <option value={40}>40 / page</option>
            <option value={60}>60 / page</option>
            <option value={100}>100 / page</option>
          </select>
        </div>

        {filtersOpen ? (
          <div className={catalogueStyles.advancedFilters}>
            <select
              className={styles.filterSelect}
              value={categoryFilter === "" ? "" : String(categoryFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setCategoryFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by category"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={subcategoryFilter === "" ? "" : String(subcategoryFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setSubcategoryFilter(raw === "" ? "" : Number(raw));
              }}
              disabled={categoryFilter === ""}
              aria-label="Filter by sub category"
            >
              <option value="">All Sub Categories</option>
              {listSubcategories.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={uomFilter === "" ? "" : String(uomFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setUomFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by UOM"
            >
              <option value="">All UOMs</option>
              {uoms.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.symbol}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={materialTypeFilter === "" ? "" : String(materialTypeFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setMaterialTypeFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by material type"
            >
              <option value="">All Material Types</option>
              {materialTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.material_type_code} — {t.erp_category_desc}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={materialGroupFilter === "" ? "" : String(materialGroupFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setMaterialGroupFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by material group"
            >
              <option value="">All Material Groups</option>
              {materialGroups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.sap_material_group_code} — {g.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={purchasingGroupFilter === "" ? "" : String(purchasingGroupFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setPurchasingGroupFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by purchasing group"
            >
              <option value="">All Purchasing Groups</option>
              {purchasingGroups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.sap_purchase_group_code} — {g.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={plantFilter === "" ? "" : String(plantFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setPlantFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by plant"
            >
              <option value="">All Plants</option>
              {plants.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sap_plant_code} — {p.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={stockYardFilter === "" ? "" : String(stockYardFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setStockYardFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by stock yard"
            >
              <option value="">All Stock Yards</option>
              {stockYards.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.storage_code} — {y.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={departmentFilter === "" ? "" : String(departmentFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setDepartmentFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by department"
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <select
              className={styles.filterSelect}
              value={divisionFilter === "" ? "" : String(divisionFilter)}
              onChange={(event) => {
                const raw = event.target.value;
                setDivisionFilter(raw === "" ? "" : Number(raw));
              }}
              aria-label="Filter by division"
            >
              <option value="">All Divisions</option>
              {divisions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className={styles.panel}>
          {isLoading ? <p className={styles.loading}>Loading materials…</p> : null}
          {isError ? (
            <p className={styles.error}>
              Unable to load materials.{" "}
              <button type="button" className={styles.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length === 0 ? (
            <p className={styles.empty}>No materials found. Add one or upload Excel.</p>
          ) : null}
          {!isLoading && !isError && data && data.results.length > 0 ? (
            <>
              <div className={catalogueStyles.catalogueGrid}>
                {data.results.map((row) => (
                  <div
                    key={row.id}
                    role="button"
                    tabIndex={0}
                    className={catalogueStyles.materialCard}
                    onClick={() => openView(row)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openView(row);
                      }
                    }}
                  >
                    <div className={catalogueStyles.cardImageWrap}>
                      <MaterialCardMedia
                        src={row.display_thumb ?? row.display_image}
                        alt={row.item_name}
                        onAddImage={canEdit ? () => setCardImageTarget(row) : undefined}
                      />
                      <button
                        type="button"
                        className={`${catalogueStyles.cardMenuBtn} ${
                          actionMenu?.row.id === row.id ? catalogueStyles.cardMenuBtnOpen : ""
                        }`}
                        data-action-trigger="true"
                        aria-label={`Actions for ${row.item_name}`}
                        aria-haspopup="menu"
                        aria-expanded={actionMenu?.row.id === row.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleActionMenu(row, event.currentTarget);
                        }}
                      >
                        <MoreIcon size={16} />
                      </button>
                    </div>
                    <div className={catalogueStyles.cardBody}>
                      <h3 className={catalogueStyles.cardTitle}>{row.item_name}</h3>
                      <dl className={catalogueStyles.cardMeta}>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>Category</dt>
                          <dd>{row.material_category?.name ?? "—"}</dd>
                        </div>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>Subcat</dt>
                          <dd>{row.material_subcategory?.name ?? "—"}</dd>
                        </div>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>UOM</dt>
                          <dd>{formatUomRef(row.uom)}</dd>
                        </div>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>Type</dt>
                          <dd>{formatRef(row.material_type)}</dd>
                        </div>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>Plant</dt>
                          <dd>{formatRef(row.plant)}</dd>
                        </div>
                        <div className={catalogueStyles.cardMetaRow}>
                          <dt>Dept</dt>
                          <dd>{row.department?.name ?? "—"}</dd>
                        </div>
                      </dl>
                      <div className={catalogueStyles.cardFooter}>
                        <span className={catalogueStyles.cardPrice}>{row.price}</span>
                        <span
                          className={`${styles.badge} ${
                            row.is_active ? styles.badgeActive : styles.badgeInactive
                          }`}
                        >
                          {row.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className={styles.pager}>
                <span className={catalogueStyles.pagerMeta}>
                  Showing {rangeFrom}–{rangeTo} of {totalCount} materials
                  {isFetching ? " · Refreshing…" : ""}
                </span>
                <div className={styles.pagerControls}>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={page <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={page >= totalPages}
                    onClick={() => setPage((value) => value + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {actionMenu
        ? createPortal(
            <div
              ref={actionMenuRef}
              className={styles.actionsMenu}
              role="menu"
              style={{ top: actionMenu.top, left: actionMenu.left }}
            >
              <button
                type="button"
                className={styles.menuItem}
                role="menuitem"
                onClick={() => runMenuAction(() => openView(actionMenu.row))}
              >
                View
              </button>
              {canEdit ? (
                <button
                  type="button"
                  className={styles.menuItem}
                  role="menuitem"
                  onClick={() => runMenuAction(() => openEdit(actionMenu.row))}
                >
                  Edit
                </button>
              ) : null}
              {!canToggleActive ? null : actionMenu.row.is_active ? (
                <button
                  type="button"
                  className={`${styles.menuItem} ${styles.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => runMenuAction(() => setConfirmDialog({ row: actionMenu.row }))}
                  disabled={deactivateState.isLoading}
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  className={styles.menuItem}
                  role="menuitem"
                  onClick={() => runMenuAction(() => onActivate(actionMenu.row))}
                  disabled={activateState.isLoading}
                >
                  Activate
                </button>
              )}
            </div>,
            document.body,
          )
        : null}

      {cardImageTarget ? (
        <MaterialImageDialog
          material={cardImageTarget}
          initialMode="choose"
          onClose={() => setCardImageTarget(null)}
          onSaved={(record) => {
            if (detail?.id === record.id) setDetail(record);
          }}
        />
      ) : null}

      {formModalOpen
        ? createPortal(
            <>
              <button
                type="button"
                className={catalogueStyles.viewOverlay}
                aria-label="Close"
                onClick={closeModal}
              />
              <div className={catalogueStyles.viewModal} role="dialog" aria-modal="true">
                <div className={catalogueStyles.viewModalHeader}>
                  <div>
                    <h2>{modal === "create" ? "Add Material" : "Edit Material"}</h2>
                    <p>Complete all required sections to save the material record.</p>
                  </div>
                  <button
                    type="button"
                    className={styles.closeBtn}
                    aria-label="Close"
                    onClick={closeModal}
                  >
                    <CloseIcon />
                  </button>
                </div>

                {detailLoading && modal === "edit" ? (
                  <div className={catalogueStyles.viewModalBody}>
                    <p className={styles.loading}>Loading material…</p>
                  </div>
                ) : (
                  <form className={catalogueStyles.formShell} onSubmit={onSubmit}>
                    <div className={catalogueStyles.viewModalBody}>
                      {formError ? <p className={styles.formError}>{formError}</p> : null}

                      <FormSection title="Basic Information">
                        <div className={`${styles.field} ${catalogueStyles.formFieldFull}`}>
                          <label htmlFor="mat-item-name">Item Name</label>
                          <input
                            id="mat-item-name"
                            value={form.item_name}
                            onChange={(e) => patchForm({ item_name: e.target.value })}
                            required
                            maxLength={255}
                          />
                        </div>
                        <div className={`${styles.field} ${catalogueStyles.formFieldFull}`}>
                          <label htmlFor="mat-item-desc">Item Description</label>
                          <textarea
                            id="mat-item-desc"
                            value={form.item_description}
                            onChange={(e) => patchForm({ item_description: e.target.value })}
                            required
                            style={TEXTAREA_STYLE}
                          />
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="mat-doc-type">Document Type</label>
                          <input
                            id="mat-doc-type"
                            value={form.document_type}
                            onChange={(e) => patchForm({ document_type: e.target.value })}
                            required
                            maxLength={50}
                          />
                        </div>
                      </FormSection>

                      <section className={catalogueStyles.formSection}>
                        <h3 className={catalogueStyles.formSectionTitle}>Material Image</h3>
                        {modal === "edit" && detail ? (
                          <div className={catalogueStyles.formImageRow}>
                            <MaterialImagePanel
                              material={detail}
                              variant="form"
                              onChanged={setDetail}
                            />
                            <p className={catalogueStyles.formImageNote}>
                              Image changes are saved immediately and only update the image. Other
                              Material details are saved with the Save button.
                            </p>
                          </div>
                        ) : (
                          <p className={catalogueStyles.formImageNote}>
                            Save the material first, then add an image by upload or URL from View
                            or Edit Material.
                          </p>
                        )}
                      </section>

                      <FormSection title="Classification">
                        <MasterSelect
                          id="mat-division"
                          label="Division"
                          value={form.division_id}
                          onChange={(value) => patchForm({ division_id: value })}
                          options={divisionOptions}
                        />
                        <MasterSelect
                          id="mat-category"
                          label="Material Category"
                          value={form.material_category_id}
                          onChange={onCategoryChange}
                          options={categoryOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-subcategory"
                          label="Material Sub Category"
                          value={form.material_subcategory_id}
                          onChange={(value) => patchForm({ material_subcategory_id: value })}
                          options={subcategoryOptionsFor(formSubcategories)}
                          disabled={form.material_category_id === ""}
                          required
                        />
                        <MasterSelect
                          id="mat-uom"
                          label="UOM"
                          value={form.uom_id}
                          onChange={(value) => patchForm({ uom_id: value })}
                          options={uomOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-mat-type"
                          label="Material Type"
                          value={form.material_type_id}
                          onChange={(value) => patchForm({ material_type_id: value })}
                          options={materialTypeOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-mat-group"
                          label="Material Group"
                          value={form.material_group_id}
                          onChange={(value) => patchForm({ material_group_id: value })}
                          options={materialGroupOptions}
                          required
                        />
                      </FormSection>

                      <FormSection title="Specifications">
                        <div className={`${styles.field} ${catalogueStyles.formFieldFull}`}>
                          <label htmlFor="mat-desc-spec">Descriptive Spec</label>
                          <textarea
                            id="mat-desc-spec"
                            value={form.descriptive_spec}
                            onChange={(e) => patchForm({ descriptive_spec: e.target.value })}
                            required
                            style={TEXTAREA_STYLE}
                          />
                        </div>
                        <div className={`${styles.field} ${catalogueStyles.formFieldFull}`}>
                          <label htmlFor="mat-tech-spec">Technical Spec</label>
                          <textarea
                            id="mat-tech-spec"
                            value={form.technical_spec}
                            onChange={(e) => patchForm({ technical_spec: e.target.value })}
                            style={TEXTAREA_STYLE}
                          />
                        </div>
                      </FormSection>

                      <FormSection title="Commercial / Tax">
                        <div className={styles.field}>
                          <label htmlFor="mat-hsn">HSN/SAC Code</label>
                          <input
                            id="mat-hsn"
                            value={form.hsn_sac_code}
                            onChange={(e) => patchForm({ hsn_sac_code: e.target.value })}
                            required
                            maxLength={50}
                          />
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="mat-gst">GST %</label>
                          <input
                            id="mat-gst"
                            value={form.gst_percent}
                            onChange={(e) => patchForm({ gst_percent: e.target.value })}
                            required
                            inputMode="decimal"
                          />
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="mat-price">Price</label>
                          <input
                            id="mat-price"
                            value={form.price}
                            onChange={(e) => patchForm({ price: e.target.value })}
                            required
                            inputMode="decimal"
                          />
                        </div>
                      </FormSection>

                      <FormSection title="SAP / Organization">
                        <div className={styles.field}>
                          <label htmlFor="mat-sap">SAP Code</label>
                          <input
                            id="mat-sap"
                            value={form.sap_code}
                            onChange={(e) => patchForm({ sap_code: e.target.value })}
                            required
                            maxLength={50}
                          />
                        </div>
                        <div className={styles.field}>
                          <label htmlFor="mat-store">Store Code</label>
                          <input
                            id="mat-store"
                            value={form.store_code}
                            onChange={(e) => patchForm({ store_code: e.target.value })}
                            required
                            maxLength={50}
                          />
                        </div>
                        <MasterSelect
                          id="mat-stock-yard"
                          label="Stock Yard"
                          value={form.stock_yard_id}
                          onChange={onStockYardChange}
                          options={stockYardOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-plant"
                          label="Plant"
                          value={form.plant_id}
                          onChange={(value) => patchForm({ plant_id: value })}
                          options={plantOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-dept"
                          label="Department"
                          value={form.department_id}
                          onChange={(value) => patchForm({ department_id: value })}
                          options={departmentOptions}
                          required
                        />
                        <MasterSelect
                          id="mat-purch-group"
                          label="Purchasing Group"
                          value={form.purchasing_group_id}
                          onChange={(value) => patchForm({ purchasing_group_id: value })}
                          options={purchasingGroupOptions}
                          required
                        />
                      </FormSection>
                    </div>

                    <div className={catalogueStyles.viewModalFooter}>
                      <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className={styles.primaryBtn}
                        disabled={saving || detailLoading}
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </>,
            document.body,
          )
        : null}

      {modal === "view"
        ? createPortal(
            <>
              <button
                type="button"
                className={catalogueStyles.viewOverlay}
                aria-label="Close"
                onClick={closeModal}
              />
              <div className={catalogueStyles.viewModal} role="dialog" aria-modal="true">
                <div className={catalogueStyles.viewModalHeader}>
                  <div>
                    <h2>View Material</h2>
                    <p>Complete material master details</p>
                  </div>
                  <button
                    type="button"
                    className={styles.closeBtn}
                    aria-label="Close"
                    onClick={closeModal}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <div className={catalogueStyles.viewModalBody}>
                  {detailLoading ? <p className={styles.loading}>Loading material…</p> : null}
                  {formError && !detail ? <p className={styles.formError}>{formError}</p> : null}
                  {detail ? (
                    <>
                      <div className={catalogueStyles.viewHero}>
                        <MaterialImagePanel
                          material={detail}
                          onChanged={setDetail}
                          readOnly={!canEdit}
                        />
                        <div className={catalogueStyles.viewHeroMain}>
                          <h3 className={catalogueStyles.viewHeroTitle}>{detail.item_name}</h3>
                          <div className={catalogueStyles.viewHeroMeta}>
                            <p className={catalogueStyles.viewHeroSap}>
                              <span className={catalogueStyles.viewHeroSapLabel}>SAP</span>
                              {detail.sap_code}
                            </p>
                            <span
                              className={`${styles.badge} ${
                                detail.is_active ? styles.badgeActive : styles.badgeInactive
                              }`}
                            >
                              {detail.is_active ? "Active" : "Inactive"}
                            </span>
                          </div>
                          <div className={catalogueStyles.viewStatRow}>
                            <div className={catalogueStyles.viewStat}>
                              <span className={catalogueStyles.viewStatLabel}>Price</span>
                              <span className={catalogueStyles.viewStatValue}>{detail.price}</span>
                            </div>
                            <div className={catalogueStyles.viewStat}>
                              <span className={catalogueStyles.viewStatLabel}>UOM</span>
                              <span className={catalogueStyles.viewStatValue}>
                                {formatUomRef(detail.uom)}
                              </span>
                            </div>
                            <div className={catalogueStyles.viewStat}>
                              <span className={catalogueStyles.viewStatLabel}>GST</span>
                              <span className={catalogueStyles.viewStatValue}>
                                {detail.gst_percent}%
                              </span>
                            </div>
                          </div>
                          {detail.item_description.trim() ? (
                            <p className={catalogueStyles.viewHeroDesc}>{detail.item_description}</p>
                          ) : null}
                        </div>
                      </div>

                      <div className={catalogueStyles.detailSections}>
                        <ViewDetailSection title="Classification" columns={2}>
                          <DetailField label="Category" value={detail.material_category?.name} />
                          <DetailField
                            label="Subcategory"
                            value={detail.material_subcategory?.name}
                          />
                          <DetailField
                            label="Material Type"
                            value={formatRef(detail.material_type)}
                          />
                          <DetailField
                            label="Material Group"
                            value={formatRef(detail.material_group)}
                          />
                        </ViewDetailSection>

                        <div className={catalogueStyles.detailSectionsSplit}>
                          <ViewDetailSection title="Specifications" columns={2}>
                            <DetailField
                              label="Descriptive Spec"
                              value={detail.descriptive_spec}
                              wide
                              muted
                            />
                            <DetailField
                              label="Technical Spec"
                              value={detail.technical_spec || "—"}
                              wide
                              muted
                            />
                          </ViewDetailSection>

                          <ViewDetailSection title="Commercial / Tax" columns={2}>
                            <DetailField label="HSN/SAC Code" value={detail.hsn_sac_code} />
                            <DetailField label="GST %" value={detail.gst_percent} />
                            <DetailField label="Price" value={detail.price} />
                            <DetailField
                              label="Purchasing Group"
                              value={formatRef(detail.purchasing_group)}
                            />
                          </ViewDetailSection>
                        </div>

                        <ViewDetailSection title="SAP / Organization" columns={3}>
                          <DetailField label="Plant" value={formatRef(detail.plant)} />
                          <DetailField label="Store Code" value={detail.store_code} />
                          <DetailField label="Stock Yard" value={formatRef(detail.stock_yard)} />
                          <DetailField label="Department" value={detail.department?.name} />
                          <DetailField label="Division" value={detail.division?.name ?? "—"} />
                          <DetailField label="Document Type" value={detail.document_type} />
                        </ViewDetailSection>

                        <ViewDetailSection title="System Information" columns={3}>
                          <DetailField
                            label="Status"
                            value={detail.is_active ? "Active" : "Inactive"}
                          />
                          <DetailField label="Created At" value={formatDate(detail.created_at)} />
                          <DetailField label="Updated At" value={formatDate(detail.updated_at)} />
                        </ViewDetailSection>
                      </div>
                    </>
                  ) : null}
                </div>
                {detail ? (
                  <div className={catalogueStyles.viewModalFooter}>
                    <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                      Close
                    </button>
                    <button
                      type="button"
                      className={styles.primaryBtn}
                      onClick={() => {
                        setForm(recordToForm(detail));
                        setModal("edit");
                      }}
                    >
                      Edit
                    </button>
                  </div>
                ) : null}
              </div>
            </>,
            document.body,
          )
        : null}

      {modal === "import" ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => {
              if (!importBusy) closeModal();
            }}
          />
          <div className={`${styles.modal} ${styles.importModal}`} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>
                  {importJob && TERMINAL_JOB_STATUSES.has(importJob.status)
                    ? importJob.status === "FAILED"
                      ? "Import Failed"
                      : "Import Completed"
                    : importPreview
                      ? "Validate Import"
                      : "Excel Import"}
                </h2>
                <p>
                  {importJob
                    ? importJob.progress_label || importJob.detail || "Processing in the background…"
                    : importPreview
                      ? "Review validation results before confirming import."
                      : validateState.isLoading
                        ? "Validating file…"
                        : "Choose a file via Upload Excel to validate."}
                </p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                disabled={importBusy && !formError}
                onClick={closeModal}
              >
                <CloseIcon />
              </button>
            </div>

            {validateState.isLoading ? <p className={styles.loading}>Validating…</p> : null}
            {formError ? <p className={styles.formError}>{formError}</p> : null}

            {importPreview && !importJob ? (
              <>
                <div className={styles.summary}>
                  <div className={styles.summaryCard}>
                    <span>Total</span>
                    <strong>{importPreview.total}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Valid</span>
                    <strong>{importPreview.valid}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Existing</span>
                    <strong>{importPreview.existing}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Duplicate</span>
                    <strong>{importPreview.duplicate}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Failed</span>
                    <strong>{importPreview.failed}</strong>
                  </div>
                  {importPreview.warnings ? (
                    <div className={styles.summaryCard}>
                      <span>Image Warnings</span>
                      <strong>{importPreview.warnings}</strong>
                    </div>
                  ) : null}
                </div>
                {importPreview.warnings ? (
                  <p className={styles.importDetail}>
                    {importPreview.warnings} row(s) have an invalid Item image URL. These materials
                    will be imported without an image.
                  </p>
                ) : null}
                {importPreview.missing_masters_summary.length > 0 ? (
                  <>
                    <p className={styles.importDetail}>Missing masters summary</p>
                    <ul className={styles.errorList}>
                      {importPreview.missing_masters_summary.map((line) => (
                        <li key={line} style={{ color: "var(--erp-text)" }}>
                          {line}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {importPreview.rows.length > 0 ? (
                  <div className={styles.previewTableWrap}>
                    <table className={styles.previewTable}>
                      <thead>
                        <tr>
                          <th>Row</th>
                          <th>SAP Code</th>
                          <th>Item Name</th>
                          <th>Status</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importPreview.rows.map((row) => (
                          <tr key={`${row.row}-${row.sap_code}`}>
                            <td>{row.row}</td>
                            <td>{row.sap_code}</td>
                            <td>{row.item_name}</td>
                            <td>{row.status}</td>
                            <td>{row.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <div className={styles.formActions}>
                  <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    disabled={importState.isLoading || !importFile}
                    onClick={onConfirmImport}
                  >
                    {importState.isLoading ? "Starting import…" : "Confirm Import"}
                  </button>
                </div>
              </>
            ) : null}

            {importJob ? (
              <>
                <div className={styles.progressBlock}>
                  <div className={styles.progressMeta}>
                    <strong>{importJob.status.replaceAll("_", " ")}</strong>
                    <span>{importJob.progress_label}</span>
                  </div>
                  <div className={styles.progressTrack}>
                    <div
                      className={styles.progressFill}
                      style={{ width: `${importJob.progress_percentage}%` }}
                    />
                  </div>
                </div>
                <div className={styles.summary}>
                  <div className={styles.summaryCard}>
                    <span>Total Rows</span>
                    <strong>{importJob.total_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Created</span>
                    <strong>{importJob.created_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Existing</span>
                    <strong>{importJob.skipped_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Failed</span>
                    <strong>{importJob.failed_rows}</strong>
                  </div>
                  {importJob.warning_rows ? (
                    <div className={styles.summaryCard}>
                      <span>Image Warnings</span>
                      <strong>{importJob.warning_rows}</strong>
                    </div>
                  ) : null}
                </div>
                {importJob.detail ? <p className={styles.importDetail}>{importJob.detail}</p> : null}
                <div className={styles.formActions}>
                  {importJob.has_error_file ? (
                    <button
                      type="button"
                      className={styles.secondaryBtn}
                      disabled={errorDownloadBusy}
                      onClick={onDownloadErrors}
                    >
                      {errorDownloadBusy
                        ? "Downloading…"
                        : importJob.failed_rows === 0 && importJob.warning_rows
                          ? "Download Warning Excel"
                          : "Download Error Excel"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    disabled={importBusy && !TERMINAL_JOB_STATUSES.has(importJob.status)}
                    onClick={closeModal}
                  >
                    {TERMINAL_JOB_STATUSES.has(importJob.status) ? "Done" : "Running…"}
                  </button>
                </div>
              </>
            ) : null}

            {formError && !importPreview && !importJob && !validateState.isLoading ? (
              <div className={styles.formActions}>
                <button type="button" className={styles.primaryBtn} onClick={closeModal}>
                  Close
                </button>
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {confirmDialog ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => !confirmBusy && setConfirmDialog(null)}
          />
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>Deactivate Material</h2>
                <p>The record will be marked inactive and can be activated later.</p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                disabled={confirmBusy}
                onClick={() => setConfirmDialog(null)}
              >
                <CloseIcon />
              </button>
            </div>
            <p className={styles.confirmMessage}>
              Deactivate material <strong>&quot;{confirmDialog.row.item_name}&quot;</strong> (
              {confirmDialog.row.sap_code})?
            </p>
            <div className={styles.formActions}>
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={confirmBusy}
                onClick={() => setConfirmDialog(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={confirmBusy}
                onClick={confirmDeactivate}
              >
                {confirmBusy ? "Please wait…" : "Deactivate"}
              </button>
            </div>
          </div>
        </>
      ) : null}

      {noticeDialog ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => setNoticeDialog(null)}
          />
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>{noticeDialog.title}</h2>
                <p>{noticeDialog.message}</p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                onClick={() => setNoticeDialog(null)}
              >
                <CloseIcon />
              </button>
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.primaryBtn} onClick={() => setNoticeDialog(null)}>
                OK
              </button>
            </div>
          </div>
        </>
      ) : null}
    </PageContainer>
  );
}
