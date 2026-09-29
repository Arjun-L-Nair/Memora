// Shared foundational types for Memora.
// Business/domain types (Student, Teacher, LearningPlan, etc.) will be added
// in later tickets once backend contracts are implemented.

export type UserRole = "student" | "teacher" | "admin";

export interface NavItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
}
