import { FormEvent, useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Modal } from "@/components/ui/Modal";
import {
  activateTeacher,
  createTeacher,
  deactivateTeacher,
  listTeachers,
  type TeacherRecord,
} from "@/services/adminService";

export function Teachers() {
  const [teachers, setTeachers] = useState<TeacherRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function loadTeachers() {
    listTeachers()
      .then(setTeachers)
      .catch(() => setError("Couldn't load teachers. Please try again."));
  }

  useEffect(loadTeachers, []);

  function resetForm() {
    setFullName("");
    setEmail("");
    setPassword("");
    setFormError(null);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createTeacher({ full_name: fullName, email, password });
      setIsModalOpen(false);
      resetForm();
      loadTeachers();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setFormError(
        status === 409
          ? "A teacher with that email already exists."
          : "Couldn't create this teacher. Please check the details and try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(teacher: TeacherRecord) {
    try {
      if (teacher.is_active) {
        await deactivateTeacher(teacher.id);
      } else {
        await activateTeacher(teacher.id);
      }
      loadTeachers();
    } catch {
      setError("Couldn't update this teacher. Please try again.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Teachers</h1>
          <p className="mt-1 text-muted-foreground">Manage teacher accounts.</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>Add Teacher</Button>
      </div>

      {teachers === null && !error && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <EmptyState icon={GraduationCap} title="Something went wrong" description={error} />
      )}

      {teachers !== null && teachers.length === 0 && (
        <EmptyState
          icon={GraduationCap}
          title="No teachers listed yet"
          description="Add your first teacher account to get started."
        />
      )}

      {teachers !== null && teachers.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teachers.map((teacher) => (
            <Card variant="glass" key={teacher.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{teacher.full_name}</CardTitle>
                  <Badge variant={teacher.is_active ? "success" : "neutral"}>
                    {teacher.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <CardDescription>
                  {teacher.email}
                  {teacher.organization_name ? ` • ${teacher.organization_name}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" size="sm" onClick={() => handleToggleActive(teacher)}>
                  {teacher.is_active ? "Deactivate" : "Activate"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          resetForm();
        }}
        title="Add Teacher"
      >
        <form className="flex flex-col gap-4" onSubmit={handleCreate}>
          <Input
            label="Full Name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <Input
            label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Initial Password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {formError && (
            <p role="alert" className="text-sm text-error-600">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create Teacher"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}
