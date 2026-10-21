import { render, screen } from "@testing-library/react";
import DataDeletionPage from "@/app/data-deletion/page";

describe("DataDeletionPage", () => {
  it("explains the request → confirm → erase flow", () => {
    render(<DataDeletionPage />);

    expect(
      screen.getByRole("heading", { name: /delete your account/i, level: 1 })
    ).toBeInTheDocument();
    expect(screen.getByText(/1\. Request deletion/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Your gym confirms/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. FitNation erases your data/i)).toBeInTheDocument();
    expect(screen.getByText(/deletion is permanent/i)).toBeInTheDocument();
  });

  it("lists what is erased, what is retained, and links back to the policy", () => {
    render(<DataDeletionPage />);

    expect(screen.getByText(/progress photos/i)).toBeInTheDocument();
    expect(screen.getByText(/logged out on every device/i)).toBeInTheDocument();
    expect(screen.getByText(/statutory and financial reasons/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /privacy policy/i })
    ).toHaveAttribute("href", "/privacy");
    expect(screen.getByText("support@yougetfitwithus.com")).toBeInTheDocument();
  });
});