import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { HomeRedirect, RequireAccess } from "@/components/auth/RequireAccess";
import { RequireUserAdmin } from "@/components/auth/RequireUserAdmin";
import { ERPLayout } from "@/layouts/ERPLayout/ERPLayout";
import {
  ActivateAccountPage,
  AuthShell,
  ForgotPasswordPage,
  LoginPage,
  ResetPasswordPage,
} from "@/modules/auth";
import { DashboardPage } from "@/modules/dashboard";
import { HrPage } from "@/modules/hr";
import { MasterPage } from "@/modules/master";
import { DepartmentPage } from "@/modules/master/department";
import { DesignationPage } from "@/modules/master/designation";
import { DivisionPage } from "@/modules/master/division";
import { FacilityPage } from "@/modules/master/facility";
import { MaterialCategoryPage } from "@/modules/master/material-category";
import { MaterialGroupPage } from "@/modules/master/material-group";
import { MaterialSubcategoryPage } from "@/modules/master/material-subcategory";
import { MaterialTypePage } from "@/modules/master/material-type";
import { MaterialPage } from "@/modules/master/material";
import { PlantPage } from "@/modules/master/plant";
import { PurchasingGroupPage } from "@/modules/master/purchasing-group";
import { QcParameterPage } from "@/modules/master/qc-parameter";
import { StockYardPage } from "@/modules/master/stock-yard";
import { CompanyPage } from "@/modules/master/company";
import { EmployeePage } from "@/modules/master/employee";
import { UnitPage } from "@/modules/master/unit";
import { UomPage } from "@/modules/master/uom";
import { UserOnboardingPage } from "@/modules/master/user-onboarding";
import { VendorPage } from "@/modules/master/vendor";
import { VerticalPage } from "@/modules/master/vertical";
import { WeighBridgePage } from "@/modules/master/weighbridge";
import { ProcurementPage } from "@/modules/procurement";
import { ProductionPage } from "@/modules/production";
import { FeedConsumptionPage } from "@/modules/production/feed-consumption";
import { ProductionPlanningPage } from "@/modules/production/planning";
import { ProductionEntryPage } from "@/modules/production/production-entry";
import { SalesPage } from "@/modules/sales";
import { ModulePlaceholder } from "@/modules/shared/ModulePlaceholder";
import { salesStages } from "@/config/navigation";

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AuthShell />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/activate-account/:token" element={<ActivateAccountPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<ERPLayout />}>
          <Route index element={<HomeRedirect />} />
          <Route path="dashboard" element={guard("dashboard", undefined, <DashboardPage />)} />
          <Route path="procurement" element={guard("procurement", undefined, <ProcurementPage />)} />
          <Route path="production" element={guard("production", undefined, <ProductionPage />)} />
          <Route
            path="production/planning"
            element={guard("production", "planning", <ProductionPlanningPage />)}
          />
          <Route
            path="production/feed-consumption"
            element={guard("production", "feed-consumption", <FeedConsumptionPage />)}
          />
          <Route
            path="production/production-entry"
            element={guard("production", "production-entry", <ProductionEntryPage />)}
          />
          <Route path="sales" element={guard("sales", undefined, <SalesPage />)} />
          {salesStages.map((stage) =>
            stage.to ? (
              <Route
                key={stage.id}
                path={stage.to.slice(1)}
                element={guard(
                  "sales",
                  stage.id,
                  <ModulePlaceholder title={`Sales · ${stage.label}`} />,
                )}
              />
            ) : null,
          )}
          <Route path="hr" element={guard("hr", undefined, <HrPage />)} />
          <Route path="master" element={guard("master", undefined, <MasterPage />)} />
          {MASTER_ROUTES.map(([path, stage, page]) => (
            <Route key={path} path={`master/${path}`} element={guard("master", stage, page)} />
          ))}
          <Route
            path="master/user-onboarding"
            element={
              <RequireUserAdmin>
                <UserOnboardingPage />
              </RequireUserAdmin>
            }
          />
          <Route path="*" element={<HomeRedirect />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function guard(module: string, stage: string | undefined, page: ReactNode) {
  return (
    <RequireAccess module={module} stage={stage}>
      {page}
    </RequireAccess>
  );
}

/** Master pages: route path, Master stage id (see `masterStages`), page. */
const MASTER_ROUTES: [string, string, ReactNode][] = [
  ["division", "division", <DivisionPage />],
  ["department", "department", <DepartmentPage />],
  ["designation", "designation", <DesignationPage />],
  ["facility", "facility", <FacilityPage />],
  ["employee", "employee", <EmployeePage />],
  ["company", "company", <CompanyPage />],
  ["unit", "unit", <UnitPage />],
  ["vertical", "vertical", <VerticalPage />],
  ["uom", "uom", <UomPage />],
  ["qc-parameter", "qc-parameter", <QcParameterPage />],
  ["vendor", "vendor", <VendorPage />],
  ["material-category", "material-category", <MaterialCategoryPage />],
  ["material-sub-category", "material-sub-category", <MaterialSubcategoryPage />],
  ["material-group", "material-group", <MaterialGroupPage />],
  ["purchasing-group", "purchasing-group", <PurchasingGroupPage />],
  ["plant", "plant", <PlantPage />],
  ["material-type", "material-type", <MaterialTypePage />],
  ["material", "material-item", <MaterialPage />],
  ["stock-yard", "stock-yard", <StockYardPage />],
  ["weighbridge", "weighbridge", <WeighBridgePage />],
];
