import { FormEvent, useEffect, useState } from "react";
import { Users } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Modal } from "@/components/ui/Modal";
import {
  createStudent,
  deactivateStudent,
  listStudents,
  resetStudentPin,
  updateStudent,
  type StudentRecord,
} from "@/services/studentService";

export function Students() {
  const [students, setStudents] = useState<StudentRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [studentCode, setStudentCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [pin, setPin] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // --- Edit Student modal state ---
  const [editStudent, setEditStudent] = useState<StudentRecord | null>(null);
  const [editFullName, setEditFullName] = useState("");
  const [editStudentCode, setEditStudentCode] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  // --- Reset PIN modal state ---
  const [resetPinStudent, setResetPinStudent] = useState<StudentRecord | null>(null);
  const [newPin, setNewPin] = useState("");
  const [resetPinError, setResetPinError] = useState<string | null>(null);
  const [resetPinSubmitting, setResetPinSubmitting] = useState(false);
  const [resetPinSuccess, setResetPinSuccess] = useState(false);

  function loadStudents() {
    listStudents()
      .then(setStudents)
      .catch(() => setError("Couldn't load students. Please try again."));
  }

  useEffect(loadStudents, []);

  function resetForm() {
    setStudentCode("");
    setFullName("");
    setPin("");
    setFormError(null);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createStudent({ student_code: studentCode, full_name: fullName, pin });
      setIsModalOpen(false);
      resetForm();
      loadStudents();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setFormError(
        status === 409
          ? "That Student ID is already in use. Choose a different one."
          : "Couldn't create this student. Please check the details and try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate(studentId: number) {
    try {
      await deactivateStudent(studentId);
      loadStudents();
    } catch {
      setError("Couldn't deactivate this student. Please try again.");
    }
  }

  function openEditModal(student: StudentRecord) {
    setEditStudent(student);
    setEditFullName(student.full_name);
    setEditStudentCode(student.student_code);
    setEditError(null);
  }

  async function handleEdit(event: FormEvent) {
    event.preventDefault();
    if (!editStudent) return;
    setEditError(null);
    setEditSubmitting(true);
    try {
      await updateStudent(editStudent.id, {
        full_name: editFullName,
        student_code: editStudentCode,
      });
      setEditStudent(null);
      loadStudents();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setEditError(
        status === 409
          ? "That Student ID is already in use. Choose a different one."
          : "Couldn't save these changes. Please try again."
      );
    } finally {
      setEditSubmitting(false);
    }
  }

  function openResetPinModal(student: StudentRecord) {
    setResetPinStudent(student);
    setNewPin("");
    setResetPinError(null);
    setResetPinSuccess(false);
  }

  async function handleResetPin(event: FormEvent) {
    event.preventDefault();
    if (!resetPinStudent) return;
    setResetPinError(null);
    setResetPinSubmitting(true);
    try {
      await resetStudentPin(resetPinStudent.id, newPin);
      setResetPinSuccess(true);
    } catch {
      setResetPinError("Couldn't reset this PIN. Please try again.");
    } finally {
      setResetPinSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Students</h1>
          <p className="mt-1 text-muted-foreground">Manage the students in your care.</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>Add Student</Button>
      </div>

      {students === null && !error && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <EmptyState icon={Users} title="Something went wrong" description={error} />
      )}

      {students !== null && students.length === 0 && (
        <EmptyState
          icon={Users}
          title="No students yet"
          description="Add your first student to get started."
        />
      )}

      {students !== null && students.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {students.map((student) => (
            <Card variant="glass" key={student.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{student.full_name}</CardTitle>
                  <Badge variant={student.is_active ? "success" : "neutral"}>
                    {student.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <CardDescription>
                  ID: {student.student_code} • Difficulty: {student.current_difficulty_level}
                </CardDescription>
              </CardHeader>
              {student.is_active && (
                <CardContent className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEditModal(student)}>
                    Edit
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openResetPinModal(student)}>
                    Reset PIN
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDeactivate(student.id)}
                  >
                    Deactivate
                  </Button>
                </CardContent>
              )}
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
        title="Add Student"
      >
        <form className="flex flex-col gap-4" onSubmit={handleCreate}>
          <Input
            label="Student ID"
            required
            value={studentCode}
            onChange={(e) => setStudentCode(e.target.value)}
          />
          <Input
            label="Full Name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <Input
            label="4-Digit PIN"
            inputMode="numeric"
            pattern="\d{4}"
            maxLength={4}
            required
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
          />
          {formError && (
            <p role="alert" className="text-sm text-error-600">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create Student"}
          </Button>
        </form>
      </Modal>

      <Modal
        isOpen={editStudent !== null}
        onClose={() => setEditStudent(null)}
        title={`Edit Student${editStudent ? ` — ${editStudent.full_name}` : ""}`}
      >
        <form className="flex flex-col gap-4" onSubmit={handleEdit}>
          <Input
            label="Student ID"
            required
            value={editStudentCode}
            onChange={(e) => setEditStudentCode(e.target.value)}
          />
          <Input
            label="Full Name"
            required
            value={editFullName}
            onChange={(e) => setEditFullName(e.target.value)}
          />
          {editError && (
            <p role="alert" className="text-sm text-error-600">
              {editError}
            </p>
          )}
          <Button type="submit" disabled={editSubmitting}>
            {editSubmitting ? "Saving..." : "Save Changes"}
          </Button>
        </form>
      </Modal>

      <Modal
        isOpen={resetPinStudent !== null}
        onClose={() => setResetPinStudent(null)}
        title={`Reset PIN${resetPinStudent ? ` — ${resetPinStudent.full_name}` : ""}`}
      >
        {resetPinSuccess ? (
          <div className="flex flex-col gap-4">
            <p className="text-foreground">
              PIN reset. Share the new PIN with the student so they can log in.
            </p>
            <Button onClick={() => setResetPinStudent(null)}>Done</Button>
          </div>
        ) : (
          <form className="flex flex-col gap-4" onSubmit={handleResetPin}>
            <Input
              label="New 4-Digit PIN"
              inputMode="numeric"
              pattern="\d{4}"
              maxLength={4}
              required
              value={newPin}
              onChange={(e) => setNewPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
            />
            {resetPinError && (
              <p role="alert" className="text-sm text-error-600">
                {resetPinError}
              </p>
            )}
            <Button type="submit" disabled={resetPinSubmitting || newPin.length !== 4}>
              {resetPinSubmitting ? "Resetting..." : "Reset PIN"}
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
