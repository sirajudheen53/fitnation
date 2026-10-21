import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import AdminGymsPage from "@/app/admin/page";
import { ApiError } from "@/lib/api";
import {
  deleteAdminTenant,
  fetchAdminTenants,
  rotateAdminTenantCredentials,
  updateAdminTenant,
  updateAdminTenantStatus,
} from "@/lib/api";
import { ArchiveGymDialog } from "@/features/admin/components/ArchiveGymDialog";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { EditGymDialog } from "@/features/admin/components/EditGymDialog";
import { RotateCredentialsDialog } from "@/features/admin/components/RotateCredentialsDialog";
import type { AdminTenant } from "@/types/admin";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/admin",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "admin-token",
  getStoredUser: () => ({
    id: 1,
    email: "ops@fitnation.app",
    name: "Platform Admin",
    role: "platform_admin",
    tenant_id: null,
    tenant_name: null,
    is_owner: false,
  }),
  logout: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchAdminTenants: jest.fn(),
  onboardGym: jest.fn(),
  updateAdminTenant: jest.fn(),
  updateAdminTenantStatus: jest.fn(),
  rotateAdminTenantCredentials: jest.fn(),
  deleteAdminTenant: jest.fn(),
}));

const sampleTenant = (overrides: Partial<AdminTenant> = {}): AdminTenant => ({
  id: 1,
  name: "Iron Temple Fitness",
  subscription_plan: "starter",
  status: "active",
  contact_email: "owner@irontemple.com",
  contact_phone: "+91 98765 43210",
  member_count: 120,
  branch_count: 2,
  created_at: "2026-01-15T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
});

/** Develop's ConfirmDialog is a Card overlay without role="dialog" — scope to its Card. */
function confirmCard(message: RegExp): HTMLElement {
  const node = screen.getByText(message).closest("div.rounded-xl");
  if (!(node instanceof HTMLElement)) {
    throw new Error("ConfirmDialog card not found");
  }
  return node;
}

describe("EditGymDialog", () => {
  it("pre-fills the gym fields and saves via PATCH", async () => {
    const onSaved = jest.fn();
    const updated = sampleTenant({ name: "Iron Temple Fitness II" });
    (updateAdminTenant as jest.Mock).mockResolvedValue(updated);

    render(<EditGymDialog tenant={sampleTenant()} onClose={() => {}} onSaved={onSaved} />);

    expect(screen.getByLabelText("Gym name")).toHaveValue("Iron Temple Fitness");
    expect(screen.getByLabelText("Contact email")).toHaveValue("owner@irontemple.com");

    fireEvent.change(screen.getByLabelText("Gym name"), {
      target: { value: "Iron Temple Fitness II" },
    });
    fireEvent.change(screen.getByLabelText("Subscription plan"), {
      target: { value: "professional" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() =>
      expect(updateAdminTenant).toHaveBeenCalledWith(
        1,
        {
          name: "Iron Temple Fitness II",
          contact_email: "owner@irontemple.com",
          contact_phone: "+91 98765 43210",
          subscription_plan: "professional",
        },
        "admin-token",
      ),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
  });

  it("shows backend field errors next to the input", async () => {
    (updateAdminTenant as jest.Mock).mockRejectedValue(
      new ApiError(400, { contact_email: ["tenant with this contact email already exists."] }, "Bad Request"),
    );

    render(<EditGymDialog tenant={sampleTenant()} onClose={() => {}} onSaved={jest.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
  });
});

describe("RotateCredentialsDialog", () => {
  it("warns before rotating, then shows the one-time password", async () => {
    (rotateAdminTenantCredentials as jest.Mock).mockResolvedValue({
      owner_email: "owner@irontemple.com",
      owner_password: "one-time-pass-99",
    });

    render(<RotateCredentialsDialog tenant={sampleTenant()} onClose={() => {}} />);

    expect(screen.getByText(/stops working/)).toBeInTheDocument();
    expect(screen.getByText(/logged out/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Rotate Credentials" }));

    expect(await screen.findByText("one-time-pass-99")).toBeInTheDocument();
    expect(screen.getByText("owner@irontemple.com")).toBeInTheDocument();
    expect(screen.getByText(/shown only once/)).toBeInTheDocument();
    expect(rotateAdminTenantCredentials).toHaveBeenCalledWith(1, "admin-token");
  });

  it("copies the one-time password to the clipboard", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    (rotateAdminTenantCredentials as jest.Mock).mockResolvedValue({
      owner_email: "owner@irontemple.com",
      owner_password: "one-time-pass-99",
    });

    render(<RotateCredentialsDialog tenant={sampleTenant()} onClose={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Rotate Credentials" }));
    fireEvent.click(await screen.findByLabelText("Copy password"));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("one-time-pass-99"));
  });
});

describe("ArchiveGymDialog", () => {
  it("requires typing the gym name before calling DELETE", async () => {
    const onArchived = jest.fn();
    const archived = sampleTenant({ status: "archived" });
    (deleteAdminTenant as jest.Mock).mockResolvedValue(archived);

    render(
      <ArchiveGymDialog tenant={sampleTenant()} onClose={() => {}} onArchived={onArchived} />,
    );

    const archiveButton = screen.getByRole("button", { name: "Archive Gym" });
    expect(archiveButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Type the gym name to confirm"), {
      target: { value: "Wrong Name Gym" },
    });
    expect(archiveButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Type the gym name to confirm"), {
      target: { value: "Iron Temple Fitness" },
    });
    expect(archiveButton).toBeEnabled();

    fireEvent.click(archiveButton);

    await waitFor(() =>
      expect(deleteAdminTenant).toHaveBeenCalledWith(1, "admin-token"),
    );
    await waitFor(() => expect(onArchived).toHaveBeenCalledWith(archived));
  });
});

describe("ConfirmDialog", () => {
  it("renders the message and confirms", () => {
    const onConfirm = jest.fn();
    render(
      <ConfirmDialog
        title="Suspend Iron Temple Fitness?"
        confirmLabel="Suspend Gym"
        destructive
        onConfirm={onConfirm}
        onClose={() => {}}
      >
        <p>Owner login will be blocked.</p>
      </ConfirmDialog>,
    );

    expect(screen.getByText("Owner login will be blocked.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Suspend Gym" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("AdminGymsPage", () => {
  it("renders gyms and disables actions for archived ones", async () => {
    (fetchAdminTenants as jest.Mock).mockResolvedValue([
      sampleTenant(),
      sampleTenant({ id: 2, name: "Legacy Barbell", status: "archived" }),
    ]);

    render(<AdminGymsPage />);

    expect(await screen.findByText("Iron Temple Fitness")).toBeInTheDocument();
    expect(screen.getByText("Legacy Barbell")).toBeInTheDocument();

    expect(screen.getByLabelText("Edit Iron Temple Fitness")).toBeEnabled();
    expect(screen.getByLabelText("Edit Legacy Barbell")).toBeDisabled();
    expect(screen.getByLabelText("Rotate credentials for Legacy Barbell")).toBeDisabled();
    expect(screen.getByLabelText("Archive Legacy Barbell")).toBeDisabled();
    // Archived gyms keep the status toggle but read-only — PATCH can't un-archive.
    const legacyRow = screen.getByText("Legacy Barbell").closest("tr");
    expect(legacyRow).not.toBeNull();
    expect(
      within(legacyRow as HTMLElement).getByRole("button", { name: "Suspend" }),
    ).toBeDisabled();
  });

  it("opens the edit dialog pre-filled from the row action", async () => {
    (fetchAdminTenants as jest.Mock).mockResolvedValue([sampleTenant()]);
    render(<AdminGymsPage />);
    await screen.findByText("Iron Temple Fitness");

    fireEvent.click(screen.getByLabelText("Edit Iron Temple Fitness"));

    expect(await screen.findByText("Edit Gym")).toBeInTheDocument();
    expect(screen.getByLabelText("Gym name")).toHaveValue("Iron Temple Fitness");
  });

  it("suspends via the confirm dialog, PATCHing only the status", async () => {
    (fetchAdminTenants as jest.Mock).mockResolvedValue([sampleTenant()]);
    (updateAdminTenantStatus as jest.Mock).mockResolvedValue(
      sampleTenant({ status: "suspended" }),
    );

    render(<AdminGymsPage />);
    await screen.findByText("Iron Temple Fitness");

    fireEvent.click(screen.getByRole("button", { name: "Suspend" }));
    expect(await screen.findByText(/Members lose access/)).toBeInTheDocument();

    fireEvent.click(
      within(confirmCard(/Members lose access/)).getByRole("button", {
        name: "Suspend",
      }),
    );

    await waitFor(() =>
      expect(updateAdminTenantStatus).toHaveBeenCalledTimes(1),
    );
    expect(updateAdminTenantStatus).toHaveBeenCalledWith(
      1,
      "suspended",
      "admin-token",
    );
    expect(await screen.findByText("suspended")).toBeInTheDocument();
  });

  it("reactivates a suspended gym directly via PATCH", async () => {
    (fetchAdminTenants as jest.Mock).mockResolvedValue([
      sampleTenant({ status: "suspended" }),
    ]);
    (updateAdminTenantStatus as jest.Mock).mockResolvedValue(sampleTenant());

    render(<AdminGymsPage />);
    await screen.findByText("Iron Temple Fitness");

    fireEvent.click(screen.getByRole("button", { name: /activate/i }));

    await waitFor(() =>
      expect(updateAdminTenantStatus).toHaveBeenCalledWith(
        1,
        "active",
        "admin-token",
      ),
    );
  });
});
