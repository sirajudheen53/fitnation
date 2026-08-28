"use client";

import { Card, CardHeader, CardBody } from "@/components/ui";
import type { AttendanceHeatmap } from "@/types/analytics";

interface AttendanceHeatmapProps {
  data: AttendanceHeatmap[];
}

/** Simple heat‑map rendered as a grid of squares; colour intensity reflects count. */
export function AttendanceHeatmapChart({ data }: AttendanceHeatmapProps) {
  // Determine date range
  const dates = data.map(d => new Date(d.date));
  if (dates.length === 0) {
    return (
      <Card>
        <CardBody><p className="text-sm text-gray-500">No attendance data.</p></CardBody>
      </Card>
    );
  }
  const min = new Date(Math.min(...dates.map(d => d.getTime())));
  const max = new Date(Math.max(...dates.map(d => d.getTime())));

  // Build map for quick lookup
  const lookup = new Map(data.map(d => [d.date, d.count]));

  // Generate array of each day between min and max
  const dayMs = 24 * 60 * 60 * 1000;
  const days: string[] = [];
  for (let ts = min.getTime(); ts <= max.getTime(); ts += dayMs) {
    days.push(new Date(ts).toISOString().split('T')[0]);
  }

  const maxCount = Math.max(1, ...data.map(d => d.count));

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Attendance Heatmap</h2>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-7 gap-1">
          {days.map(date => {
            const count = lookup.get(date) ?? 0;
            const intensity = Math.round((count / maxCount) * 255);
            const bg = `rgb(${255 - intensity}, ${255 - intensity}, 255)`; // lighter for low count
            return (
              <div
                key={date}
                title={`${date}: ${count}`}
                className="h-6 w-6 rounded"
                style={{ backgroundColor: bg }}
              />
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}
