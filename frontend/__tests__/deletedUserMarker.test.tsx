/**
 * Issue #81: deleted customers render as "Deleted user" everywhere.
 *
 * The backend scrubs the referenced customer's name to the marker and sends
 * an explicit `customer_is_deleted` / `person_is_deleted` flag; these tests
 * pin the frontend rendering — the label text plus the "Deleted" badge on
 * each surface that references a deleted member.
 */
import { AttendanceTable } from "@/features/attendance/components/AttendanceTable";
import { MembershipTable } from "@/features/memberships/components/MembershipTable";
import { NotificationLogsTable } from "@/features/notifications/components/NotificationLogsTable";
import { PaymentTable } from "@/features/payments/components/PaymentTable";
import { PendingPaymentTable } from "@/features/payments/components/PendingPaymentTable";
import { render, screen } from "@testing-library/react";
import type { AttendanceRecord } from "@/types/attendance";
import type { Membership } from "@/types/membership";
import type { NotificationLog } from "@/types/notification";
import type { Payment } from "@/types/payment";

function payment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: 1,
    customer_id: 11,
    customer_name: "Arjun Kumar",
    amount: "5000.00",
    method: "upi",
    status: "completed",
    kind: "membership",
    membership_id: null,
    invoice_id: null,
    notes: null,
    payment_date: "2026-10-20T00:00:00Z",
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
    ...overrides,
  };
}

function deletedPayment(): Payment {
  // The backend shape after the member was deleted: scrubbed name + flag.
  return payment({ customer_name: "Deleted user", customer_is_deleted: true });
}

function membership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 1,
    customer_id: 11,
    customer_name: "Arjun Kumar",
    plan_id: 3,
    plan_name: "Monthly Pro",
    start_date: "2026-10-01",
    end_date: "2026-10-31",
    status: "active",
    price: 5000,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

function attendanceRecord(overrides: Partial<AttendanceRecord> = {}): AttendanceRecord {
  return {
    id: 1,
    person_id: 11,
    person_name: "Arjun Kumar",
    person_type: "customer",
    branch_id: 2,
    branch_name: "Main Branch",
    check_in_time: "2026-10-20T06:30:00Z",
    check_out_time: "2026-10-20T07:45:00Z",
    status: "present",
    date: "2026-10-20",
    created_at: "2026-10-20T06:30:00Z",
    updated_at: "2026-10-20T07:45:00Z",
    ...overrides,
  };
}

function notificationLog(overrides: Partial<NotificationLog> = {}): NotificationLog {
  return {
    id: 1,
    customer: 11,
    customer_name: "Arjun Kumar",
    notification_type: "check_in",
    status: "sent",
    content: "See you at the gym!",
    wati_message_id: "wati-1",
    error_message: "",
    created_at: "2026-10-20T06:30:00Z",
    updated_at: "2026-10-20T06:30:00Z",
    ...overrides,
  };
}

describe("payment rows (issue #81)", () => {
  it("renders the payments list marker: 'Deleted user' + badge", () => {
    render(
      <PaymentTable
        payments={[deletedPayment()]}
        filters={{}}
        onFilterChange={jest.fn()}
      />,
    );
    expect(screen.getByText("Deleted user")).toBeInTheDocument();
    expect(screen.getByTitle("This member was deleted")).toHaveTextContent("Deleted");
  });

  it("does not badge a live member's payment row", () => {
    render(
      <PaymentTable payments={[payment()]} filters={{}} onFilterChange={jest.fn()} />,
    );
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.queryByTitle("This member was deleted")).not.toBeInTheDocument();
  });

  it("renders the pending-payments queue marker with the scrubbed phone", () => {
    render(
      <PendingPaymentTable
        payments={[deletedPayment({ status: "pending", customer_phone: "" })]}
        sendingPaymentId={null}
        onSend={jest.fn()}
      />,
    );
    expect(screen.getByText("Deleted user")).toBeInTheDocument();
    expect(screen.getByTitle("This member was deleted")).toBeInTheDocument();
  });
});

describe("membership rows (issue #81)", () => {
  it("badges a membership whose member was deleted", () => {
    render(
      <MembershipTable
        memberships={[membership({ customer_name: "Deleted user", customer_is_deleted: true })]}
      />,
    );
    expect(screen.getByText("Deleted user")).toBeInTheDocument();
    expect(screen.getByTitle("This member was deleted")).toBeInTheDocument();
  });

  it("leaves live memberships unbadged", () => {
    render(<MembershipTable memberships={[membership()]} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.queryByTitle("This member was deleted")).not.toBeInTheDocument();
  });
});

describe("attendance punches (issue #81)", () => {
  it("renders the person marker for a deleted member's punch", () => {
    render(
      <AttendanceTable
        records={[
          attendanceRecord({ person_name: "Deleted user", person_is_deleted: true }),
        ]}
      />,
    );
    expect(screen.getByText("Deleted user")).toBeInTheDocument();
    expect(screen.getByTitle("This member was deleted")).toBeInTheDocument();
  });

  it("leaves live punches unbadged", () => {
    render(<AttendanceTable records={[attendanceRecord()]} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.queryByTitle("This member was deleted")).not.toBeInTheDocument();
  });
});

describe("notification logs (issue #81)", () => {
  it("badges a log whose member was deleted", () => {
    render(
      <NotificationLogsTable
        logs={[notificationLog({ customer_name: "Deleted user", customer_is_deleted: true })]}
        onRowClick={jest.fn()}
      />,
    );
    expect(screen.getByText("Deleted user")).toBeInTheDocument();
    expect(screen.getByTitle("This member was deleted")).toBeInTheDocument();
  });
});
