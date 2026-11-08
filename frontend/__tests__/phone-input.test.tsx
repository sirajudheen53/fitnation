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

/** Stateful harness passing a hint — the wizard's phone-field shape. */
function HintHarness() {
  const [value, setValue] = useState("");
  return <PhoneInput label="Phone" hint="The phone IS the login" value={value} onChange={setValue} />;
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

describe("PhoneInput resolved-value preview (#99)", () => {
  it("previews the E.164 value while typing", () => {
    render(<Harness />);
    expect(screen.queryByTestId("phone-preview")).not.toBeInTheDocument();
    fireEvent.change(nationalInput(), { target: { value: "9876" } });
    expect(screen.getByTestId("phone-preview")).toHaveTextContent("Will save as +919876");
    fireEvent.change(nationalInput(), { target: { value: "9876543210" } });
    expect(screen.getByTestId("phone-preview")).toHaveTextContent("Will save as +919876543210");
  });

  it("previews the new dial code when the country changes", () => {
    render(<Harness initialValue="+919876543210" />);
    fireEvent.change(screen.getByLabelText("Phone country code"), {
      target: { value: "AE" },
    });
    expect(screen.getByTestId("phone-preview")).toHaveTextContent("Will save as +9719876543210");
  });

  it("resolves untouched legacy prefills to what the backend will store", () => {
    render(<ExternalValueHarness value="8606806956" />);
    expect(screen.getByTestId("phone-preview")).toHaveTextContent("Will save as +918606806956");
  });

  it("keeps the hint alongside the preview and restores hint-only when cleared", () => {
    render(<HintHarness />);
    expect(screen.getByText("The phone IS the login")).toBeInTheDocument();
    expect(screen.queryByTestId("phone-preview")).not.toBeInTheDocument();
    fireEvent.change(nationalInput(), { target: { value: "9876543210" } });
    // The hint stays (it can carry live state, e.g. "Looking up…" in the
    // wizard) — the preview line is appended under it (#99).
    expect(screen.getByText("The phone IS the login")).toBeInTheDocument();
    expect(screen.getByTestId("phone-preview")).toBeInTheDocument();
    fireEvent.change(nationalInput(), { target: { value: "" } });
    expect(screen.getByText("The phone IS the login")).toBeInTheDocument();
    expect(screen.queryByTestId("phone-preview")).not.toBeInTheDocument();
  });
});

describe("PhoneInput normalization error state (#99)", () => {
  it("stays a neutral preview while an incomplete number is being typed", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "9876" } });
    expect(screen.queryByTestId("phone-normalize-error")).not.toBeInTheDocument();
    expect(nationalInput()).toHaveAttribute("aria-invalid", "false");
  });

  it("shows a clear error after blur when the value can't be normalized", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "9876" } });
    fireEvent.blur(nationalInput());
    expect(screen.getByTestId("phone-normalize-error")).toBeInTheDocument();
    expect(nationalInput()).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByTestId("phone-preview")).not.toBeInTheDocument();
  });

  it("clears the error state once the number becomes valid again", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "9876" } });
    fireEvent.blur(nationalInput());
    expect(screen.getByTestId("phone-normalize-error")).toBeInTheDocument();
    fireEvent.change(nationalInput(), { target: { value: "9876543210" } });
    expect(screen.queryByTestId("phone-normalize-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("phone-preview")).toBeInTheDocument();
  });

  it("does not fire for a valid number blurred after typing", () => {
    render(<Harness />);
    fireEvent.change(nationalInput(), { target: { value: "9876543210" } });
    fireEvent.blur(nationalInput());
    expect(screen.queryByTestId("phone-normalize-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("phone-preview")).toBeInTheDocument();
  });

  it("the form-supplied error wins — no duplicate normalize error", () => {
    render(
      <PhoneInput label="Phone" value="+91987" onChange={jest.fn()} error="Enter a valid phone number" />,
    );
    expect(screen.getByText("Enter a valid phone number")).toBeInTheDocument();
    expect(screen.queryByTestId("phone-normalize-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("phone-preview")).not.toBeInTheDocument();
  });
});
