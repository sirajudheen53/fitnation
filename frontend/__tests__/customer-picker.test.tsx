import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CustomerPicker } from "@/features/payments/components/CustomerPicker";
import { searchCustomers } from "@/lib/api";
import type { Customer } from "@/types/customer";

// Only the network surface is mocked; helpers like errorMessage stay real.
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  searchCustomers: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedSearchCustomers = searchCustomers as jest.Mock;

const customer = (overrides: Partial<Customer> = {}): Customer => ({
  id: 5,
  email: null,
  user: 51,
  name: "Arjun Kumar",
  branch: null,
  status: "active",
  notes: "",
  address_street: "",
  address_city: "",
  address_state: "",
  address_postal_code: "",
  phone: "9876543210",
  gender: null,
  date_of_birth: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  is_active: true,
  profile_photo: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

/**
 * Stateful parent mirroring the real contract: `selected` reflects what the
 * parent stored, so clear/deselect paths (guarded on `selected`) actually run.
 */
function PickerHarness({
  debounceMs = 20,
  onSelect,
}: {
  debounceMs?: number;
  onSelect?: (customer: Customer | null) => void;
}) {
  const [selected, setSelected] = useState<Customer | null>(null);
  const handleSelect = (next: Customer | null) => {
    setSelected(next);
    onSelect?.(next);
  };
  return <CustomerPicker selected={selected} onSelect={handleSelect} debounceMs={debounceMs} />;
}

function setup(onSelect?: (customer: Customer | null) => void, debounceMs = 20) {
  const spy = onSelect ?? jest.fn();
  render(<PickerHarness debounceMs={debounceMs} onSelect={spy} />);
  return spy;
}

/** Type a query and wait for the debounced search to land and settle. */
async function search(query: string) {
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: query } });
  await waitFor(() => expect(mockedSearchCustomers).toHaveBeenCalled());
  await waitFor(() =>
    expect(screen.queryByTestId("customer-picker-loading")).not.toBeInTheDocument(),
  );
}

beforeEach(() => {
  mockedSearchCustomers.mockReset();
});

it("renders the search input with a placeholder", () => {
  setup();
  expect(screen.getByPlaceholderText("Search by name or phone")).toBeInTheDocument();
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("stays idle below the 2-character minimum and never calls the API", async () => {
  setup();
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "a" } });
  await waitFor(() =>
    expect(screen.queryByTestId("customer-picker-loading")).not.toBeInTheDocument(),
  );
  expect(mockedSearchCustomers).not.toHaveBeenCalled();
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("debounces typing into one request per settled query and lists matches", async () => {
  const onSelect = setup();
  mockedSearchCustomers.mockResolvedValue([
    customer(),
    customer({ id: 6, name: "Asha Nair", phone: "9123456780" }),
  ]);

  // Both keystrokes land inside the debounce window → a single "arjun" call.
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "a" } });
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "arjun" } });

  await screen.findByRole("option", { name: /Arjun Kumar/ });
  expect(mockedSearchCustomers).toHaveBeenCalledTimes(1);
  expect(mockedSearchCustomers).toHaveBeenCalledWith("test-token", "arjun");
  expect(screen.getByRole("option", { name: /Asha Nair/ })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("option", { name: /Arjun Kumar/ }));
  await waitFor(() => expect(onSelect).toHaveBeenCalledWith(customer()));
  // Picked: the input shows the name and the dropdown closes.
  expect(screen.getByLabelText("Customer")).toHaveValue("Arjun Kumar");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("shows an empty state when nothing matches", async () => {
  setup();
  mockedSearchCustomers.mockResolvedValue([]);
  await search("zzzz");
  expect(screen.getByTestId("customer-picker-empty")).toHaveTextContent(
    "No customers match “zzzz”.",
  );
});

it("shows an error state with a working retry", async () => {
  setup();
  mockedSearchCustomers.mockRejectedValueOnce(new Error("network down"));
  mockedSearchCustomers.mockResolvedValueOnce([customer()]);

  await search("arjun");
  expect(screen.getByText("Customer search failed.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
  await screen.findByRole("option", { name: /Arjun Kumar/ });
  expect(mockedSearchCustomers).toHaveBeenCalledTimes(2);
  expect(screen.queryByText("Customer search failed.")).not.toBeInTheDocument();
});

it("clears the selection and search state via the clear button", async () => {
  const onSelect = setup();
  mockedSearchCustomers.mockResolvedValue([customer()]);

  await search("arjun");
  fireEvent.click(screen.getByRole("option", { name: /Arjun Kumar/ }));
  await waitFor(() => expect(onSelect).toHaveBeenCalledWith(customer()));

  fireEvent.click(screen.getByRole("button", { name: "Clear customer" }));
  await waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(null));
  expect(screen.getByLabelText("Customer")).toHaveValue("");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("drops the picked customer when the text is edited again", async () => {
  const onSelect = setup();
  mockedSearchCustomers.mockResolvedValue([customer()]);

  await search("arjun");
  fireEvent.click(screen.getByRole("option", { name: /Arjun Kumar/ }));
  await waitFor(() => expect(onSelect).toHaveBeenCalledWith(customer()));

  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "arjun kumara" } });
  await waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(null));
  // The stale pick is dropped but a fresh (debounced) search starts.
  await waitFor(() =>
    expect(mockedSearchCustomers).toHaveBeenLastCalledWith("test-token", "arjun kumara"),
  );
});
