/**
 * FBOS-026 — Customer profile photo: picker, validation, FormData API path,
 * and avatar display with initials fallback.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  buildCustomerBody,
  createCustomer,
  updateCustomer,
  resolveMediaUrl,
} from "@/lib/api";
import {
  ProfilePhotoPicker,
  validateProfilePhoto,
  MAX_PHOTO_SIZE_BYTES,
} from "@/features/customers/components/ProfilePhotoPicker";
import {
  CustomerAvatar,
  getCustomerInitials,
} from "@/features/customers/components/CustomerAvatar";
import { CustomerForm } from "@/features/customers/components/CustomerForm";
import { CustomerTable } from "@/features/customers/components/CustomerTable";
import { OverviewTab } from "@/features/customers/components/OverviewTab";
import type { Customer, CustomerFormData } from "@/types/customer";

function makeFile(name = "photo.jpg", type = "image/jpeg", size = 1_000): File {
  return new File([new ArrayBuffer(size)], name, { type });
}

const baseCustomer: Customer = {
  id: 1,
  email: "arjun@example.com",
  user: 11,
  name: "Arjun Kumar",
  branch: null,
  status: "active",
  notes: "",
  address_street: "",
  address_city: "",
  address_state: "",
  address_postal_code: "",
  phone: null,
  gender: null,
  date_of_birth: null,
  branch_id: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  is_active: true,
  profile_photo: null,
  height_cm: null,
  weight_kg: null,
  bmi: null,
  fitness_goal: null,
  injuries: null,
  medical_info: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function mockFetchOnce(payload: unknown, status = 200) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

/* ── Validation ──────────────────────────────────────────────────────── */

describe("validateProfilePhoto", () => {
  it("accepts an allowed type within the size limit", () => {
    expect(validateProfilePhoto(makeFile("a.jpg", "image/jpeg"))).toBeNull();
    expect(validateProfilePhoto(makeFile("a.png", "image/png"))).toBeNull();
    expect(validateProfilePhoto(makeFile("a.webp", "image/webp"))).toBeNull();
  });

  it("rejects disallowed types", () => {
    expect(validateProfilePhoto(makeFile("a.pdf", "application/pdf"))).toMatch(
      /JPEG, PNG, or WebP/i,
    );
  });

  it("accepts a file at exactly the size limit", () => {
    expect(validateProfilePhoto(makeFile("a.jpg", "image/jpeg", MAX_PHOTO_SIZE_BYTES))).toBeNull();
  });

  it("rejects files over 5 MB", () => {
    expect(
      validateProfilePhoto(makeFile("a.jpg", "image/jpeg", MAX_PHOTO_SIZE_BYTES + 1)),
    ).toMatch(/5 MB or smaller/i);
  });
});

/* ── Media URL resolution ────────────────────────────────────────────── */

describe("resolveMediaUrl", () => {
  it("prefixes relative media paths with the API origin", () => {
    expect(resolveMediaUrl("/media/customer-photos/p.jpg")).toBe(
      "http://localhost:8000/media/customer-photos/p.jpg",
    );
  });

  it("passes absolute URLs through untouched", () => {
    expect(resolveMediaUrl("https://cdn.example.com/p.jpg")).toBe(
      "https://cdn.example.com/p.jpg",
    );
  });

  it("returns null for empty values", () => {
    expect(resolveMediaUrl(null)).toBeNull();
    expect(resolveMediaUrl("")).toBeNull();
    expect(resolveMediaUrl(undefined)).toBeNull();
  });
});

/* ── Initials fallback ───────────────────────────────────────────────── */

describe("getCustomerInitials", () => {
  it("joins the first two name initials", () => {
    expect(getCustomerInitials("Arjun Kumar")).toBe("AK");
  });

  it("uses a single initial for one-word names", () => {
    expect(getCustomerInitials("Priya")).toBe("P");
  });

  it("returns ? for blank names", () => {
    expect(getCustomerInitials("   ")).toBe("?");
  });
});

/* ── CustomerAvatar ──────────────────────────────────────────────────── */

describe("CustomerAvatar", () => {
  it("renders initials when the customer has no photo", () => {
    render(<CustomerAvatar customer={baseCustomer} />);
    expect(screen.getByText("AK")).toBeInTheDocument();
    expect(screen.queryByTestId("customer-avatar-photo")).not.toBeInTheDocument();
  });

  it("renders the photo when a profile_photo URL is present", () => {
    render(
      <CustomerAvatar
        customer={{ ...baseCustomer, profile_photo: "/media/customer-photos/p.jpg" }}
      />,
    );
    const img = screen.getByTestId("customer-avatar-photo");
    expect(img).toHaveAttribute("src", "http://localhost:8000/media/customer-photos/p.jpg");
    expect(screen.queryByText("AK")).not.toBeInTheDocument();
  });
});

/* ── Request body building ───────────────────────────────────────────── */

describe("buildCustomerBody", () => {
  const file = makeFile();

  it("builds multipart FormData when a photo File is present", () => {
    const body = buildCustomerBody({
      profile_photo: file,
      email: "a@b.com",
      first_name: "A",
      last_name: "K",
      is_active: true,
      branch_id: 3,
      phone: undefined,
    });
    expect(body instanceof FormData).toBe(true);
    const form = body as FormData;
    expect(form.get("profile_photo")).toBe(file);
    expect(form.get("email")).toBe("a@b.com");
    expect(form.get("is_active")).toBe("true");
    // Contract: the wire field is `branch` (no backend alias).
    expect(form.get("branch")).toBe("3");
    expect(form.has("branch_id")).toBe(false);
    expect(form.has("phone")).toBe(false);
  });

  it("stays JSON without the photo field when none is selected", () => {
    const body = buildCustomerBody({
      email: "a@b.com",
      first_name: "A",
      last_name: "K",
      is_active: true,
      branch_id: 3,
      profile_photo: undefined,
    }) as Record<string, unknown>;
    expect(body instanceof FormData).toBe(false);
    expect(body.email).toBe("a@b.com");
    expect(body.branch).toBe(3);
    expect("branch_id" in body).toBe(false);
    expect("profile_photo" in body).toBe(false);
  });

  it("keeps profile_photo: null in the JSON body for explicit removal", () => {
    const body = buildCustomerBody({
      email: "a@b.com",
      first_name: "A",
      last_name: "K",
      is_active: true,
      profile_photo: null,
    }) as Record<string, unknown>;
    expect(body.profile_photo).toBeNull();
  });
});

/* ── API layer: FormData path over the wire ──────────────────────────── */

describe("customer photo API calls", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("createCustomer sends multipart without a Content-Type header", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 9, ...baseCustomer }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await createCustomer(
      { email: "a@b.com", first_name: "A", last_name: "K", is_active: true, profile_photo: makeFile() },
      "tok",
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/customers/customers/");
    expect(init.body instanceof FormData).toBe(true);
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
    expect(headers.Authorization).toBe("Token tok");
  });

  it("createCustomer without a photo still sends JSON", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 9, ...baseCustomer }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await createCustomer(
      { email: "a@b.com", first_name: "A", last_name: "K", is_active: true },
      "tok",
    );

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(typeof init.body).toBe("string");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("updateCustomer sends profile_photo: null in JSON when the photo is removed", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ...baseCustomer }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await updateCustomer(
      7,
      { email: "a@b.com", first_name: "A", last_name: "K", is_active: true, profile_photo: null },
      "tok",
    );

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(init.body as string).profile_photo).toBeNull();
  });
});

/* ── ProfilePhotoPicker interactions ─────────────────────────────────── */

describe("ProfilePhotoPicker", () => {
  it("renders the upload affordance and accept list when empty", () => {
    render(<ProfilePhotoPicker file={null} onChange={jest.fn()} onRemove={jest.fn()} />);
    expect(screen.getByRole("button", { name: /upload profile photo/i })).toBeInTheDocument();
    expect(screen.getByText(/JPEG, PNG, or WebP - up to 5 MB/i)).toBeInTheDocument();
  });

  it("emits the selected file through onChange", () => {
    const onChange = jest.fn();
    render(<ProfilePhotoPicker file={null} onChange={onChange} onRemove={jest.fn()} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = makeFile();
    fireEvent.change(input, { target: { files: [file] } });
    expect(onChange).toHaveBeenCalledWith(file);
  });

  it("restricts the file input to allowed types", () => {
    render(<ProfilePhotoPicker file={null} onChange={jest.fn()} onRemove={jest.fn()} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.accept).toBe("image/jpeg,image/png,image/webp");
  });

  it("shows a remove button when a photo exists and calls onRemove", () => {
    const onRemove = jest.fn();
    render(
      <ProfilePhotoPicker
        file={null}
        existingPhotoUrl="http://localhost:8000/media/p.jpg"
        onChange={jest.fn()}
        onRemove={onRemove}
      />,
    );
    expect(screen.getByAltText(/profile photo preview/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /remove profile photo/i }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("renders an inline validation error via the error prop", () => {
    render(
      <ProfilePhotoPicker
        file={null}
        error="Photo must be 5 MB or smaller."
        onChange={jest.fn()}
        onRemove={jest.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/5 MB or smaller/i);
  });
});

/* ── CustomerForm integration ────────────────────────────────────────── */

describe("CustomerForm photo integration", () => {
  function fillRequiredFields() {
    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Arjun" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Kumar" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "arjun@example.com" } });
  }

  it("includes the selected file in the submitted payload", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fillRequiredFields();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = makeFile();
    fireEvent.change(input, { target: { files: [file] } });

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());

    const payload = onSubmit.mock.calls[0][0] as CustomerFormData;
    expect(payload.profile_photo).toBe(file);
  });

  it("blocks an invalid file with an inline error and submits without a photo", async () => {
    const onSubmit = jest.fn();
    const { container } = render(<CustomerForm onSubmit={onSubmit} />);

    fillRequiredFields();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.pdf", "application/pdf")] } });

    expect(await screen.findByRole("alert")).toHaveTextContent(/JPEG, PNG, or WebP/i);

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect((onSubmit.mock.calls[0][0] as CustomerFormData).profile_photo).toBeUndefined();
  });

  it("submits profile_photo: null after removing an existing photo on edit", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <CustomerForm
        customer={{ ...baseCustomer, profile_photo: "/media/customer-photos/p.jpg" }}
        onSubmit={onSubmit}
      />,
    );

    // Existing photo renders via the resolved URL.
    expect(screen.getByAltText(/profile photo preview/i)).toHaveAttribute(
      "src",
      "http://localhost:8000/media/customer-photos/p.jpg",
    );

    fireEvent.click(screen.getByRole("button", { name: /remove profile photo/i }));
    fillRequiredFields();
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect((onSubmit.mock.calls[0][0] as CustomerFormData).profile_photo).toBeNull();
  });

  it("clears stale picker state when a customer reloads", () => {
    const onSubmit = jest.fn();
    const { rerender } = render(<CustomerForm customer={baseCustomer} onSubmit={onSubmit} />);
    rerender(<CustomerForm customer={{ ...baseCustomer, id: 2 }} onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: /upload profile photo/i })).toBeInTheDocument();
  });
});

/* ── Table + Overview display ────────────────────────────────────────── */

describe("customer photo display", () => {
  it("CustomerTable shows initials fallback when there is no photo", () => {
    render(<CustomerTable customers={[baseCustomer]} />);
    expect(screen.getByText("AK")).toBeInTheDocument();
    expect(screen.queryByTestId("customer-avatar-photo")).not.toBeInTheDocument();
  });

  it("CustomerTable shows the photo when present", () => {
    render(
      <CustomerTable
        customers={[{ ...baseCustomer, profile_photo: "/media/customer-photos/p.jpg" }]}
      />,
    );
    expect(screen.getByTestId("customer-avatar-photo")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/customer-photos/p.jpg",
    );
  });

  it("OverviewTab shows the identity header with initials fallback", () => {
    render(<OverviewTab customer={baseCustomer} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("AK")).toBeInTheDocument();
  });

  it("OverviewTab shows the photo when present", () => {
    render(
      <OverviewTab customer={{ ...baseCustomer, profile_photo: "/media/customer-photos/p.jpg" }} />,
    );
    expect(screen.getByTestId("customer-avatar-photo")).toBeInTheDocument();
  });
});
