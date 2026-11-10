import { baseApi } from "@/app/store/api";
import { authReducer } from "@/app/store/authSlice";

export const rootReducer = {
  auth: authReducer,
  [baseApi.reducerPath]: baseApi.reducer,
};
