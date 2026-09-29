import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "@/contexts/AuthContext";
import { MiraProvider } from "@/contexts/MiraContext";
import { RequireAuth } from "@/components/RequireAuth";

import { StudentLayout } from "@/layouts/StudentLayout";
import { TeacherLayout } from "@/layouts/TeacherLayout";
import { AdminLayout } from "@/layouts/AdminLayout";

import { RoleSelect } from "@/pages/auth/RoleSelect";
import { TeacherLogin } from "@/pages/auth/TeacherLogin";
import { StudentLogin } from "@/pages/auth/StudentLogin";
import { AdminLogin } from "@/pages/auth/AdminLogin";

import { StudentDashboard } from "@/pages/student/StudentDashboard";
import { Learning } from "@/pages/student/Learning";
import { Quiz } from "@/pages/student/Quiz";
import { Reflection } from "@/pages/student/Reflection";
import { Progress } from "@/pages/student/Progress";
import { Settings } from "@/pages/student/Settings";
import { Skills } from "@/pages/student/Skills";

import { TeacherDashboard } from "@/pages/teacher/TeacherDashboard";
import { Students as TeacherStudents } from "@/pages/teacher/Students";
import { LearningPlans } from "@/pages/teacher/LearningPlans";
import { Analytics } from "@/pages/teacher/Analytics";

import { AdminDashboard } from "@/pages/admin/AdminDashboard";
import { Teachers } from "@/pages/admin/Teachers";
import { Students as AdminStudents } from "@/pages/admin/Students";

/**
 * Route configuration for Memora.
 *
 * Each role's route tree is wrapped in RequireAuth, which redirects to
 * that role's login page if the visitor isn't authenticated as that
 * role. This is a UX guard only — the actual security boundary is
 * server-side (see app/api/deps.py), enforced independently by every
 * protected endpoint.
 */
function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/login/student" replace />} />
        <Route path="/role-select" element={<RoleSelect />} />

        <Route path="/login/teacher" element={<TeacherLogin />} />
        <Route path="/login/student" element={<StudentLogin />} />
        <Route path="/login/admin" element={<AdminLogin />} />

        <Route
          path="/student"
          element={
            <RequireAuth role="student">
              <MiraProvider>
                <StudentLayout />
              </MiraProvider>
            </RequireAuth>
          }
        >
          <Route index element={<StudentDashboard />} />
          <Route path="learning" element={<Learning />} />
          <Route path="quiz" element={<Quiz />} />
          <Route path="reflection" element={<Reflection />} />
          <Route path="progress" element={<Progress />} />
          <Route path="settings" element={<Settings />} />
          <Route path="skills" element={<Skills />} />
        </Route>

        <Route
          path="/teacher"
          element={
            <RequireAuth role="teacher">
              <TeacherLayout />
            </RequireAuth>
          }
        >
          <Route index element={<TeacherDashboard />} />
          <Route path="students" element={<TeacherStudents />} />
          <Route path="learning-plans" element={<LearningPlans />} />
          <Route path="analytics" element={<Analytics />} />
        </Route>

        <Route
          path="/admin"
          element={
            <RequireAuth role="admin">
              <AdminLayout />
            </RequireAuth>
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="teachers" element={<Teachers />} />
          <Route path="students" element={<AdminStudents />} />
        </Route>

        <Route path="*" element={<Navigate to="/student" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
