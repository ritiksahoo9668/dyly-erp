import { useMemo } from "react";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { stageActions } from "@/config/access";

/**
 * Which Master actions to offer on a page (`stageId` is the Master stage id in `masterStages`).
 * Hiding buttons is a convenience only; the API rejects the same actions.
 */
export function useMasterPermissions(stageId: string) {
  const user = useAppSelector(selectAuthUser);
  return useMemo(() => {
    const actions = stageActions(user, "master", stageId);
    return {
      canCreate: actions.CREATE,
      canEdit: actions.EDIT,
      canExport: actions.EXPORT,
      canUpload: actions.UPLOAD,
      canToggleActive: actions.ACTIVATE_DEACTIVATE,
    };
  }, [user, stageId]);
}
