import { type FormEvent, type ReactNode, useState } from "react";
import { useCreateEmployeeMutation, useUpdateEmployeeMutation } from "@/app/store/api";
import { SearchableSelect } from "@/components/common/SearchableSelect";
import { CloseIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import {
  EMPLOYEE_GENDERS,
  type EmployeeGender,
  type EmployeeRecord,
  type EmployeeWritePayload,
} from "@/types/employee";
import styles from "./EmployeePage.module.css";
import { parseEmployeeErrors } from "./employeeErrors";
import { toOptions, useDepartmentVerticals, useEmployeeMasters } from "./useEmployeeLookups";

type FormState = {
  full_name: string;
  gender: EmployeeGender | "";
  mobile_number: string;
  personal_email: string;
  date_of_joining: string;
  location: string;
  department_id: number | "";
  vertical_id: number | "";
  designation_id: number | "";
  company_id: number | "";
  division_id: number | "";
  facility_id: number | "";
  company_email: string;
};

type FieldKey = keyof FormState;

const EMPTY_FORM: FormState = {
  full_name: "",
  gender: "",
  mobile_number: "",
  personal_email: "",
  date_of_joining: "",
  location: "",
  department_id: "",
  vertical_id: "",
  designation_id: "",
  company_id: "",
  division_id: "",
  facility_id: "",
  company_email: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function toForm(record: EmployeeRecord): FormState {
  return {
    full_name: record.full_name,
    gender: record.gender,
    mobile_number: record.mobile_number,
    personal_email: record.personal_email,
    date_of_joining: record.date_of_joining,
    location: record.location,
    department_id: record.department.id,
    vertical_id: record.vertical?.id ?? "",
    designation_id: record.designation.id,
    company_id: record.company.id,
    division_id: record.division?.id ?? "",
    facility_id: record.facility?.id ?? "",
    company_email: record.company_email,
  };
}

function toPayload(form: FormState): EmployeeWritePayload {
  const id = (value: number | "") => (value === "" ? null : value);
  return {
    full_name: form.full_name.trim(),
    gender: form.gender,
    mobile_number: form.mobile_number.trim(),
    personal_email: form.personal_email.trim().toLowerCase(),
    date_of_joining: form.date_of_joining,
    location: form.location.trim(),
    department_id: id(form.department_id),
    vertical_id: id(form.vertical_id),
    designation_id: id(form.designation_id),
    company_id: id(form.company_id),
    division_id: id(form.division_id),
    facility_id: id(form.facility_id),
    company_email: form.company_email.trim().toLowerCase(),
  };
}

function validate(form: FormState): Partial<Record<FieldKey, string>> {
  const errors: Partial<Record<FieldKey, string>> = {};
  if (!form.full_name.trim()) errors.full_name = "Full Name is required.";
  if (!form.gender) errors.gender = "Gender is required.";
  const digits = form.mobile_number.replace(/[\s\-().]/g, "");
  if (!form.mobile_number.trim()) errors.mobile_number = "Mobile Number is required.";
  else if (!/^\+?\d{10,15}$/.test(digits.replace(/^00/, "+")))
    errors.mobile_number = "Enter 10 to 15 digits; a leading + country code is allowed.";
  if (form.personal_email.trim() && !EMAIL_PATTERN.test(form.personal_email.trim()))
    errors.personal_email = "Enter a valid email address.";
  if (!form.date_of_joining) errors.date_of_joining = "Date Of Joining is required.";
  if (!form.location.trim()) errors.location = "Location is required.";
  if (form.department_id === "") errors.department_id = "Department is required.";
  if (form.designation_id === "") errors.designation_id = "Designation is required.";
  if (form.company_id === "") errors.company_id = "Company is required.";
  if (form.company_email.trim() && !EMAIL_PATTERN.test(form.company_email.trim()))
    errors.company_email = "Enter a valid email address.";
  return errors;
}

type Props = {
  record: EmployeeRecord | null;
  onClose: () => void;
  onSaved: (record: EmployeeRecord) => void;
};

export function EmployeeFormDrawer({ record, onClose, onSaved }: Props) {
  const isEdit = record !== null;
  const [form, setForm] = useState<FormState>(() => (record ? toForm(record) : EMPTY_FORM));
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  const masters = useEmployeeMasters();
  const { verticals, isFetching: verticalsLoading } = useDepartmentVerticals(form.department_id);
  const [createEmployee, createState] = useCreateEmployeeMutation();
  const [updateEmployee, updateState] = useUpdateEmployeeMutation();
  const saving = createState.isLoading || updateState.isLoading;

  function patch(values: Partial<FormState>) {
    setForm((current) => ({ ...current, ...values }));
    setErrors((current) => {
      const next = { ...current };
      for (const key of Object.keys(values)) delete next[key];
      return next;
    });
    setDuplicateWarning(null);
  }

  async function save(confirmDuplicate: boolean) {
    setFormError(null);
    const body = {
      ...toPayload(form),
      ...(confirmDuplicate ? { confirm_possible_duplicate: true } : {}),
    };
    try {
      const saved = record
        ? await updateEmployee({ id: record.id, body }).unwrap()
        : await createEmployee(body).unwrap();
      onSaved(saved);
    } catch (err) {
      const parsed = parseEmployeeErrors(err);
      if (parsed.possibleDuplicate) {
        setDuplicateWarning(parsed.fields.personal_email ?? "Possible duplicate employee.");
        return;
      }
      setErrors(parsed.fields);
      setFormError(parsed.message || "Please correct the highlighted fields.");
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const clientErrors = validate(form);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) {
      setFormError("Please correct the highlighted fields.");
      return;
    }
    void save(false);
  }

  function field(
    key: FieldKey,
    label: string,
    control: ReactNode,
    opts: { wide?: boolean; hint?: string } = {},
  ) {
    const error = errors[key];
    return (
      <div
        className={`${styles.field} ${opts.wide ? styles.fieldWide : ""} ${
          error ? styles.fieldInvalid : ""
        }`}
      >
        <label htmlFor={`employee-${key}`}>{label}</label>
        {control}
        {error ? <p className={styles.fieldError}>{error}</p> : null}
        {!error && opts.hint ? <p className={styles.fieldHint}>{opts.hint}</p> : null}
      </div>
    );
  }

  function textInput(
    key: FieldKey,
    props: { type?: string; maxLength?: number; placeholder?: string } = {},
  ) {
    return (
      <input
        id={`employee-${key}`}
        type={props.type ?? "text"}
        value={form[key] as string}
        maxLength={props.maxLength}
        placeholder={props.placeholder}
        onChange={(event) => patch({ [key]: event.target.value } as Partial<FormState>)}
      />
    );
  }

  function masterSelect(
    key: FieldKey,
    options: ReturnType<typeof toOptions>,
    opts: {
      placeholder?: string;
      disabled?: boolean;
      clearable?: boolean;
      onChange?: (value: number | "") => void;
    } = {},
  ) {
    return (
      <SearchableSelect
        id={`employee-${key}`}
        value={form[key] as number | ""}
        options={options}
        placeholder={opts.placeholder ?? "Select"}
        disabled={opts.disabled}
        clearable={opts.clearable}
        invalid={Boolean(errors[key])}
        onChange={opts.onChange ?? ((value) => patch({ [key]: value } as Partial<FormState>))}
      />
    );
  }

  const verticalPlaceholder =
    form.department_id === ""
      ? "Select a Department first"
      : verticalsLoading
        ? "Loading verticals…"
        : verticals.length === 0
          ? "No verticals for this Department"
          : "Select";

  return (
    <>
      <button
        type="button"
        className={styles.drawerBackdrop}
        aria-label="Close"
        onClick={onClose}
      />
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby="employee-form-title"
      >
        <div className={styles.drawerHeader}>
          <div>
            <h2 id="employee-form-title">{isEdit ? "Edit Employee" : "Add Employee"}</h2>
            <p>
              {isEdit ? `Update details for ${record.full_name}.` : "Fields marked * are required."}
            </p>
          </div>
          <button type="button" className={shared.closeBtn} aria-label="Close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        <form className={styles.drawerBody} id="employee-form" onSubmit={onSubmit} noValidate>
          {formError ? <p className={shared.formError}>{formError}</p> : null}

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Personal Information</h3>
            <div className={styles.fieldGrid}>
              {field("full_name", "Full Name *", textInput("full_name", { maxLength: 150 }), {
                wide: true,
              })}
              {field(
                "gender",
                "Gender *",
                <select
                  id="employee-gender"
                  value={form.gender}
                  onChange={(event) => patch({ gender: event.target.value as EmployeeGender | "" })}
                >
                  <option value="">Select</option>
                  {EMPLOYEE_GENDERS.map((gender) => (
                    <option key={gender} value={gender}>
                      {gender}
                    </option>
                  ))}
                </select>,
              )}
              {field(
                "mobile_number",
                "Mobile Number *",
                textInput("mobile_number", {
                  type: "tel",
                  maxLength: 20,
                  placeholder: "+91 98765 43210",
                }),
                { hint: "Must be unique. Country code is kept." },
              )}
              {field(
                "personal_email",
                "Personal Email",
                textInput("personal_email", { type: "email", maxLength: 254 }),
              )}
              {field(
                "date_of_joining",
                "Date Of Joining *",
                textInput("date_of_joining", { type: "date" }),
              )}
              {field("location", "Location *", textInput("location", { maxLength: 150 }), {
                wide: true,
              })}
            </div>
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Employment</h3>
            <div className={styles.fieldGrid}>
              {field(
                "department_id",
                "Department *",
                masterSelect(
                  "department_id",
                  toOptions(masters.departments, { keep: form.department_id }),
                  {
                    onChange: (value) => patch({ department_id: value, vertical_id: "" }),
                  },
                ),
              )}
              {field(
                "vertical_id",
                "Vertical",
                masterSelect("vertical_id", toOptions(verticals, { keep: form.vertical_id }), {
                  placeholder: verticalPlaceholder,
                  disabled: form.department_id === "",
                  clearable: true,
                }),
              )}
              {field(
                "designation_id",
                "Designation *",
                masterSelect(
                  "designation_id",
                  toOptions(masters.designations, { keep: form.designation_id }),
                ),
              )}
            </div>
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Organization</h3>
            <div className={styles.fieldGrid}>
              {field(
                "company_id",
                "Company *",
                masterSelect("company_id", toOptions(masters.companies, { keep: form.company_id })),
              )}
              {field(
                "division_id",
                "Division",
                masterSelect(
                  "division_id",
                  toOptions(masters.divisions, { keep: form.division_id }),
                  {
                    clearable: true,
                  },
                ),
              )}
              {field(
                "facility_id",
                "Facility",
                masterSelect(
                  "facility_id",
                  toOptions(masters.facilities, { keep: form.facility_id }),
                  {
                    clearable: true,
                  },
                ),
              )}
            </div>
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Communication</h3>
            <div className={styles.fieldGrid}>
              {field(
                "company_email",
                "Company Email",
                textInput("company_email", { type: "email", maxLength: 254 }),
                {
                  wide: true,
                  hint: "Shared company mailboxes are allowed.",
                },
              )}
            </div>
          </section>

          {duplicateWarning ? (
            <div className={styles.warningBox} role="alert">
              <strong>Possible duplicate employee</strong>
              <span>{duplicateWarning}</span>
              <div className={styles.warningActions}>
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  onClick={() => setDuplicateWarning(null)}
                >
                  Review
                </button>
                <button
                  type="button"
                  className={shared.primaryBtn}
                  disabled={saving}
                  onClick={() => void save(true)}
                >
                  {saving ? "Saving…" : "Save anyway"}
                </button>
              </div>
            </div>
          ) : null}
        </form>

        <div className={styles.drawerFooter}>
          <button type="button" className={shared.secondaryBtn} onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            form="employee-form"
            className={shared.primaryBtn}
            disabled={saving || Boolean(duplicateWarning)}
          >
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Save Employee"}
          </button>
        </div>
      </aside>
    </>
  );
}
