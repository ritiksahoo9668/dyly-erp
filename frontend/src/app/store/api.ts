import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import { logout, type AuthState } from "@/app/store/authSlice";
import { env } from "@/config/env";
import type {
  AuthUser,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  LoginRequest,
  LoginResponse,
  ResetPasswordRequest,
} from "@/types/auth";
import type {
  AccessAssignment,
  AccessRegistryResponse,
  UserAccessResponse,
} from "@/types/access";
import type { HealthResponse } from "@/types/health";
import type {
  ImportJob,
  NameMasterImportPreview,
  NameMasterListParams,
  NameMasterListResponse,
  NameMasterRecord,
  NameMasterResource,
  NameMasterWritePayload,
} from "@/types/nameMaster";
import type {
  VerticalImportPreview,
  VerticalListParams,
  VerticalListResponse,
  VerticalRecord,
  VerticalWritePayload,
} from "@/types/vertical";
import type { UnitListParams, UnitListResponse, UnitRecord, UnitWritePayload } from "@/types/unit";
import type { UomListParams, UomListResponse, UomRecord, UomWritePayload } from "@/types/uom";
import type { MasterSummary } from "@/types/masterSummary";
import type {
  VendorImportPreview,
  VendorListParams,
  VendorListResponse,
  VendorRecord,
  VendorWritePayload,
} from "@/types/vendor";
import type {
  QcParameterImportPreview,
  QcParameterListParams,
  QcParameterListResponse,
  QcParameterRecord,
  QcParameterWritePayload,
} from "@/types/qcParameter";
import type {
  MaterialSubcategoryListParams,
  MaterialSubcategoryListResponse,
  MaterialSubcategoryRecord,
  MaterialSubcategoryWritePayload,
} from "@/types/materialSubcategory";
import type {
  StockYardListParams,
  StockYardListResponse,
  StockYardRecord,
  StockYardWritePayload,
} from "@/types/stockYard";
import type {
  MaterialGroupListParams,
  MaterialGroupListResponse,
  MaterialGroupRecord,
  MaterialGroupWritePayload,
} from "@/types/materialGroup";
import type {
  PurchasingGroupListParams,
  PurchasingGroupListResponse,
  PurchasingGroupRecord,
  PurchasingGroupWritePayload,
} from "@/types/purchasingGroup";
import type {
  PlantListParams,
  PlantListResponse,
  PlantRecord,
  PlantWritePayload,
} from "@/types/plant";
import type {
  MaterialTypeListParams,
  MaterialTypeListResponse,
  MaterialTypeRecord,
  MaterialTypeWritePayload,
} from "@/types/materialType";
import type {
  MaterialImportPreview,
  MaterialListParams,
  MaterialListResponse,
  MaterialRecord,
  MaterialWritePayload,
} from "@/types/material";
import type {
  EmployeeImportPreview,
  EmployeeListParams,
  EmployeeListResponse,
  EmployeeRecord,
  EmployeeStats,
  EmployeeWritePayload,
} from "@/types/employee";
import type {
  ActivateAccountRequest,
  ActivationValidateResponse,
  ErpUserListParams,
  ErpUserListResponse,
  ErpUserRecord,
  OnboardingEmployee,
  UserOnboardingDetail,
  UserOnboardingListParams,
  UserOnboardingListResponse,
  UserOnboardingStats,
  UserOnboardingWritePayload,
  UserRole,
} from "@/types/userOnboarding";

const rawBaseQuery = fetchBaseQuery({
  baseUrl: env.apiBaseUrl,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as { auth: AuthState }).auth.accessToken;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

const baseQueryWithAuth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  const result = await rawBaseQuery(args, api, extraOptions);
  const url = typeof args === "string" ? args : args.url;
  if (result.error && result.error.status === 401) {
    if (!url.includes("/api/v1/auth/login/") && !url.includes("/api/v1/auth/forgot-password/")) {
      api.dispatch(logout());
    }
  }
  if (result.error && result.error.status === 403 && !url.includes("/api/v1/auth/")) {
    // Access may have been revoked: refresh the current user so menus and routes follow.
    api.dispatch(baseApi.util.invalidateTags(["Me"]));
  }
  return result;
};

/** Master list URL, or its open `lookup/` variant used by dropdowns. */
function masterBase(resource: string, lookup?: boolean) {
  return `/api/v1/master/${resource}/${lookup ? "lookup/" : ""}`;
}

function buildListUrl(resource: NameMasterResource, params: NameMasterListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase(resource, params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildVerticalListUrl(params: VerticalListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (typeof params.department === "number") search.set("department", String(params.department));
  const qs = search.toString();
  const base = masterBase("verticals", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildUomListUrl(params: UomListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("uoms", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildQcParameterListUrl(params: QcParameterListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = "/api/v1/master/qc-parameters/";
  return qs ? `${base}?${qs}` : base;
}

function buildVendorListUrl(params: VendorListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (params.location) search.set("location", params.location);
  if (params.ordering) search.set("ordering", params.ordering);
  const qs = search.toString();
  const base = "/api/v1/master/vendors/";
  return qs ? `${base}?${qs}` : base;
}

function buildStockYardListUrl(params: StockYardListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("stock-yards", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildMaterialGroupListUrl(params: MaterialGroupListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("material-groups", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildPurchasingGroupListUrl(params: PurchasingGroupListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("purchasing-groups", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildPlantListUrl(params: PlantListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("plants", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildMaterialTypeListUrl(params: MaterialTypeListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  const qs = search.toString();
  const base = masterBase("material-types", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildMaterialListUrl(params: MaterialListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (params.ordering) search.set("ordering", params.ordering);
  const filterKeys = [
    "material_category",
    "material_subcategory",
    "uom",
    "material_type",
    "material_group",
    "purchasing_group",
    "plant",
    "stock_yard",
    "department",
    "division",
  ] as const;
  for (const key of filterKeys) {
    const value = params[key];
    if (typeof value === "number") search.set(key, String(value));
  }
  const qs = search.toString();
  const base = "/api/v1/master/materials/";
  return qs ? `${base}?${qs}` : base;
}

function buildEmployeeListUrl(params: EmployeeListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (params.ordering) search.set("ordering", params.ordering);
  if (params.gender) search.set("gender", params.gender);
  const filterKeys = [
    "department",
    "vertical",
    "designation",
    "company",
    "division",
    "facility",
  ] as const;
  for (const key of filterKeys) {
    const value = params[key];
    if (typeof value === "number") search.set(key, String(value));
  }
  const qs = search.toString();
  const base = "/api/v1/master/employees/";
  return qs ? `${base}?${qs}` : base;
}

function buildUnitListUrl(params: UnitListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (typeof params.company === "number") search.set("company", String(params.company));
  const qs = search.toString();
  const base = masterBase("units", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

function buildQueryUrl(base: string, params: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    const text = String(value).trim();
    if (text) search.set(key, text);
  }
  const qs = search.toString();
  return qs ? `${base}?${qs}` : base;
}

const ONBOARDING_BASE = "/api/v1/user-onboarding/";
const ERP_USERS_BASE = "/api/v1/users/";

function buildMaterialSubcategoryListUrl(params: MaterialSubcategoryListParams = {}) {
  const search = new URLSearchParams();
  if (params.search?.trim()) search.set("search", params.search.trim());
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
  if (typeof params.category === "number") search.set("category", String(params.category));
  const qs = search.toString();
  const base = masterBase("material-subcategories", params.lookup);
  return qs ? `${base}?${qs}` : base;
}

type MasterTag =
  | "Division"
  | "Department"
  | "Designation"
  | "Facility"
  | "Company"
  | "Vertical"
  | "Uom"
  | "MaterialCategory"
  | "WeighBridge";

function listProvides(tag: MasterTag) {
  return (result: NameMasterListResponse | undefined) =>
    result
      ? [...result.results.map(({ id }) => ({ type: tag, id })), { type: tag, id: "LIST" as const }]
      : [{ type: tag, id: "LIST" as const }];
}

export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithAuth,
  tagTypes: [
    "Me",
    "Division",
    "Department",
    "Designation",
    "Facility",
    "Company",
    "Unit",
    "Vertical",
    "Uom",
    "MaterialCategory",
    "MaterialSubcategory",
    "StockYard",
    "MaterialGroup",
    "PurchasingGroup",
    "Plant",
    "WeighBridge",
    "MaterialType",
    "Material",
    "Employee",
    "QcParameter",
    "Vendor",
    "ImportJob",
    "UserOnboarding",
    "ErpUser",
    "UserAccess",
  ],
  endpoints: (builder) => ({
    getHealth: builder.query<HealthResponse, void>({
      query: () => "/api/v1/health/",
    }),
    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (body) => ({
        url: "/api/v1/auth/login/",
        method: "POST",
        body,
      }),
    }),
    getMe: builder.query<AuthUser, void>({
      query: () => "/api/v1/auth/me/",
      providesTags: ["Me"],
    }),
    forgotPassword: builder.mutation<ForgotPasswordResponse, ForgotPasswordRequest>({
      query: (body) => ({
        url: "/api/v1/auth/forgot-password/",
        method: "POST",
        body,
      }),
    }),
    resetPassword: builder.mutation<{ detail: string }, ResetPasswordRequest>({
      query: (body) => ({
        url: "/api/v1/auth/reset-password/",
        method: "POST",
        body,
      }),
    }),

    getDivisions: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("divisions", params ?? {}),
      providesTags: listProvides("Division"),
    }),
    createDivision: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/divisions/", method: "POST", body }),
      invalidatesTags: [{ type: "Division", id: "LIST" }],
    }),
    updateDivision: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({ url: `/api/v1/master/divisions/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Division", id },
        { type: "Division", id: "LIST" },
      ],
    }),
    deactivateDivision: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/divisions/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Division", id },
        { type: "Division", id: "LIST" },
      ],
    }),
    validateDivisions: builder.mutation<NameMasterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/divisions/validate/", method: "POST", body };
      },
    }),
    importDivisions: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/divisions/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Division", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getDepartments: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("departments", params ?? {}),
      providesTags: listProvides("Department"),
    }),
    createDepartment: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/departments/", method: "POST", body }),
      invalidatesTags: [{ type: "Department", id: "LIST" }],
    }),
    updateDepartment: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/departments/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Department", id },
        { type: "Department", id: "LIST" },
      ],
    }),
    deactivateDepartment: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/departments/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Department", id },
        { type: "Department", id: "LIST" },
      ],
    }),
    validateDepartments: builder.mutation<NameMasterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/departments/validate/", method: "POST", body };
      },
    }),
    importDepartments: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/departments/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Department", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getDesignations: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("designations", params ?? {}),
      providesTags: listProvides("Designation"),
    }),
    createDesignation: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/designations/", method: "POST", body }),
      invalidatesTags: [{ type: "Designation", id: "LIST" }],
    }),
    updateDesignation: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/designations/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Designation", id },
        { type: "Designation", id: "LIST" },
      ],
    }),
    deactivateDesignation: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/designations/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Designation", id },
        { type: "Designation", id: "LIST" },
      ],
    }),
    validateDesignations: builder.mutation<NameMasterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/designations/validate/", method: "POST", body };
      },
    }),
    importDesignations: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/designations/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Designation", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getFacilities: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("facilities", params ?? {}),
      providesTags: listProvides("Facility"),
    }),
    createFacility: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/facilities/", method: "POST", body }),
      invalidatesTags: [{ type: "Facility", id: "LIST" }],
    }),
    updateFacility: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({ url: `/api/v1/master/facilities/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Facility", id },
        { type: "Facility", id: "LIST" },
      ],
    }),
    deactivateFacility: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/facilities/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Facility", id },
        { type: "Facility", id: "LIST" },
      ],
    }),
    validateFacilities: builder.mutation<NameMasterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/facilities/validate/", method: "POST", body };
      },
    }),
    importFacilities: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/facilities/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Facility", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getCompanies: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("companies", params ?? {}),
      providesTags: listProvides("Company"),
    }),
    createCompany: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/companies/", method: "POST", body }),
      invalidatesTags: [{ type: "Company", id: "LIST" }],
    }),
    updateCompany: builder.mutation<NameMasterRecord, { id: number; body: NameMasterWritePayload }>(
      {
        query: ({ id, body }) => ({
          url: `/api/v1/master/companies/${id}/`,
          method: "PATCH",
          body,
        }),
        invalidatesTags: (_r, _e, { id }) => [
          { type: "Company", id },
          { type: "Company", id: "LIST" },
          { type: "Unit", id: "LIST" },
        ],
      },
    ),
    deactivateCompany: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/companies/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Company", id },
        { type: "Company", id: "LIST" },
        { type: "Unit", id: "LIST" },
      ],
    }),
    validateCompanies: builder.mutation<NameMasterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/companies/validate/", method: "POST", body };
      },
    }),
    importCompanies: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/companies/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Company", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getUnits: builder.query<UnitListResponse, UnitListParams | void>({
      query: (params) => buildUnitListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Unit" as const, id })),
              { type: "Unit" as const, id: "LIST" },
            ]
          : [{ type: "Unit" as const, id: "LIST" }],
    }),
    createUnit: builder.mutation<UnitRecord, UnitWritePayload>({
      query: (body) => ({ url: "/api/v1/master/units/", method: "POST", body }),
      invalidatesTags: [
        { type: "Unit", id: "LIST" },
        { type: "Company", id: "LIST" },
      ],
    }),
    updateUnit: builder.mutation<UnitRecord, { id: number; body: Partial<UnitWritePayload> }>({
      query: ({ id, body }) => ({ url: `/api/v1/master/units/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Unit", id },
        { type: "Unit", id: "LIST" },
        { type: "Company", id: "LIST" },
      ],
    }),
    deactivateUnit: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/units/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Unit", id },
        { type: "Unit", id: "LIST" },
        { type: "Company", id: "LIST" },
      ],
    }),
    importUnits: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/units/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Unit", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getWeighBridges: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("weighbridges", params ?? {}),
      providesTags: listProvides("WeighBridge"),
    }),
    createWeighBridge: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/weighbridges/", method: "POST", body }),
      invalidatesTags: [{ type: "WeighBridge", id: "LIST" }],
    }),
    updateWeighBridge: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/weighbridges/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "WeighBridge", id },
        { type: "WeighBridge", id: "LIST" },
      ],
    }),
    deactivateWeighBridge: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/weighbridges/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "WeighBridge", id },
        { type: "WeighBridge", id: "LIST" },
      ],
    }),
    importWeighBridges: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/weighbridges/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "WeighBridge", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getVerticals: builder.query<VerticalListResponse, VerticalListParams | void>({
      query: (params) => buildVerticalListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Vertical" as const, id })),
              { type: "Vertical" as const, id: "LIST" },
            ]
          : [{ type: "Vertical" as const, id: "LIST" }],
    }),
    createVertical: builder.mutation<VerticalRecord, VerticalWritePayload>({
      query: (body) => ({ url: "/api/v1/master/verticals/", method: "POST", body }),
      invalidatesTags: [{ type: "Vertical", id: "LIST" }],
    }),
    updateVertical: builder.mutation<VerticalRecord, { id: number; body: VerticalWritePayload }>({
      query: ({ id, body }) => ({ url: `/api/v1/master/verticals/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Vertical", id },
        { type: "Vertical", id: "LIST" },
      ],
    }),
    deactivateVertical: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/verticals/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Vertical", id },
        { type: "Vertical", id: "LIST" },
      ],
    }),
    validateVerticals: builder.mutation<VerticalImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/verticals/validate/", method: "POST", body };
      },
    }),
    importVerticals: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/verticals/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Vertical", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getUoms: builder.query<UomListResponse, UomListParams | void>({
      query: (params) => buildUomListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Uom" as const, id })),
              { type: "Uom" as const, id: "LIST" },
            ]
          : [{ type: "Uom" as const, id: "LIST" }],
    }),
    createUom: builder.mutation<UomRecord, UomWritePayload>({
      query: (body) => ({ url: "/api/v1/master/uoms/", method: "POST", body }),
      invalidatesTags: [{ type: "Uom", id: "LIST" }],
    }),
    updateUom: builder.mutation<UomRecord, { id: number; body: UomWritePayload }>({
      query: ({ id, body }) => ({ url: `/api/v1/master/uoms/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Uom", id },
        { type: "Uom", id: "LIST" },
      ],
    }),
    deactivateUom: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/uoms/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Uom", id },
        { type: "Uom", id: "LIST" },
      ],
    }),
    importUoms: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/uoms/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Uom", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getMaterialCategories: builder.query<NameMasterListResponse, NameMasterListParams | void>({
      query: (params) => buildListUrl("material-categories", params ?? {}),
      providesTags: listProvides("MaterialCategory"),
    }),
    createMaterialCategory: builder.mutation<NameMasterRecord, NameMasterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/material-categories/", method: "POST", body }),
      invalidatesTags: [{ type: "MaterialCategory", id: "LIST" }],
    }),
    updateMaterialCategory: builder.mutation<
      NameMasterRecord,
      { id: number; body: NameMasterWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/material-categories/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "MaterialCategory", id },
        { type: "MaterialCategory", id: "LIST" },
      ],
    }),
    deactivateMaterialCategory: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/material-categories/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "MaterialCategory", id },
        { type: "MaterialCategory", id: "LIST" },
      ],
    }),
    importMaterialCategories: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/material-categories/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "MaterialCategory", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getMaterialSubcategories: builder.query<
      MaterialSubcategoryListResponse,
      MaterialSubcategoryListParams | void
    >({
      query: (params) => buildMaterialSubcategoryListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "MaterialSubcategory" as const, id })),
              { type: "MaterialSubcategory" as const, id: "LIST" },
            ]
          : [{ type: "MaterialSubcategory" as const, id: "LIST" }],
    }),
    createMaterialSubcategory: builder.mutation<
      MaterialSubcategoryRecord,
      MaterialSubcategoryWritePayload
    >({
      query: (body) => ({ url: "/api/v1/master/material-subcategories/", method: "POST", body }),
      invalidatesTags: [{ type: "MaterialSubcategory", id: "LIST" }],
    }),
    updateMaterialSubcategory: builder.mutation<
      MaterialSubcategoryRecord,
      { id: number; body: MaterialSubcategoryWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/material-subcategories/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "MaterialSubcategory", id },
        { type: "MaterialSubcategory", id: "LIST" },
      ],
    }),
    deactivateMaterialSubcategory: builder.mutation<void, number>({
      query: (id) => ({
        url: `/api/v1/master/material-subcategories/${id}/`,
        method: "DELETE",
      }),
      invalidatesTags: (_r, _e, id) => [
        { type: "MaterialSubcategory", id },
        { type: "MaterialSubcategory", id: "LIST" },
      ],
    }),
    importMaterialSubcategories: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/material-subcategories/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "MaterialSubcategory", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getStockYards: builder.query<StockYardListResponse, StockYardListParams | void>({
      query: (params) => buildStockYardListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "StockYard" as const, id })),
              { type: "StockYard" as const, id: "LIST" },
            ]
          : [{ type: "StockYard" as const, id: "LIST" }],
    }),
    createStockYard: builder.mutation<StockYardRecord, StockYardWritePayload>({
      query: (body) => ({ url: "/api/v1/master/stock-yards/", method: "POST", body }),
      invalidatesTags: [{ type: "StockYard", id: "LIST" }],
    }),
    updateStockYard: builder.mutation<StockYardRecord, { id: number; body: StockYardWritePayload }>(
      {
        query: ({ id, body }) => ({
          url: `/api/v1/master/stock-yards/${id}/`,
          method: "PATCH",
          body,
        }),
        invalidatesTags: (_r, _e, { id }) => [
          { type: "StockYard", id },
          { type: "StockYard", id: "LIST" },
        ],
      },
    ),
    deactivateStockYard: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/stock-yards/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "StockYard", id },
        { type: "StockYard", id: "LIST" },
      ],
    }),
    importStockYards: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/stock-yards/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "StockYard", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getMaterialGroups: builder.query<MaterialGroupListResponse, MaterialGroupListParams | void>({
      query: (params) => buildMaterialGroupListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "MaterialGroup" as const, id })),
              { type: "MaterialGroup" as const, id: "LIST" },
            ]
          : [{ type: "MaterialGroup" as const, id: "LIST" }],
    }),
    createMaterialGroup: builder.mutation<MaterialGroupRecord, MaterialGroupWritePayload>({
      query: (body) => ({ url: "/api/v1/master/material-groups/", method: "POST", body }),
      invalidatesTags: [{ type: "MaterialGroup", id: "LIST" }],
    }),
    updateMaterialGroup: builder.mutation<
      MaterialGroupRecord,
      { id: number; body: MaterialGroupWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/material-groups/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "MaterialGroup", id },
        { type: "MaterialGroup", id: "LIST" },
      ],
    }),
    deactivateMaterialGroup: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/material-groups/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "MaterialGroup", id },
        { type: "MaterialGroup", id: "LIST" },
      ],
    }),
    importMaterialGroups: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/material-groups/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "MaterialGroup", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getPurchasingGroups: builder.query<
      PurchasingGroupListResponse,
      PurchasingGroupListParams | void
    >({
      query: (params) => buildPurchasingGroupListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "PurchasingGroup" as const, id })),
              { type: "PurchasingGroup" as const, id: "LIST" },
            ]
          : [{ type: "PurchasingGroup" as const, id: "LIST" }],
    }),
    createPurchasingGroup: builder.mutation<PurchasingGroupRecord, PurchasingGroupWritePayload>({
      query: (body) => ({ url: "/api/v1/master/purchasing-groups/", method: "POST", body }),
      invalidatesTags: [{ type: "PurchasingGroup", id: "LIST" }],
    }),
    updatePurchasingGroup: builder.mutation<
      PurchasingGroupRecord,
      { id: number; body: PurchasingGroupWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/purchasing-groups/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "PurchasingGroup", id },
        { type: "PurchasingGroup", id: "LIST" },
      ],
    }),
    deactivatePurchasingGroup: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/purchasing-groups/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "PurchasingGroup", id },
        { type: "PurchasingGroup", id: "LIST" },
      ],
    }),
    importPurchasingGroups: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/purchasing-groups/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "PurchasingGroup", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getPlants: builder.query<PlantListResponse, PlantListParams | void>({
      query: (params) => buildPlantListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Plant" as const, id })),
              { type: "Plant" as const, id: "LIST" },
            ]
          : [{ type: "Plant" as const, id: "LIST" }],
    }),
    createPlant: builder.mutation<PlantRecord, PlantWritePayload>({
      query: (body) => ({ url: "/api/v1/master/plants/", method: "POST", body }),
      invalidatesTags: [{ type: "Plant", id: "LIST" }],
    }),
    updatePlant: builder.mutation<PlantRecord, { id: number; body: PlantWritePayload }>({
      query: ({ id, body }) => ({
        url: `/api/v1/master/plants/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Plant", id },
        { type: "Plant", id: "LIST" },
      ],
    }),
    deactivatePlant: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/plants/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Plant", id },
        { type: "Plant", id: "LIST" },
      ],
    }),
    importPlants: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/plants/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Plant", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getMaterialTypes: builder.query<MaterialTypeListResponse, MaterialTypeListParams | void>({
      query: (params) => buildMaterialTypeListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "MaterialType" as const, id })),
              { type: "MaterialType" as const, id: "LIST" },
            ]
          : [{ type: "MaterialType" as const, id: "LIST" }],
    }),
    createMaterialType: builder.mutation<MaterialTypeRecord, MaterialTypeWritePayload>({
      query: (body) => ({ url: "/api/v1/master/material-types/", method: "POST", body }),
      invalidatesTags: [{ type: "MaterialType", id: "LIST" }],
    }),
    updateMaterialType: builder.mutation<
      MaterialTypeRecord,
      { id: number; body: MaterialTypeWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/material-types/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "MaterialType", id },
        { type: "MaterialType", id: "LIST" },
      ],
    }),
    deactivateMaterialType: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/material-types/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "MaterialType", id },
        { type: "MaterialType", id: "LIST" },
      ],
    }),
    importMaterialTypes: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/material-types/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "MaterialType", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getMaterials: builder.query<MaterialListResponse, MaterialListParams | void>({
      query: (params) => buildMaterialListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Material" as const, id })),
              { type: "Material" as const, id: "LIST" },
            ]
          : [{ type: "Material" as const, id: "LIST" }],
    }),
    getMaterial: builder.query<MaterialRecord, number>({
      query: (id) => `/api/v1/master/materials/${id}/`,
      providesTags: (_r, _e, id) => [{ type: "Material", id }],
    }),
    createMaterial: builder.mutation<MaterialRecord, MaterialWritePayload>({
      query: (body) => ({ url: "/api/v1/master/materials/", method: "POST", body }),
      invalidatesTags: [{ type: "Material", id: "LIST" }],
    }),
    updateMaterial: builder.mutation<MaterialRecord, { id: number; body: MaterialWritePayload }>({
      query: ({ id, body }) => ({
        url: `/api/v1/master/materials/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),
    deactivateMaterial: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/materials/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),
    activateMaterial: builder.mutation<MaterialRecord, number>({
      query: (id) => ({ url: `/api/v1/master/materials/${id}/activate/`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),
    validateMaterials: builder.mutation<MaterialImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/materials/validate/", method: "POST", body };
      },
    }),
    importMaterials: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/materials/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Material", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),
    uploadMaterialImage: builder.mutation<MaterialRecord, { id: number; file: File }>({
      query: ({ id, file }) => {
        const body = new FormData();
        body.append("file", file);
        return { url: `/api/v1/master/materials/${id}/image/upload/`, method: "POST", body };
      },
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),
    setMaterialImageUrl: builder.mutation<MaterialRecord, { id: number; image_url: string }>({
      query: ({ id, image_url }) => ({
        url: `/api/v1/master/materials/${id}/image/url/`,
        method: "POST",
        body: { image_url },
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),
    removeMaterialImage: builder.mutation<MaterialRecord, number>({
      query: (id) => ({ url: `/api/v1/master/materials/${id}/image/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Material", id },
        { type: "Material", id: "LIST" },
      ],
    }),

    getEmployees: builder.query<EmployeeListResponse, EmployeeListParams | void>({
      query: (params) => buildEmployeeListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Employee" as const, id })),
              { type: "Employee" as const, id: "LIST" },
            ]
          : [{ type: "Employee" as const, id: "LIST" }],
    }),
    getQcParameters: builder.query<QcParameterListResponse, QcParameterListParams | void>({
      query: (params) => buildQcParameterListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "QcParameter" as const, id })),
              { type: "QcParameter" as const, id: "LIST" },
            ]
          : [{ type: "QcParameter" as const, id: "LIST" }],
    }),
    createQcParameter: builder.mutation<QcParameterRecord, QcParameterWritePayload>({
      query: (body) => ({ url: "/api/v1/master/qc-parameters/", method: "POST", body }),
      invalidatesTags: [{ type: "QcParameter", id: "LIST" }],
    }),
    updateQcParameter: builder.mutation<
      QcParameterRecord,
      { id: number; body: QcParameterWritePayload }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/qc-parameters/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "QcParameter", id },
        { type: "QcParameter", id: "LIST" },
      ],
    }),
    deactivateQcParameter: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/qc-parameters/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "QcParameter", id },
        { type: "QcParameter", id: "LIST" },
      ],
    }),
    activateQcParameter: builder.mutation<QcParameterRecord, number>({
      query: (id) => ({ url: `/api/v1/master/qc-parameters/${id}/activate/`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "QcParameter", id },
        { type: "QcParameter", id: "LIST" },
      ],
    }),
    validateQcParameters: builder.mutation<QcParameterImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/qc-parameters/validate/", method: "POST", body };
      },
    }),
    importQcParameters: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/qc-parameters/import/", method: "POST", body };
      },
      invalidatesTags: [{ type: "ImportJob", id: "LIST" }],
    }),
    getMasterSummary: builder.query<MasterSummary, void>({
      query: () => "/api/v1/master/summary/",
    }),
    getVendors: builder.query<VendorListResponse, VendorListParams | void>({
      query: (params) => buildVendorListUrl(params ?? {}),
      providesTags: (result) =>
        result
          ? [
              ...result.results.map(({ id }) => ({ type: "Vendor" as const, id })),
              { type: "Vendor" as const, id: "LIST" },
            ]
          : [{ type: "Vendor" as const, id: "LIST" }],
    }),
    getVendorLocations: builder.query<string[], void>({
      query: () => "/api/v1/master/vendors/locations/",
      providesTags: [{ type: "Vendor", id: "LIST" }],
    }),
    createVendor: builder.mutation<VendorRecord, VendorWritePayload>({
      query: (body) => ({ url: "/api/v1/master/vendors/", method: "POST", body }),
      invalidatesTags: [{ type: "Vendor", id: "LIST" }],
    }),
    updateVendor: builder.mutation<VendorRecord, { id: number; body: VendorWritePayload }>({
      query: ({ id, body }) => ({ url: `/api/v1/master/vendors/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Vendor", id },
        { type: "Vendor", id: "LIST" },
      ],
    }),
    deactivateVendor: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/vendors/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Vendor", id },
        { type: "Vendor", id: "LIST" },
      ],
    }),
    activateVendor: builder.mutation<VendorRecord, number>({
      query: (id) => ({ url: `/api/v1/master/vendors/${id}/activate/`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Vendor", id },
        { type: "Vendor", id: "LIST" },
      ],
    }),
    validateVendors: builder.mutation<VendorImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/vendors/validate/", method: "POST", body };
      },
    }),
    importVendors: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/vendors/import/", method: "POST", body };
      },
      invalidatesTags: [{ type: "ImportJob", id: "LIST" }],
    }),
    getEmployeeStats: builder.query<EmployeeStats, void>({
      query: () => "/api/v1/master/employees/stats/",
      providesTags: [{ type: "Employee", id: "LIST" }],
    }),
    bulkSetEmployeeStatus: builder.mutation<
      { updated: number },
      { ids: number[]; is_active: boolean }
    >({
      query: (body) => ({ url: "/api/v1/master/employees/bulk-status/", method: "POST", body }),
      invalidatesTags: (_r, _e, { ids }) => [
        ...ids.map((id) => ({ type: "Employee" as const, id })),
        { type: "Employee" as const, id: "LIST" },
      ],
    }),
    getEmployee: builder.query<EmployeeRecord, number>({
      query: (id) => `/api/v1/master/employees/${id}/`,
      providesTags: (_r, _e, id) => [{ type: "Employee", id }],
    }),
    createEmployee: builder.mutation<EmployeeRecord, EmployeeWritePayload>({
      query: (body) => ({ url: "/api/v1/master/employees/", method: "POST", body }),
      invalidatesTags: [{ type: "Employee", id: "LIST" }],
    }),
    updateEmployee: builder.mutation<
      EmployeeRecord,
      { id: number; body: Partial<EmployeeWritePayload> }
    >({
      query: ({ id, body }) => ({
        url: `/api/v1/master/employees/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Employee", id },
        { type: "Employee", id: "LIST" },
      ],
    }),
    deactivateEmployee: builder.mutation<void, number>({
      query: (id) => ({ url: `/api/v1/master/employees/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Employee", id },
        { type: "Employee", id: "LIST" },
      ],
    }),
    activateEmployee: builder.mutation<EmployeeRecord, number>({
      query: (id) => ({ url: `/api/v1/master/employees/${id}/activate/`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Employee", id },
        { type: "Employee", id: "LIST" },
      ],
    }),
    validateEmployees: builder.mutation<EmployeeImportPreview, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/employees/validate/", method: "POST", body };
      },
    }),
    importEmployees: builder.mutation<ImportJob, File>({
      query: (file) => {
        const body = new FormData();
        body.append("file", file);
        return { url: "/api/v1/master/employees/import/", method: "POST", body };
      },
      invalidatesTags: [
        { type: "Employee", id: "LIST" },
        { type: "ImportJob", id: "LIST" },
      ],
    }),

    getImportJob: builder.query<ImportJob, number>({
      query: (id) => `/api/v1/master/import-jobs/${id}/`,
      providesTags: (_r, _e, id) => [{ type: "ImportJob", id }],
    }),

    getUserOnboardings: builder.query<UserOnboardingListResponse, UserOnboardingListParams>({
      query: (params) => buildQueryUrl(ONBOARDING_BASE, params),
      providesTags: [{ type: "UserOnboarding", id: "LIST" }],
    }),
    getUserOnboardingStats: builder.query<UserOnboardingStats, void>({
      query: () => `${ONBOARDING_BASE}stats/`,
      providesTags: [{ type: "UserOnboarding", id: "STATS" }],
    }),
    getUserOnboarding: builder.query<UserOnboardingDetail, number>({
      query: (id) => `${ONBOARDING_BASE}${id}/`,
      providesTags: (_r, _e, id) => [{ type: "UserOnboarding", id }],
    }),
    getOnboardingEmployeeOptions: builder.query<OnboardingEmployee[], void>({
      query: () => `${ONBOARDING_BASE}employee-options/`,
      providesTags: [{ type: "UserOnboarding", id: "EMPLOYEE_OPTIONS" }],
    }),
    createUserOnboarding: builder.mutation<UserOnboardingDetail, UserOnboardingWritePayload>({
      query: (body) => ({ url: ONBOARDING_BASE, method: "POST", body }),
      invalidatesTags: ["UserOnboarding", "ErpUser"],
    }),
    updateUserOnboarding: builder.mutation<
      UserOnboardingDetail,
      { id: number; body: Partial<UserOnboardingWritePayload> }
    >({
      query: ({ id, body }) => ({ url: `${ONBOARDING_BASE}${id}/`, method: "PATCH", body }),
      invalidatesTags: ["UserOnboarding", "ErpUser"],
    }),
    discardUserOnboarding: builder.mutation<void, number>({
      query: (id) => ({ url: `${ONBOARDING_BASE}${id}/`, method: "DELETE" }),
      invalidatesTags: ["UserOnboarding"],
    }),
    onboardingAction: builder.mutation<
      UserOnboardingDetail,
      { id: number; action: "send-invite" | "resend-invite" | "revoke" }
    >({
      query: ({ id, action }) => ({ url: `${ONBOARDING_BASE}${id}/${action}/`, method: "POST" }),
      invalidatesTags: ["UserOnboarding", "ErpUser"],
    }),
    getErpUsers: builder.query<ErpUserListResponse, ErpUserListParams>({
      query: (params) => buildQueryUrl(ERP_USERS_BASE, params),
      providesTags: [{ type: "ErpUser", id: "LIST" }],
    }),
    setErpUserActive: builder.mutation<ErpUserRecord, { id: number; active: boolean }>({
      query: ({ id, active }) => ({
        url: `${ERP_USERS_BASE}${id}/${active ? "activate" : "deactivate"}/`,
        method: "POST",
      }),
      invalidatesTags: ["ErpUser", "UserOnboarding"],
    }),
    changeErpUserRole: builder.mutation<ErpUserRecord, { id: number; role: UserRole }>({
      query: ({ id, role }) => ({
        url: `${ERP_USERS_BASE}${id}/change-role/`,
        method: "POST",
        body: { role },
      }),
      invalidatesTags: ["ErpUser", "UserOnboarding", "UserAccess"],
    }),
    getAccessRegistry: builder.query<AccessRegistryResponse, void>({
      query: () => "/api/v1/auth/access-registry/",
      keepUnusedDataFor: 3600,
    }),
    getUserAccess: builder.query<UserAccessResponse, number>({
      query: (id) => `${ERP_USERS_BASE}${id}/access/`,
      providesTags: (_r, _e, id) => [{ type: "UserAccess", id }],
    }),
    updateUserAccess: builder.mutation<UserAccessResponse, { id: number; access: AccessAssignment }>({
      query: ({ id, access }) => ({
        url: `${ERP_USERS_BASE}${id}/access/`,
        method: "PUT",
        body: { access },
      }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "UserAccess", id },
        "ErpUser",
        "UserOnboarding",
      ],
    }),
    validateActivationToken: builder.mutation<ActivationValidateResponse, { token: string }>({
      query: (body) => ({ url: "/api/v1/auth/activation/validate/", method: "POST", body }),
    }),
    activateAccount: builder.mutation<{ detail: string }, ActivateAccountRequest>({
      query: (body) => ({ url: "/api/v1/auth/activation/activate/", method: "POST", body }),
    }),
  }),
});

export const {
  useGetHealthQuery,
  useLoginMutation,
  useGetMeQuery,
  useGetAccessRegistryQuery,
  useGetUserAccessQuery,
  useUpdateUserAccessMutation,
  useForgotPasswordMutation,
  useResetPasswordMutation,
  useGetDivisionsQuery,
  useCreateDivisionMutation,
  useUpdateDivisionMutation,
  useDeactivateDivisionMutation,
  useValidateDivisionsMutation,
  useImportDivisionsMutation,
  useGetDepartmentsQuery,
  useCreateDepartmentMutation,
  useUpdateDepartmentMutation,
  useDeactivateDepartmentMutation,
  useValidateDepartmentsMutation,
  useImportDepartmentsMutation,
  useGetDesignationsQuery,
  useCreateDesignationMutation,
  useUpdateDesignationMutation,
  useDeactivateDesignationMutation,
  useValidateDesignationsMutation,
  useImportDesignationsMutation,
  useGetFacilitiesQuery,
  useCreateFacilityMutation,
  useUpdateFacilityMutation,
  useDeactivateFacilityMutation,
  useValidateFacilitiesMutation,
  useImportFacilitiesMutation,
  useGetCompaniesQuery,
  useCreateCompanyMutation,
  useUpdateCompanyMutation,
  useDeactivateCompanyMutation,
  useValidateCompaniesMutation,
  useImportCompaniesMutation,
  useGetUnitsQuery,
  useCreateUnitMutation,
  useUpdateUnitMutation,
  useDeactivateUnitMutation,
  useImportUnitsMutation,
  useGetWeighBridgesQuery,
  useCreateWeighBridgeMutation,
  useUpdateWeighBridgeMutation,
  useDeactivateWeighBridgeMutation,
  useImportWeighBridgesMutation,
  useGetVerticalsQuery,
  useCreateVerticalMutation,
  useUpdateVerticalMutation,
  useDeactivateVerticalMutation,
  useValidateVerticalsMutation,
  useImportVerticalsMutation,
  useGetUomsQuery,
  useCreateUomMutation,
  useUpdateUomMutation,
  useDeactivateUomMutation,
  useImportUomsMutation,
  useGetMaterialCategoriesQuery,
  useCreateMaterialCategoryMutation,
  useUpdateMaterialCategoryMutation,
  useDeactivateMaterialCategoryMutation,
  useImportMaterialCategoriesMutation,
  useGetMaterialSubcategoriesQuery,
  useCreateMaterialSubcategoryMutation,
  useUpdateMaterialSubcategoryMutation,
  useDeactivateMaterialSubcategoryMutation,
  useImportMaterialSubcategoriesMutation,
  useGetStockYardsQuery,
  useCreateStockYardMutation,
  useUpdateStockYardMutation,
  useDeactivateStockYardMutation,
  useImportStockYardsMutation,
  useGetMaterialGroupsQuery,
  useCreateMaterialGroupMutation,
  useUpdateMaterialGroupMutation,
  useDeactivateMaterialGroupMutation,
  useImportMaterialGroupsMutation,
  useGetPurchasingGroupsQuery,
  useCreatePurchasingGroupMutation,
  useUpdatePurchasingGroupMutation,
  useDeactivatePurchasingGroupMutation,
  useImportPurchasingGroupsMutation,
  useGetPlantsQuery,
  useCreatePlantMutation,
  useUpdatePlantMutation,
  useDeactivatePlantMutation,
  useImportPlantsMutation,
  useGetMaterialTypesQuery,
  useCreateMaterialTypeMutation,
  useUpdateMaterialTypeMutation,
  useDeactivateMaterialTypeMutation,
  useImportMaterialTypesMutation,
  useGetMaterialsQuery,
  useGetMaterialQuery,
  useLazyGetMaterialQuery,
  useCreateMaterialMutation,
  useUpdateMaterialMutation,
  useDeactivateMaterialMutation,
  useActivateMaterialMutation,
  useValidateMaterialsMutation,
  useImportMaterialsMutation,
  useUploadMaterialImageMutation,
  useSetMaterialImageUrlMutation,
  useRemoveMaterialImageMutation,
  useGetEmployeesQuery,
  useGetEmployeeStatsQuery,
  useBulkSetEmployeeStatusMutation,
  useLazyGetEmployeeQuery,
  useCreateEmployeeMutation,
  useUpdateEmployeeMutation,
  useDeactivateEmployeeMutation,
  useActivateEmployeeMutation,
  useValidateEmployeesMutation,
  useImportEmployeesMutation,
  useGetImportJobQuery,
  useLazyGetImportJobQuery,
  useGetQcParametersQuery,
  useCreateQcParameterMutation,
  useUpdateQcParameterMutation,
  useDeactivateQcParameterMutation,
  useActivateQcParameterMutation,
  useValidateQcParametersMutation,
  useImportQcParametersMutation,
  useGetMasterSummaryQuery,
  useGetVendorsQuery,
  useGetVendorLocationsQuery,
  useCreateVendorMutation,
  useUpdateVendorMutation,
  useDeactivateVendorMutation,
  useActivateVendorMutation,
  useValidateVendorsMutation,
  useImportVendorsMutation,
  useGetUserOnboardingsQuery,
  useGetUserOnboardingStatsQuery,
  useGetUserOnboardingQuery,
  useLazyGetUserOnboardingQuery,
  useGetOnboardingEmployeeOptionsQuery,
  useCreateUserOnboardingMutation,
  useUpdateUserOnboardingMutation,
  useDiscardUserOnboardingMutation,
  useOnboardingActionMutation,
  useGetErpUsersQuery,
  useSetErpUserActiveMutation,
  useChangeErpUserRoleMutation,
  useValidateActivationTokenMutation,
  useActivateAccountMutation,
} = baseApi;

export async function downloadNameMasterTemplate(
  resource:
    | NameMasterResource
    | "units"
    | "verticals"
    | "uoms"
    | "material-subcategories"
    | "stock-yards"
    | "material-groups"
    | "purchasing-groups"
    | "plants"
    | "material-types"
    | "materials"
    | "employees"
    | "qc-parameters"
    | "vendors",
  filename: string,
  accessToken: string | null,
) {
  const response = await fetch(`${env.apiBaseUrl}/api/v1/master/${resource}/template/`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!response.ok) {
    throw new Error("Unable to download template.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadImportJobErrors(jobId: number, accessToken: string | null) {
  const response = await fetch(`${env.apiBaseUrl}/api/v1/master/import-jobs/${jobId}/errors/`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!response.ok) {
    throw new Error("Unable to download error file.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `import_job_${jobId}_errors.xlsx`;
  anchor.click();
  URL.revokeObjectURL(url);
}
