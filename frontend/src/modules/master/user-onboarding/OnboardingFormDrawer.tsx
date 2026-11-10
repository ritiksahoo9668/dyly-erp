import { type ReactNode, useMemo, useState } from "react";
import {
  useCreateUserOnboardingMutation,
  useGetOnboardingEmployeeOptionsQuery,
  useUpdateUserOnboardingMutation,
} from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { SearchableSelect } from "@/components/common/SearchableSelect";
import { CloseIcon } from "@/components/navigation/icons";
import employeeStyles from "@/modules/master/employee/EmployeePage.module.css";
import { parseEmployeeErrors } from "@/modules/master/employee/employeeErrors";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { AccessAssignment } from "@/types/access";
import type { OnboardingEmployee, UserOnboardingDetail, UserRole } from "@/types/userOnboarding";
import { AccessMatrix } from "./AccessMatrix";
import { roleLabel } from "./onboardingFormat";
import styles from "./UserOnboardingPage.module.css";

type EmailSource = "company" | "personal" | "other";
type FieldKey = "employee_id" | "login_email" | "role";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function defaultSource(employee: OnboardingEmployee | undefined): EmailSource {
  if (employee?.company_email) return "company";
  if (employee?.personal_email) return "personal";
  return "other";
}

function sourceFor(employee: OnboardingEmployee, email: string): EmailSource {
  if (employee.company_email && employee.company_email.toLowerCase() === email) return "company";
  if (employee.personal_email && employee.personal_email.toLowerCase() === email) return "personal";
  return "other";
}

type Props = {
  record: UserOnboardingDetail | null;
  onClose: () => void;
  onSaved: (record: UserOnboardingDetail, sent: boolean) => void;
};

export function OnboardingFormDrawer({ record, onClose, onSaved }: Props) {
  const isEdit = record !== null;
  const user = useAppSelector(selectAuthUser);
  const assignable = useMemo<UserRole[]>(() => {
    const roles = [...(user?.assignable_roles ?? [])];
    if (record && !roles.includes(record.role)) roles.push(record.role);
    return roles;
  }, [record, user?.assignable_roles]);

  const optionsQuery = useGetOnboardingEmployeeOptionsQuery(undefined, {
    refetchOnMountOrArgChange: true,
  });
  const employees = useMemo(() => {
    const list = optionsQuery.data ?? [];
    if (record && !list.some((item) => item.id === record.employee.id)) {
      return [record.employee, ...list];
    }
    return list;
  }, [optionsQuery.data, record]);

  const [employeeId, setEmployeeId] = useState<number | "">(record?.employee.id ?? "");
  const [emailSource, setEmailSource] = useState<EmailSource>(() =>
    record ? sourceFor(record.employee, record.login_email) : "company",
  );
  const [otherEmail, setOtherEmail] = useState(() =>
    record && sourceFor(record.employee, record.login_email) === "other" ? record.login_email : "",
  );
  const [role, setRole] = useState<UserRole | "">(
    record?.role ?? (assignable.length === 1 ? assignable[0] : ""),
  );
  const [access, setAccess] = useState<AccessAssignment>(record?.access ?? {});
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const [createOnboarding, createState] = useCreateUserOnboardingMutation();
  const [updateOnboarding, updateState] = useUpdateUserOnboardingMutation();
  const saving = createState.isLoading || updateState.isLoading;

  const employee = employees.find((item) => item.id === employeeId);
  const loginEmail = (
    emailSource === "company"
      ? (employee?.company_email ?? "")
      : emailSource === "personal"
        ? (employee?.personal_email ?? "")
        : otherEmail
  )
    .trim()
    .toLowerCase();

  function clearError(key: FieldKey) {
    setErrors((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function chooseEmployee(value: number | "") {
    setEmployeeId(value);
    clearError("employee_id");
    clearError("login_email");
    setEmailSource(defaultSource(employees.find((item) => item.id === value)));
  }

  function validate() {
    const next: Partial<Record<FieldKey, string>> = {};
    if (employeeId === "") next.employee_id = "Select an employee.";
    if (!loginEmail) next.login_email = "Login email is required.";
    else if (!EMAIL_PATTERN.test(loginEmail)) next.login_email = "Enter a valid email address.";
    if (!role) next.role = "Select a role.";
    return next;
  }

  async function save(sendInvite: boolean) {
    setFormError(null);
    const clientErrors = validate();
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length || employeeId === "" || !role) {
      setFormError("Please correct the highlighted fields.");
      return;
    }
    const body = {
      employee_id: employeeId,
      login_email: loginEmail,
      role,
      access: role === "SUPERADMIN" ? {} : access,
    };
    try {
      let saved: UserOnboardingDetail;
      if (record) {
        saved = await updateOnboarding({
          id: record.id,
          body: { ...body, send_invite: sendInvite },
        }).unwrap();
      } else {
        saved = await createOnboarding({ ...body, send_invite: sendInvite }).unwrap();
      }
      onSaved(saved, sendInvite);
    } catch (err) {
      const parsed = parseEmployeeErrors(err);
      setErrors({
        employee_id: parsed.fields.employee_id,
        login_email: parsed.fields.login_email,
        role: parsed.fields.role,
      });
      setFormError(
        parsed.fields.access || parsed.message || "Please correct the highlighted fields.",
      );
    }
  }

  function field(key: FieldKey | null, label: string, control: ReactNode, hint?: string) {
    const error = key ? errors[key] : undefined;
    return (
      <div
        className={`${employeeStyles.field} ${employeeStyles.fieldWide} ${
          error ? employeeStyles.fieldInvalid : ""
        }`}
      >
        <label htmlFor={key ? `onboarding-${key}` : undefined}>{label}</label>
        {control}
        {error ? <p className={employeeStyles.fieldError}>{error}</p> : null}
        {!error && hint ? <p className={employeeStyles.fieldHint}>{hint}</p> : null}
      </div>
    );
  }

  const emailChoices: { key: EmailSource; label: string; value: string }[] = [
    { key: "company", label: "Company Email", value: employee?.company_email ?? "" },
    { key: "personal", label: "Personal Email", value: employee?.personal_email ?? "" },
    { key: "other", label: "Other", value: "" },
  ];

  const employeePlaceholder = optionsQuery.isFetching
    ? "Loading employees…"
    : employees.length === 0
      ? "No employees available for onboarding"
      : "Search by name or employee code";

  return (
    <>
      <button
        type="button"
        className={employeeStyles.drawerBackdrop}
        aria-label="Close"
        onClick={() => !saving && onClose()}
      />
      <aside
        className={employeeStyles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-form-title"
      >
        <div className={employeeStyles.drawerHeader}>
          <div>
            <h2 id="onboarding-form-title">{isEdit ? "Edit Onboarding Draft" : "Onboard User"}</h2>
            <p>
              {isEdit
                ? `${record.onboarding_code} · ${record.employee.full_name}`
                : "Create ERP access for an existing employee. Fields marked * are required."}
            </p>
          </div>
          <button
            type="button"
            className={shared.closeBtn}
            aria-label="Close"
            disabled={saving}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>

        <form
          className={employeeStyles.drawerBody}
          id="onboarding-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void save(false);
          }}
        >
          {formError ? <p className={shared.formError}>{formError}</p> : null}

          <section className={employeeStyles.section}>
            <h3 className={employeeStyles.sectionTitle}>Employee</h3>
            <div className={employeeStyles.fieldGrid}>
              {field(
                "employee_id",
                "Employee *",
                <SearchableSelect
                  id="onboarding-employee_id"
                  value={employeeId}
                  options={employees.map((item) => ({
                    value: item.id,
                    label: `${item.full_name} (${item.employee_code})`,
                  }))}
                  placeholder={employeePlaceholder}
                  searchPlaceholder="Search employee…"
                  emptyText="No matching employee without ERP access."
                  invalid={Boolean(errors.employee_id)}
                  disabled={optionsQuery.isFetching && employees.length === 0}
                  onChange={chooseEmployee}
                />,
                "Only active employees without an existing ERP onboarding are listed.",
              )}
            </div>
            {employee ? (
              <div className={styles.readonlyGrid}>
                {[
                  ["Employee Code", employee.employee_code],
                  ["Department", employee.department?.name],
                  ["Designation", employee.designation?.name],
                  ["Company", employee.company?.name],
                  ["Unit", employee.unit?.name],
                ].map(([label, value]) => (
                  <div key={label} className={styles.readonlyItem}>
                    <span>{label}</span>
                    <strong>{value || "—"}</strong>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className={employeeStyles.section}>
            <h3 className={employeeStyles.sectionTitle}>ERP Access</h3>
            <div className={employeeStyles.fieldGrid}>
              {field(
                "login_email",
                "Login Email *",
                <>
                  <div className={styles.choiceRow} role="radiogroup" aria-label="Login email source">
                    {emailChoices.map((choice) => {
                      const unavailable = choice.key !== "other" && !choice.value;
                      return (
                        <label
                          key={choice.key}
                          className={`${styles.choice} ${
                            emailSource === choice.key ? styles.choiceActive : ""
                          }`}
                          aria-disabled={unavailable}
                          title={unavailable ? "Not recorded in Employee Master" : choice.value}
                        >
                          <input
                            type="radio"
                            name="login-email-source"
                            checked={emailSource === choice.key}
                            disabled={unavailable}
                            onChange={() => {
                              setEmailSource(choice.key);
                              clearError("login_email");
                            }}
                          />
                          {choice.label}
                        </label>
                      );
                    })}
                  </div>
                  {emailSource === "other" ? (
                    <input
                      id="onboarding-login_email"
                      type="email"
                      maxLength={254}
                      autoComplete="off"
                      placeholder="name@company.com"
                      value={otherEmail}
                      onChange={(event) => {
                        setOtherEmail(event.target.value);
                        clearError("login_email");
                      }}
                    />
                  ) : (
                    <input
                      id="onboarding-login_email"
                      type="email"
                      readOnly
                      value={loginEmail}
                      placeholder={employee ? "Not recorded" : "Select an employee first"}
                    />
                  )}
                </>,
                "The invitation is sent to this address and it becomes the login ID.",
              )}
              {field(
                "role",
                "Role *",
                <select
                  id="onboarding-role"
                  className={styles.selectField}
                  value={role}
                  onChange={(event) => {
                    setRole(event.target.value as UserRole | "");
                    clearError("role");
                  }}
                >
                  <option value="">Select role</option>
                  {assignable.map((item) => (
                    <option key={item} value={item}>
                      {roleLabel(item)}
                    </option>
                  ))}
                </select>,
              )}
            </div>
          </section>

          <section className={employeeStyles.section}>
            <h3 className={employeeStyles.sectionTitle}>Module Access</h3>
            {role === "" ? (
              <p className={employeeStyles.fieldHint}>Select a role to assign module access.</p>
            ) : (
              <>
                {role !== "SUPERADMIN" ? (
                  <p className={employeeStyles.fieldHint}>
                    Enable modules and tick the actions this user needs. Approvals still follow the
                    workflow assignment and financial authority.
                    {Object.values(access).some((entry) => entry?.enabled)
                      ? ""
                      : " No module is enabled yet, so the user will only be able to sign in."}
                  </p>
                ) : null}
                <AccessMatrix value={access} role={role} onChange={setAccess} />
              </>
            )}
          </section>

          <p className={styles.infoBox}>
            No password is created here. The employee receives a secure activation link and sets
            their own password. The link expires automatically and can be used only once.
          </p>
        </form>

        <div className={employeeStyles.drawerFooter}>
          <button type="button" className={shared.secondaryBtn} disabled={saving} onClick={onClose}>
            Cancel
          </button>
          <span className={employeeStyles.drawerFooterSpacer} />
          <button
            type="submit"
            form="onboarding-form"
            className={shared.secondaryBtn}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save Draft"}
          </button>
          <button
            type="button"
            className={shared.primaryBtn}
            disabled={saving}
            onClick={() => void save(true)}
          >
            {saving ? "Please wait…" : "Save & Send Invitation"}
          </button>
        </div>
      </aside>
    </>
  );
}
