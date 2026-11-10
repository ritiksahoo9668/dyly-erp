import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useGetMeQuery } from "@/app/store/api";
import { logout, selectAuthUser, selectIsAuthenticated, setUser } from "@/app/store/authSlice";
import { useAppDispatch, useAppSelector } from "@/app/store/hooks";
import { LoadingState } from "@/components/feedback/LoadingState";
import { useEffect } from "react";

/** Module access can change while signed in; menus follow within this interval. */
const ACCESS_REFRESH_MS = 60_000;

export function ProtectedRoute() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const storedUser = useAppSelector(selectAuthUser);
  const { data, isLoading, isError, isSuccess } = useGetMeQuery(undefined, {
    skip: !isAuthenticated,
    pollingInterval: ACCESS_REFRESH_MS,
    refetchOnFocus: true,
  });

  useEffect(() => {
    if (isSuccess && data) {
      dispatch(setUser(data));
    }
  }, [data, dispatch, isSuccess]);

  useEffect(() => {
    if (isError) {
      dispatch(logout());
    }
  }, [dispatch, isError]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (isLoading && !storedUser) {
    return <LoadingState label="Checking session…" />;
  }

  return <Outlet />;
}
