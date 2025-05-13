
export interface User {
  id: string;
  email: string;
  role: string;
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  token: string | null;
}
