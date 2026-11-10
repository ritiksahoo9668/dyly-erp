export type AccessModuleKey = "DASHBOARD" | "PROCUREMENT" | "PRODUCTION" | "SALES" | "HR" | "MASTER";

export type AccessAction =
  | "VIEW"
  | "CREATE"
  | "EDIT"
  | "EXPORT"
  | "CANCEL"
  | "UPLOAD"
  | "ACTIVATE_DEACTIVATE";

/** Effective access of the signed-in user (from `/auth/me`). Superadmin is not enumerated. */
export type UserAccessPayload = {
  full_access: boolean;
  modules: Partial<
    Record<
      AccessModuleKey,
      {
        nav_id: string;
        submodules: Record<string, { nav_id: string; actions: AccessAction[] }>;
      }
    >
  >;
};

export type AccessRegistrySubmodule = {
  key: string;
  label: string;
  nav_id: string;
  actions: { key: AccessAction; label: string }[];
};

export type AccessRegistryModule = {
  key: AccessModuleKey;
  label: string;
  nav_id: string;
  submodules: AccessRegistrySubmodule[];
};

export type AccessRegistryResponse = {
  modules: AccessRegistryModule[];
};

/** Stored access of one user / draft (API input and output). Submodules list granted actions. */
export type AccessAssignment = Partial<
  Record<AccessModuleKey, { enabled: boolean; submodules: Record<string, AccessAction[]> }>
>;

export type UserAccessResponse = {
  user_id: number;
  role: string;
  full_access: boolean;
  access: AccessAssignment;
  editable: boolean;
};
