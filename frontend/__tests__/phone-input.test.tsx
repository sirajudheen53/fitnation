/**
 * PhoneInput (issue #88): country-code selector + national number field that
 * emits the E.164 shape the backend stores.
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";

import { PhoneInput } from "@/components/ui/PhoneInput";

function Harness({ initialValue = "", onBlur }: { initialValue?: string; onBlur?: () => void }) {
  const [value, setValue] = useState(initialValue);
  return (
    <div>
      <p data-testid="emitted">{value || "(empty)"}</p>
      <PhoneInput label="Phone" value={value} onChange={setValue} onBlur={onBlur} />
    </div>
  );
}

const nationalInput = (label = "Phone") => screen.getByLabelText(label);

/** Value owned entirely by the parent (no echo) — models a form reset/prefill. */
function ExternalValueHarness({ value }: { value: string }) {
  return <PhoneInput label="Phone" value={value} onChange={jest.fn()} />;
}

describe("PhoneInput", () => {
  it("defaults to India (+91) and an empty national number", () => {
    render(<Harness />);
    expect(screen.getByLabelText("Phone country code")).toHaveValue("IN");
    expect(nationalInput()).toHaveValue("");
    expect(screen.getByTestId("emitted")).toHaveTextContent("(empty)");
  });

  it("emits +dial+digits as the user types", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "9876543210" } });
    expect(nationalInput()).toHaveValue("9876543210");
    expect(screen.getByTestId("emitted")).toHaveTextContent("+919876543210");
  });

  it("ignores non-digit characters typed into the national field", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "98765-abc43210" } });
    expect(nationalInput()).toHaveValue("9876543210");
    expect(screen.getByTestId("emitted")).toHaveTextContent("+919876543210");
  });

  it("emits empty when the national number is cleared", () => {
    render(<Harness initialValue="+919876543210" />);
    expect(nationalInput()).toHaveValue("9876543210");
    fireEvent.change(nationalInput(), { target: { value: "" } });
    expect(screen.getByTestId("emitted")).toHaveTextContent("(empty)");
  });

  it("splits a pasted full +91 number instead of truncating it", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "+91 98765 43210" } });
    expect(nationalInput()).toHaveValue("9876543210");
    expect(screen.getByTestId("emitted")).toHaveTextContent("+919876543210");
  });

  it("switches country when a pasted number carries another dial code", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "+971501234567" } });
    expect(screen.getByLabelText("Phone country code")).toHaveValue("AE");
    expect(nationalInput()).toHaveValue("501234567");
    expect(screen.getByTestId("emitted")).toHaveTextContent("+971501234567");
  });

  it("re-emits with the new dial code when the country changes", () => {
    render(<Harness initialValue="+919876543210" />);
    fireEvent.change(screen.getByLabelText("Phone country code"), {
      target: { value: "AE" },
    });
    expect(screen.getByTestId("emitted")).toHaveTextContent("+9719876543210");
  });

  it("re-syncs both halves when the value is reset externally (form prefill)", () => {
    const { rerender } = render(<ExternalValueHarness value="" />);
    rerender(<ExternalValueHarness value="+919876543210" />);
    expect(screen.getByLabelText("Phone country code")).toHaveValue("IN");
    expect(nationalInput()).toHaveValue("9876543210");
  });

  it("parses legacy bare rows onto the India default on prefill", () => {
    render(<Harness initialValue="8606806956" />);
    expect(screen.getByLabelText("Phone country code")).toHaveValue("IN");
    expect(nationalInput()).toHaveValue("8606806956");
  });

  it("shows the label, error, and hint like the shared Input", () => {
    render(
      <PhoneInput label="Emergency contact phone" value="" onChange={jest.fn()} error="Enter a valid phone number" />,
    );
    expect(screen.getByText("Emergency contact phone")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid phone number")).toBeInTheDocument();
    expect(nationalInput("Emergency contact phone")).toHaveAttribute("aria-invalid", "true");
  });

  it("fires onBlur on the national field (wizard phone lookup)", () => {
    const onBlur = jest.fn();
    render(<Harness onBlur={onBlur} />);
    fireEvent.blur(nationalInput());
    expect(onBlur).toHaveBeenCalledTimes(1);
  });

  it("disables both halves when disabled", () => {
    render(<PhoneInput label="Phone" value="+919876543210" onChange={jest.fn()} disabled />);
    expect(screen.getByLabelText("Phone country code")).toBeDisabled();
    expect(nationalInput()).toBeDisabled();
  });
});
