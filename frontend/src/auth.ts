import { createContext, useContext } from "react";

export const AuthContext = createContext<{
  email: string | null;
  setEmail: (email: string | null) => void;
}>({
  email: null,
  setEmail: () => {},
});

export const useAuth = () => useContext(AuthContext);
