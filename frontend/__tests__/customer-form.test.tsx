/**
 * Customer form (msg 2438): optional email/last-name with the email-or-phone
 * rule, address inputs, and admission-fee capture on the create flow.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CustomerForm } from "@/features/customers/components/CustomerForm";
import { buildCustomerBody } from "@/lib/api";
import type { Customer, CustomerFormData } from "@/types/customer";

const baseCustomer: Customer = {
  id: 1,
  email: "arjun@example.com",
  user: 11,
  name: "Arjun Kumar",
  branch: null,
  status: "active",
  notes: "",
  address_street: "12 MG Road",
  address_city: "Bengaluru",
  address_state: "Karnataka",
  address_postal_code: "560001",
  phone: "+91 98765 43210",
  gender: null,
  date_of_birth: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  is_active: true,
  profile_photo: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function submitForm(container: HTMLElement) {
  fireEvent.submit(container.querySelector("form")!);
}

describe("CustomerForm optional contact fields", () => {
  it("blocks submit and flags the email field when email and phone are both empty", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Arjun" } });
    submitForm(container);

    expect(await screen.findByText("Email or phone is required")).toBeInTheDocument();
    await waitFor(() => expect(onSubmit).not.toHaveBeenCalled());
  });

  it("accepts a phone-only customer without last name (synthetic identity flow)", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Arjun" } });
    // PhoneInput composes the E.164 value from the country code + digits (#88).
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+91 98765 43210" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const payload = onSubmit.mock.calls[0][0] as CustomerFormData;
    expect(payload.email).toBe("");
    expect(payload.last_name).toBe("");
    expect(payload.phone).toBe("+919876543210");
  });

  it("accepts an email-only customer without last name", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Priya" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "priya@example.com" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const payload = onSubmit.mock.calls[0][0] as CustomerFormData;
    expect(payload.email).toBe("priya@example.com");
    expect(payload.last_name).toBe("");
    expect(payload.phone).toBeUndefined();
  });

  it("still validates email format when one is entered", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Priya" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } });
    submitForm(container);

    expect(await screen.findByText("Please enter a valid email")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("prefills blanks (not undefined) for a customer with a NULL email on edit", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <CustomerForm customer={{ ...baseCustomer, email: null }} onSubmit={onSubmit} />,
    );

    expect(screen.getByLabelText("Email")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+91 90000 11111" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const payload = onSubmit.mock.calls[0][0] as CustomerFormData;
    expect(payload.email).toBe("");
  });
});

describe("CustomerForm address section", () => {
  it("submits the four address fields to the payload", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Arjun" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "arjun@example.com" } });
    fireEvent.change(screen.getByLabelText("Street"), { target: { value: "12 MG Road" } });
    fireEvent.change(screen.getByLabelText("City"), { target: { value: "Bengaluru" } });
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "Karnataka" } });
    fireEvent.change(screen.getByLabelText("Postal code"), { target: { value: "560001" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      address_street: "12 MG Road",
      address_city: "Bengaluru",
      address_state: "Karnataka",
      address_postal_code: "560001",
    });
  });

  it("prefills address fields from the customer on edit", () => {
    render(<CustomerForm customer={baseCustomer} onSubmit={jest.fn()} />);

    expect(screen.getByLabelText("Street")).toHaveValue("12 MG Road");
    expect(screen.getByLabelText("City")).toHaveValue("Bengaluru");
    expect(screen.getByLabelText("State")).toHaveValue("Karnataka");
    expect(screen.getByLabelText("Postal code")).toHaveValue("560001");
  });

  it("omits address from buildCustomerBody's contract siblings but keeps address fields on the wire", () => {
    const body = buildCustomerBody({
      email: "",
      first_name: "Arjun",
      is_active: true,
      address_street: "12 MG Road",
      address_city: "Bengaluru",
    }) as Record<string, unknown>;
    expect(body.address_street).toBe("12 MG Road");
    expect(body.address_city).toBe("Bengaluru");
  });
});

describe("CustomerForm admission fee capture", () => {
  async function fillBasics() {
    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Arjun" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "arjun@example.com" } });
  }

  it("does not include an admission fee when the section stays collapsed", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    await fillBasics();
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect((onSubmit.mock.calls[0][0] as CustomerFormData).admission_fee).toBeUndefined();
  });

  it("captures a paid-now fee with the chosen method", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    await fillBasics();
    fireEvent.click(screen.getByRole("button", { name: /Admission fee/i }));
    await userEvent.type(screen.getByLabelText("Amount (₹)"), "5000");
    fireEvent.change(screen.getByLabelText("Method"), { target: { value: "card" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      admission_fee: { amount: 5000, status: "completed", method: "card" },
    });
  });

  it("captures a pending fee", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    await fillBasics();
    fireEvent.click(screen.getByRole("button", { name: /Admission fee/i }));
    await userEvent.type(screen.getByLabelText("Amount (₹)"), "2500");
    fireEvent.change(screen.getByLabelText("Collection"), { target: { value: "pending" } });
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      admission_fee: { amount: 2500, status: "pending" },
    });
  });

  it("rejects a negative amount", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    await fillBasics();
    fireEvent.click(screen.getByRole("button", { name: /Admission fee/i }));
    await userEvent.type(screen.getByLabelText("Amount (₹)"), "-5");
    submitForm(container);

    expect(await screen.findByText("Enter a valid amount")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("withdraws the fee when the section is collapsed again", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    await fillBasics();
    fireEvent.click(screen.getByRole("button", { name: /Admission fee/i }));
    await userEvent.type(screen.getByLabelText("Amount (₹)"), "5000");
    // Collapse again — the entered amount must not leak into the payload.
    fireEvent.click(screen.getByRole("button", { name: /Admission fee/i }));
    submitForm(container);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect((onSubmit.mock.calls[0][0] as CustomerFormData).admission_fee).toBeUndefined();
  });

  it("never offers fee capture on the edit flow", () => {
    render(<CustomerForm customer={baseCustomer} onSubmit={jest.fn()} />);
    expect(screen.queryByText(/Admission fee/i)).not.toBeInTheDocument();
  });

  it("strips admission_fee from the customer request body", () => {
    const body = buildCustomerBody({
      email: "",
      first_name: "Arjun",
      is_active: true,
      admission_fee: { amount: 5000, status: "completed", method: "cash" },
    }) as Record<string, unknown>;
    expect("admission_fee" in body).toBe(false);
  });
});
