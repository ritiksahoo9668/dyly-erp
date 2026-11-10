import { type FormEvent, useEffect, useState } from "react";
import { useCreateVendorMutation, useUpdateVendorMutation } from "@/app/store/api";
import { CloseIcon } from "@/components/navigation/icons";
import type { VendorRecord, VendorWritePayload } from "@/types/vendor";
import { extractApiError } from "@/utils/extractApiError";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import styles from "./VendorPage.module.css";

type FieldKey = keyof VendorWritePayload;
type FieldErrors = Partial<Record<FieldKey, string>>;

const FIELD_KEYS: FieldKey[] = [
  "sap_vendor_id",
  "vendor_name",
  "email",
  "contact_no",
  "gstin",
  "location",
];
const EMPTY_FORM: VendorWritePayload = {
  sap_vendor_id: "",
  vendor_name: "",
  email: "",
  contact_no: "",
  gstin: "",
  location: "",
};

function parseFormErrors(error: unknown): { fields: FieldErrors; message: string | null } {
  const detail = (error as { data?: { error?: { detail?: unknown } } } | null)?.data?.error?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const fields: FieldErrors = {};
    let message: string | null = null;
    for (const [key, value] of Object.entries(detail as Record<string, unknown>)) {
      const text = Array.isArray(value) ? String(value[0]) : String(value);
      if ((FIELD_KEYS as string[]).includes(key)) fields[key as FieldKey] = text;
      else message ??= text;
    }
    if (Object.keys(fields).length || message) return { fields, message };
  }
  return { fields: {}, message: extractApiError(error) };
}

type Props = {
  record: VendorRecord | null;
  locations: string[];
  onClose: () => void;
  onSaved: (record: VendorRecord) => void;
};

export function VendorFormModal({ record, locations, onClose, onSaved }: Props) {
  const [form, setForm] = useState<VendorWritePayload>(() =>
    record
      ? {
          sap_vendor_id: record.sap_vendor_id,
          vendor_name: record.vendor_name,
          email: record.email,
          contact_no: record.contact_no,
          gstin: record.gstin,
          location: record.location,
        }
      : EMPTY_FORM,
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [createVendor, createState] = useCreateVendorMutation();
  const [updateVendor, updateState] = useUpdateVendorMutation();
  const saving = createState.isLoading || updateState.isLoading;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  function setField(key: FieldKey, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const payload: VendorWritePayload = {
      sap_vendor_id: form.sap_vendor_id.trim(),
      vendor_name: form.vendor_name.trim(),
      email: form.email.trim().toLowerCase(),
      contact_no: form.contact_no.trim(),
      gstin: form.gstin.replace(/\s+/g, "").toUpperCase(),
      location: form.location.trim(),
    };
    if (!payload.vendor_name) {
      setFieldErrors({ vendor_name: "Vendor Name is required." });
      return;
    }
    if (payload.gstin && payload.gstin.length !== 15) {
      setFieldErrors({ gstin: "GSTIN must be 15 characters." });
      return;
    }
    setFieldErrors({});
    try {
      const saved = record
        ? await updateVendor({ id: record.id, body: payload }).unwrap()
        : await createVendor(payload).unwrap();
      onSaved(saved);
    } catch (err) {
      const parsed = parseFormErrors(err);
      setFieldErrors(parsed.fields);
      setFormError(parsed.message);
    }
  }

  function field(
    key: FieldKey,
    label: string,
    options: {
      placeholder?: string;
      maxLength?: number;
      hint?: string;
      type?: string;
      inputMode?: "text" | "email" | "tel";
      upper?: boolean;
      wide?: boolean;
      autoFocus?: boolean;
      list?: string;
    } = {},
  ) {
    const error = fieldErrors[key];
    return (
      <div className={`${styles.formField} ${options.wide ? styles.formFieldWide : ""}`}>
        <label htmlFor={`vendor-${key}`}>{label}</label>
        <input
          id={`vendor-${key}`}
          type={options.type ?? "text"}
          inputMode={options.inputMode}
          className={[error ? styles.inputInvalid : "", options.upper ? styles.upperInput : ""]
            .filter(Boolean)
            .join(" ")}
          value={form[key]}
          onChange={(event) =>
            setField(key, options.upper ? event.target.value.toUpperCase() : event.target.value)
          }
          placeholder={options.placeholder}
          maxLength={options.maxLength}
          aria-invalid={Boolean(error)}
          autoFocus={options.autoFocus}
          list={options.list}
          autoComplete="off"
        />
        {error ? (
          <p className={styles.fieldError}>{error}</p>
        ) : options.hint ? (
          <p className={styles.fieldHint}>{options.hint}</p>
        ) : null}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        className={shared.backdrop}
        aria-label="Close"
        onClick={() => !saving && onClose()}
      />
      <div
        className={`${shared.modal} ${styles.formModal}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vendor-form-title"
      >
        <div className={shared.modalHeader}>
          <div>
            <h2 id="vendor-form-title">{record ? "Edit Vendor" : "Add Vendor"}</h2>
            <p>
              {record
                ? `Update details for ${record.vendor_name}.`
                : "Fields marked * are required."}
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

        <form className={styles.formGrid} onSubmit={onSubmit} noValidate>
          {formError ? (
            <p className={`${shared.formError} ${styles.formFieldWide}`}>{formError}</p>
          ) : null}

          <div className={styles.formField}>
            <label htmlFor="vendor-erp-id">ERP Vendor ID</label>
            <input
              id="vendor-erp-id"
              className={styles.readOnlyInput}
              value={record ? record.erp_vendor_id : ""}
              placeholder="Generated on save"
              readOnly
              tabIndex={-1}
              aria-readonly="true"
            />
            <p className={styles.fieldHint}>System generated · cannot be edited</p>
          </div>
          {field("sap_vendor_id", "SAP Vendor ID", {
            placeholder: "e.g. 10013560",
            maxLength: 30,
            hint: "Optional · add when the SAP Vendor Code is created",
          })}
          {field("vendor_name", "Vendor Name *", {
            placeholder: "e.g. AB Drives & Automation Pvt Ltd",
            maxLength: 255,
            wide: true,
            autoFocus: true,
          })}
          {field("email", "Email ID", {
            type: "email",
            inputMode: "email",
            placeholder: "e.g. sales@vendor.com",
            maxLength: 254,
          })}
          {field("contact_no", "Contact No.", {
            type: "tel",
            inputMode: "tel",
            placeholder: "e.g. +91 99070 81109",
            maxLength: 20,
          })}
          {field("gstin", "GSTIN", {
            placeholder: "e.g. 22AAAAA0000A1ZC",
            maxLength: 15,
            upper: true,
            hint: "15 characters · saved in capitals",
          })}
          {field("location", "Location", {
            placeholder: "e.g. Raipur",
            maxLength: 150,
            list: "vendor-location-options",
          })}
          <datalist id="vendor-location-options">
            {locations.map((location) => (
              <option key={location} value={location} />
            ))}
          </datalist>

          <div className={`${shared.formActions} ${styles.formFieldWide}`}>
            <button
              type="button"
              className={shared.secondaryBtn}
              disabled={saving}
              onClick={onClose}
            >
              Cancel
            </button>
            <button type="submit" className={shared.primaryBtn} disabled={saving}>
              {saving ? "Saving…" : record ? "Save Changes" : "Add Vendor"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
