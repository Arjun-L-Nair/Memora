import { apiClient } from "@/services/apiClient";
import { saveSession } from "@/services/authStorage";
import type { UserRole } from "@/types";

/**
 * authService.ts
 *
 * Thin wrappers around the three backend login endpoints
 * (app/api/v1/auth.py, app/api/v1/admin.py). Each function performs the
 * login request and, on success, persists the returned token pair via
 * authStorage. No token refresh logic here — that lives in
 * apiClient.ts's response interceptor.
 */

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function loginTeacher(email: string, password: string): Promise<void> {
  const { data } = await apiClient.post<TokenResponse>("/auth/teacher/login", {
    email,
    password,
  });
  persist(data, "teacher");
}

export async function loginStudent(studentCode: string, pin: string): Promise<void> {
  const { data } = await apiClient.post<TokenResponse>("/auth/student/login", {
    student_code: studentCode,
    pin,
  });
  persist(data, "student");
}

export async function loginAdmin(email: string, password: string): Promise<void> {
  const { data } = await apiClient.post<TokenResponse>("/admin/login", {
    email,
    password,
  });
  persist(data, "admin");
}

function persist(tokens: TokenResponse, role: UserRole): void {
  saveSession({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    role,
  });
}
