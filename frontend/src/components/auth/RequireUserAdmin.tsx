import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useGetMeQuery } from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { LoadingState } from "@/components/feedback/LoadingState";
import { canManageUsers } from "@/config/navigation";

/** Keeps the User role out of user-administration pages; the API enforces the same rule. */
export function RequireUserAdmin({ children }: { children: ReactNode }) {
  const user = useAppSelector(selectAuthUser);
  const { isFetching } = useGetMeQuery();

  if (user?.can_manage_users === undefined && isFetching) {
    return <LoadingState label="Checking access…" />;
  }
  if (!canManageUsers(user)) {
    return <Navigate to="/master" replace />;
  }
  return <>{children}</>;
}
