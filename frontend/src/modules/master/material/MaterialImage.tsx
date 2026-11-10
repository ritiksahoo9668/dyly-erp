import { type DragEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  useRemoveMaterialImageMutation,
  useSetMaterialImageUrlMutation,
  useUploadMaterialImageMutation,
} from "@/app/store/api";
import { CloseIcon, MoreIcon } from "@/components/navigation/icons";
import styles from "@/modules/master/shared/NameMasterPage.module.css";
import imageStyles from "./MaterialImage.module.css";
import type { MaterialImageSource, MaterialRecord } from "@/types/material";
import { extractApiError } from "@/utils/extractApiError";

/** Client-side guard only; the server enforces the configured limit. */
export const MATERIAL_IMAGE_MAX_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
const ACCEPTED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ACCEPT_ATTR = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";
const URL_MAX_LENGTH = 500;
const BLOCKED_URL_SCHEME = /^\s*(javascript|data|vbscript|file|blob):/i;

export type MaterialImageTarget = {
  id: number;
  item_name: string;
  image_source: MaterialImageSource;
  display_image: string | null;
  item_image?: string;
};

type DialogMode = "choose" | "upload" | "url";

export function PackagePlaceholderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20.25 7.5l-8.25-4.5-8.25 4.5m16.5 0l-8.25 4.5m8.25-4.5v9l-8.25 4.5m0-9l-8.25-4.5m8.25 4.5v9m0 0l-8.25 4.5m8.25-4.5l8.25-4.5"
      />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0l-4 4m4-4l4 4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10 14a4 4 0 005.66 0l3-3a4 4 0 00-5.66-5.66l-1 1M14 10a4 4 0 00-5.66 0l-3 3a4 4 0 005.66 5.66l1-1"
      />
    </svg>
  );
}

function formatBytes(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function validateImageFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const hasAllowedExt = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!hasAllowedExt || (file.type && !ACCEPTED_MIME_TYPES.includes(file.type))) {
    return "Only JPG, JPEG, PNG or WebP images are allowed.";
  }
  if (file.size <= 0) return "The selected file is empty.";
  if (file.size > MATERIAL_IMAGE_MAX_BYTES) {
    return `Image must be ${formatBytes(MATERIAL_IMAGE_MAX_BYTES)} or smaller (selected ${formatBytes(file.size)}).`;
  }
  return null;
}

function validateImageUrl(raw: string): { url: string; error: string | null } {
  const trimmed = raw.trim();
  if (!trimmed) return { url: "", error: "Image URL is required." };
  if (BLOCKED_URL_SCHEME.test(trimmed)) {
    return { url: trimmed, error: "Only http:// or https:// image URLs are allowed." };
  }
  if (trimmed.length > URL_MAX_LENGTH) {
    return { url: trimmed, error: `Image URL must be ${URL_MAX_LENGTH} characters or fewer.` };
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return { url: trimmed, error: "Only http:// or https:// image URLs are allowed." };
    }
    if (!parsed.hostname.includes(".") && parsed.hostname !== "localhost") {
      return { url: trimmed, error: "Enter a valid http:// or https:// image URL." };
    }
  } catch {
    return { url: trimmed, error: "Enter a valid http:// or https:// image URL." };
  }
  return { url: trimmed, error: null };
}

/** Card image area: lazy thumbnail, clean placeholder, never a broken-image icon. */
export function MaterialCardMedia({
  src,
  alt,
  onAddImage,
}: {
  src: string | null | undefined;
  alt: string;
  onAddImage?: () => void;
}) {
  const url = (src ?? "").trim();
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const showImage = url !== "" && failedSrc !== url;

  if (showImage) {
    return (
      <img
        className={imageStyles.cardImage}
        src={url}
        alt={alt}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailedSrc(url)}
      />
    );
  }

  return (
    <div className={imageStyles.cardPlaceholder}>
      <PackagePlaceholderIcon />
      <span className={imageStyles.cardPlaceholderText}>No image</span>
      {onAddImage ? (
        <button
          type="button"
          className={imageStyles.cardAddImage}
          onClick={(event) => {
            event.stopPropagation();
            onAddImage();
          }}
          onKeyDown={(event) => event.stopPropagation()}
        >
          + Add Image
        </button>
      ) : null}
    </div>
  );
}

/** Upload / URL dialog. Image actions only touch the image reference of the Material. */
export function MaterialImageDialog({
  material,
  initialMode,
  initialUrl = "",
  onClose,
  onSaved,
}: {
  material: { id: number; item_name: string };
  initialMode: DialogMode;
  initialUrl?: string;
  onClose: () => void;
  onSaved: (record: MaterialRecord) => void;
}) {
  const [mode, setMode] = useState<DialogMode>(initialMode);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileReadable, setFileReadable] = useState(false);
  const [dragging, setDragging] = useState(false);

  const [urlInput, setUrlInput] = useState(initialUrl);
  const [urlPreview, setUrlPreview] = useState<string | null>(null);
  const [urlStatus, setUrlStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [urlError, setUrlError] = useState<string | null>(null);

  const [uploadImage, uploadState] = useUploadMaterialImageMutation();
  const [saveImageUrl, urlState] = useSetMaterialImageUrlMutation();
  const saving = uploadState.isLoading || urlState.isLoading;

  useEffect(() => {
    return () => {
      if (filePreview) URL.revokeObjectURL(filePreview);
    };
  }, [filePreview]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  function switchMode(next: DialogMode) {
    setSaveError(null);
    setMode(next);
  }

  function acceptFile(next: File | null) {
    setSaveError(null);
    setFileReadable(false);
    if (!next) return;
    const error = validateImageFile(next);
    if (error) {
      setFile(null);
      setFilePreview(null);
      setFileError(error);
      return;
    }
    setFileError(null);
    setFile(next);
    setFilePreview(URL.createObjectURL(next));
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    acceptFile(event.dataTransfer.files?.[0] ?? null);
  }

  function onPreviewUrl() {
    setSaveError(null);
    const { url, error } = validateImageUrl(urlInput);
    if (error) {
      setUrlError(error);
      setUrlPreview(null);
      setUrlStatus("idle");
      return;
    }
    setUrlError(null);
    setUrlInput(url);
    setUrlPreview(url);
    setUrlStatus("loading");
  }

  function onUrlInputChange(value: string) {
    setUrlInput(value);
    setUrlError(null);
    if (value.trim() !== urlPreview) {
      setUrlStatus("idle");
    }
  }

  async function onSave() {
    setSaveError(null);
    try {
      let record: MaterialRecord;
      if (mode === "upload") {
        if (!file || !fileReadable) return;
        record = await uploadImage({ id: material.id, file }).unwrap();
      } else if (mode === "url") {
        if (!urlPreview || urlStatus !== "ok") return;
        record = await saveImageUrl({ id: material.id, image_url: urlPreview }).unwrap();
      } else {
        return;
      }
      onSaved(record);
      onClose();
    } catch (err) {
      setSaveError(extractApiError(err));
    }
  }

  const canSave =
    !saving &&
    ((mode === "upload" && Boolean(file) && fileReadable && !fileError) ||
      (mode === "url" && urlStatus === "ok" && urlPreview === urlInput.trim()));

  const title =
    mode === "upload" ? "Upload Material Image" : mode === "url" ? "Add Image URL" : "Add Image";

  return createPortal(
    <>
      <button
        type="button"
        className={imageStyles.dialogOverlay}
        aria-label="Close"
        onClick={() => !saving && onClose()}
      />
      <div className={imageStyles.dialog} role="dialog" aria-modal="true" aria-label={title}>
        <div className={imageStyles.dialogHeader}>
          <div>
            <h2>{title}</h2>
            <p>{material.item_name}</p>
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            aria-label="Close"
            disabled={saving}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>

        <div className={imageStyles.dialogBody}>
          {mode === "choose" ? (
            <div className={imageStyles.chooseGrid}>
              <button
                type="button"
                className={imageStyles.chooseOption}
                onClick={() => switchMode("upload")}
              >
                <span className={imageStyles.chooseIcon}>
                  <UploadIcon />
                </span>
                <strong>Upload Image</strong>
                <span>JPG, JPEG, PNG or WebP up to {formatBytes(MATERIAL_IMAGE_MAX_BYTES)}</span>
              </button>
              <button
                type="button"
                className={imageStyles.chooseOption}
                onClick={() => switchMode("url")}
              >
                <span className={imageStyles.chooseIcon}>
                  <LinkIcon />
                </span>
                <strong>Add Image URL</strong>
                <span>Link to an external http:// or https:// image</span>
              </button>
            </div>
          ) : null}

          {mode === "upload" ? (
            <>
              <div
                className={`${imageStyles.dropzone} ${dragging ? imageStyles.dropzoneActive : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
              >
                <span className={imageStyles.dropzoneIcon}>
                  <UploadIcon />
                </span>
                <strong>Drag &amp; Drop</strong>
                <span className={imageStyles.dropzoneOr}>or</span>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={saving}
                >
                  Choose File
                </button>
                <span className={imageStyles.dropzoneHint}>
                  JPG / JPEG / PNG / WebP · Max {formatBytes(MATERIAL_IMAGE_MAX_BYTES)}
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT_ATTR}
                  className={imageStyles.hiddenInput}
                  onChange={(event) => {
                    acceptFile(event.target.files?.[0] ?? null);
                    event.target.value = "";
                  }}
                />
              </div>
              {fileError ? <p className={imageStyles.fieldError}>{fileError}</p> : null}

              <div className={imageStyles.previewBlock}>
                <span className={imageStyles.previewLabel}>Preview</span>
                <div className={imageStyles.previewFrame}>
                  {filePreview ? (
                    <img
                      src={filePreview}
                      alt="Selected material"
                      onLoad={() => setFileReadable(true)}
                      onError={() => {
                        setFileReadable(false);
                        setFileError("This file could not be read as an image.");
                      }}
                    />
                  ) : (
                    <div className={imageStyles.previewEmpty}>
                      <PackagePlaceholderIcon />
                      <span>No file selected</span>
                    </div>
                  )}
                </div>
                {file ? (
                  <span className={imageStyles.previewMeta}>
                    {file.name} · {formatBytes(file.size)}
                  </span>
                ) : null}
              </div>
            </>
          ) : null}

          {mode === "url" ? (
            <>
              <div className={styles.field}>
                <label htmlFor="material-image-url">Image URL *</label>
                <div className={imageStyles.urlRow}>
                  <input
                    id="material-image-url"
                    type="url"
                    inputMode="url"
                    placeholder="https://..."
                    value={urlInput}
                    maxLength={URL_MAX_LENGTH + 50}
                    onChange={(event) => onUrlInputChange(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        onPreviewUrl();
                      }
                    }}
                    disabled={saving}
                    autoFocus
                  />
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    onClick={onPreviewUrl}
                    disabled={saving || !urlInput.trim()}
                  >
                    Preview Image
                  </button>
                </div>
              </div>
              {urlError ? <p className={imageStyles.fieldError}>{urlError}</p> : null}

              <div className={imageStyles.previewBlock}>
                <span className={imageStyles.previewLabel}>Preview</span>
                <div className={imageStyles.previewFrame}>
                  {urlPreview && urlStatus !== "error" ? (
                    <img
                      key={urlPreview}
                      src={urlPreview}
                      alt="Image URL preview"
                      referrerPolicy="no-referrer"
                      className={urlStatus === "ok" ? "" : imageStyles.previewLoadingImg}
                      onLoad={() => setUrlStatus("ok")}
                      onError={() => setUrlStatus("error")}
                    />
                  ) : null}
                  {urlStatus === "loading" ? (
                    <div className={imageStyles.previewEmpty}>
                      <span>Loading preview…</span>
                    </div>
                  ) : null}
                  {urlStatus === "error" ? (
                    <div className={`${imageStyles.previewEmpty} ${imageStyles.previewWarning}`}>
                      <PackagePlaceholderIcon />
                      <span>This image could not be loaded from the URL.</span>
                    </div>
                  ) : null}
                  {!urlPreview ? (
                    <div className={imageStyles.previewEmpty}>
                      <PackagePlaceholderIcon />
                      <span>Enter a URL and click Preview Image</span>
                    </div>
                  ) : null}
                </div>
                {urlStatus === "idle" && urlPreview && urlPreview !== urlInput.trim() ? (
                  <span className={imageStyles.previewMeta}>
                    URL changed — preview again before saving.
                  </span>
                ) : null}
              </div>
            </>
          ) : null}

          {saveError ? <p className={styles.formError}>{saveError}</p> : null}
        </div>

        <div className={imageStyles.dialogFooter}>
          {mode !== "choose" && initialMode === "choose" ? (
            <button
              type="button"
              className={`${styles.ghostBtn} ${imageStyles.footerBack}`}
              onClick={() => switchMode("choose")}
              disabled={saving}
            >
              Back
            </button>
          ) : null}
          <button type="button" className={styles.secondaryBtn} onClick={onClose} disabled={saving}>
            Cancel
          </button>
          {mode !== "choose" ? (
            <button
              type="button"
              className={styles.primaryBtn}
              onClick={onSave}
              disabled={!canSave}
            >
              {saving ? "Saving…" : "Save Image"}
            </button>
          ) : null}
        </div>
      </div>
    </>,
    document.body,
  );
}

/** Larger image preview with Add / Change / Replace / Remove actions (View + Edit modals). */
export function MaterialImagePanel({
  material,
  onChanged,
  variant = "hero",
  readOnly = false,
}: {
  material: MaterialImageTarget;
  onChanged: (record: MaterialRecord) => void;
  variant?: "hero" | "form";
  readOnly?: boolean;
}) {
  const [dialog, setDialog] = useState<{ mode: DialogMode; initialUrl?: string } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [removeImage, removeState] = useRemoveMaterialImageMutation();

  const src = (material.display_image ?? "").trim();
  const hasImage = material.image_source !== "NONE" && src !== "";
  const broken = hasImage && failedSrc === src;

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (menuRef.current?.contains(event.target as Node)) return;
      setMenuOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  function openDialog(mode: DialogMode, initialUrl?: string) {
    setMenuOpen(false);
    setError(null);
    setDialog({ mode, initialUrl });
  }

  async function onConfirmRemove() {
    setError(null);
    try {
      const record = await removeImage(material.id).unwrap();
      setConfirmRemove(false);
      onChanged(record);
    } catch (err) {
      setConfirmRemove(false);
      setError(extractApiError(err));
    }
  }

  const panelClass =
    variant === "form" ? `${imageStyles.panel} ${imageStyles.panelForm}` : imageStyles.panel;

  return (
    <div className={panelClass}>
      <div className={imageStyles.panelFrame}>
        {hasImage && !broken ? (
          <img
            src={src}
            alt={material.item_name}
            decoding="async"
            referrerPolicy="no-referrer"
            onError={() => setFailedSrc(src)}
          />
        ) : null}
        {broken ? (
          <div className={`${imageStyles.panelEmpty} ${imageStyles.panelBroken}`}>
            <PackagePlaceholderIcon />
            <strong>Image unavailable</strong>
            <span>
              The saved {material.image_source === "URL" ? "image URL" : "file"} could not be
              loaded.
            </span>
          </div>
        ) : null}
        {!hasImage ? (
          <div className={imageStyles.panelEmpty}>
            <PackagePlaceholderIcon />
            <strong>No image available</strong>
          </div>
        ) : null}

        {hasImage ? (
          <>
            <span className={imageStyles.sourceBadge}>
              {material.image_source === "UPLOAD" ? "Uploaded" : "URL"}
            </span>
            {readOnly ? null : (
            <div ref={menuRef} className={imageStyles.panelMenuWrap}>
              <button
                type="button"
                className={imageStyles.panelMenuBtn}
                aria-label="Image actions"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
              >
                <MoreIcon size={16} />
              </button>
              {menuOpen ? (
                <div className={imageStyles.panelMenu} role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.menuItem}
                    onClick={() =>
                      material.image_source === "URL"
                        ? openDialog("url", material.item_image ?? material.display_image ?? "")
                        : openDialog("upload")
                    }
                  >
                    Change Image
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.menuItem}
                    onClick={() => openDialog("upload")}
                  >
                    Replace with Upload
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.menuItem}
                    onClick={() => openDialog("url")}
                  >
                    Replace with URL
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className={`${styles.menuItem} ${styles.menuItemDanger}`}
                    onClick={() => {
                      setMenuOpen(false);
                      setConfirmRemove(true);
                    }}
                  >
                    Remove Image
                  </button>
                </div>
              ) : null}
            </div>
            )}
          </>
        ) : null}
      </div>

      {!hasImage && !readOnly ? (
        <div className={imageStyles.panelActions}>
          <button type="button" className={styles.secondaryBtn} onClick={() => openDialog("upload")}>
            Upload Image
          </button>
          <button type="button" className={styles.secondaryBtn} onClick={() => openDialog("url")}>
            Add Image URL
          </button>
        </div>
      ) : null}

      {error ? <p className={imageStyles.fieldError}>{error}</p> : null}

      {dialog ? (
        <MaterialImageDialog
          material={material}
          initialMode={dialog.mode}
          initialUrl={dialog.initialUrl}
          onClose={() => setDialog(null)}
          onSaved={(record) => {
            setFailedSrc(null);
            onChanged(record);
          }}
        />
      ) : null}

      {confirmRemove
        ? createPortal(
            <>
              <button
                type="button"
                className={imageStyles.dialogOverlay}
                aria-label="Close"
                onClick={() => !removeState.isLoading && setConfirmRemove(false)}
              />
              <div
                className={`${imageStyles.dialog} ${imageStyles.dialogSmall}`}
                role="dialog"
                aria-modal="true"
              >
                <div className={imageStyles.dialogHeader}>
                  <div>
                    <h2>Remove Image</h2>
                    <p>{material.item_name}</p>
                  </div>
                </div>
                <div className={imageStyles.dialogBody}>
                  <p className={imageStyles.confirmText}>
                    Remove the image from this material? Only the image reference is cleared — the
                    Material record and all its other details stay unchanged.
                  </p>
                </div>
                <div className={imageStyles.dialogFooter}>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={removeState.isLoading}
                    onClick={() => setConfirmRemove(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={styles.dangerBtn}
                    disabled={removeState.isLoading}
                    onClick={onConfirmRemove}
                  >
                    {removeState.isLoading ? "Removing…" : "Remove Image"}
                  </button>
                </div>
              </div>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}
