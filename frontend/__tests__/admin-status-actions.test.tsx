import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { GymStatusAction } from "@/features/admin/components/GymStatusAction";
import type { AdminTenant } from "@/types/admin";

const activeTenant: AdminTenant = {
  id: 1,
  name: "Iron Temple",
  subscription_plan: "starter",
  status: "active",
  contact_email: "owner@irontemple.test",
  contact_phone: "+91 90000 00000",
  member_count: 42,
  branch_count: 2,
  created_at: "2026-08-01T00:00:00Z",
};

const suspendedTenant: AdminTenant = { ...activeTenant, status: "suspended" };

describe("GymStatusAction (issue #43)", () => {
  it("asks for confirmation before suspending an active gym", async () => {
    const onChangeStatus = jest.fn().mockResolvedValue(undefined);
    render(<GymStatusAction tenant={activeTenant} onChangeStatus={onChangeStatus} />);

    fireEvent.click(screen.getByRole("button", { name: /suspend/i }));
    expect(screen.getByText("Suspend this gym? Members lose access.")).toBeInTheDocument();
    expect(onChangeStatus).not.toHaveBeenCalled();

    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Suspend" }));
    await waitFor(() =>
      expect(onChangeStatus).toHaveBeenCalledWith(activeTenant, "suspended"),
    );
  });

  it("does not suspend when the confirmation is cancelled", () => {
    const onChangeStatus = jest.fn().mockResolvedValue(undefined);
    render(<GymStatusAction tenant={activeTenant} onChangeStatus={onChangeStatus} />);

    fireEvent.click(screen.getByRole("button", { name: /suspend/i }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onChangeStatus).not.toHaveBeenCalled();
    // Dialog is gone — a second click on Suspend re-opens it, not fires the API.
    expect(
      screen.queryByText("Suspend this gym? Members lose access."),
    ).not.toBeInTheDocument();
  });

  it("reactivates a suspended gym immediately without a dialog", async () => {
    const onChangeStatus = jest.fn().mockResolvedValue(undefined);
    render(
      <GymStatusAction tenant={suspendedTenant} onChangeStatus={onChangeStatus} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /activate/i }));
    await waitFor(() =>
      expect(onChangeStatus).toHaveBeenCalledWith(suspendedTenant, "active"),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("settles back to idle when the status change is rejected", async () => {
    const onChangeStatus = jest.fn().mockRejectedValue(new Error("boom"));
    render(<GymStatusAction tenant={activeTenant} onChangeStatus={onChangeStatus} />);

    fireEvent.click(screen.getByRole("button", { name: /suspend/i }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Suspend" }),
    );
    await waitFor(() => expect(onChangeStatus).toHaveBeenCalledTimes(1));

    // Loading settles and the dialog closes — the row action is usable again.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Suspend" })).toBeEnabled(),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
