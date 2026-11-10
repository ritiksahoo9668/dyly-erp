import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useGetMeQuery } from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { LoadingState } from "@/components/feedback/LoadingState";
import { canOpen } from "@/config/access";
import { homePath, visibleMasterStages } from "@/config/navigation";
import { AccessDenied } from "./AccessDenied";

type RequireAccessProps = {
  /** Main navigation id, e.g. "procurement". */
  module: string;
  /** Stage id within the module, e.g. "rfq". Omit for the module landing page. */
  stage?: string;
  children: ReactNode;
};

/** Shows the 403 page when the route is outside the user's module access (the API enforces it). */
export function RequireAccess({ module, stage, children }: RequireAccessProps) {
  const user = useAppSelector(selectAuthUser);
  const { isFetching } = useGetMeQuery();

  if (user?.access === undefined) {
    return isFetching ? <LoadingState label="Checking access…" /> : <AccessDenied />;
  }
  const allowed =
    module === "master" && !stage
      ? visibleMasterStages(user).length > 0
      : canOpen(user, module, stage);
  return allowed ? <>{children}</> : <AccessDenied />;
}

/** Sends `/` and unknown URLs to the first page the user may open. */
export function HomeRedirect() {
  const user = useAppSelector(selectAuthUser);
  const { isFetching } = useGetMeQuery();

  if (user?.access === undefined && isFetching) {
    return <LoadingState label="Checking access…" />;
  }
  const home = homePath(user);
  return home ? <Navigate to={home} replace /> : <AccessDenied />;
}
