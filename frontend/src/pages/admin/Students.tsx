import { useEffect, useState } from "react";
import { Users } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { listAllStudents, listTeachers, type AdminStudentRecord, type TeacherRecord } from "@/services/adminService";

/**
 * Platform-wide, read-only student oversight. Per spec, Admin is
 * lightweight and not a primary focus — editing student data remains
 * exclusively a teacher responsibility (see pages/teacher/Students.tsx).
 */
export function Students() {
  const [students, setStudents] = useState<AdminStudentRecord[] | null>(null);
  const [teachers, setTeachers] = useState<TeacherRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAllStudents()
      .then(setStudents)
      .catch(() => setError("Couldn't load students. Please try again."));
    listTeachers()
      .then(setTeachers)
      .catch(() => {
        /* Teacher names are a display enhancement only; a failure here
           just falls back to showing "Teacher #<id>" below. */
      });
  }, []);

  function teacherName(id: number): string {
    return teachers.find((t) => t.id === id)?.full_name ?? `Teacher #${id}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Students</h1>
        <p className="mt-1 text-muted-foreground">Platform-wide student oversight.</p>
      </div>

      {students === null && !error && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && <EmptyState icon={Users} title="Something went wrong" description={error} />}

      {students !== null && students.length === 0 && (
        <EmptyState
          icon={Users}
          title="No students listed yet"
          description="Students created by teachers will appear here."
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
                  <br />
                  Teacher: {teacherName(student.teacher_id)}
                </CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
