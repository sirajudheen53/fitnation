import { render, screen } from "@testing-library/react";
import PrivacyPolicyPage from "@/app/privacy/page";

describe("PrivacyPolicyPage", () => {
  it("renders the policy with the sections Play review checks", () => {
    render(<PrivacyPolicyPage />);

    expect(
      screen.getByRole("heading", { name: /privacy policy/i, level: 1 })
    ).toBeInTheDocument();
    expect(screen.getByText(/what we collect/i)).toBeInTheDocument();
    expect(screen.getAllByText(/progress photos/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/body measurements/i)).toBeInTheDocument();
    expect(screen.getByText(/phone number/i)).toBeInTheDocument();
    expect(screen.getByText(/encrypted HTTPS/i)).toBeInTheDocument();
    expect(screen.getByText(/never sold and never shared with advertisers/i)).toBeInTheDocument();
    expect(screen.getAllByText(/attendance/i).length).toBeGreaterThan(0);
  });

  it("shows the support contact and links to the deletion page", () => {
    render(<PrivacyPolicyPage />);

    const contact = screen.getByText("support@yougetfitwithus.com");
    expect(contact).toHaveAttribute("href", "mailto:support@yougetfitwithus.com");
    expect(screen.getByRole("link", { name: /how to delete your account/i })).toHaveAttribute(
      "href",
      "/data-deletion"
    );
  });
});