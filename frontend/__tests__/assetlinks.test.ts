/** @jest-environment node */
import { readFileSync } from "fs";
import { join } from "path";

// https://app.yougetfitwithus.com/.well-known/assetlinks.json must carry the
// fingerprint of whatever key actually signs the installed APK/AAB.
const UPLOAD_KEY_SHA256 =
  "E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72";

describe(".well-known/assetlinks.json", () => {
  const file = readFileSync(
    join(__dirname, "..", "public", ".well-known", "assetlinks.json"),
    "utf-8"
  );
  const statements = JSON.parse(file);

  it("parses as a single statement with the App Links relation", () => {
    expect(Array.isArray(statements)).toBe(true);
    expect(statements).toHaveLength(1);
    expect(statements[0].relation).toContain(
      "delegate_permission/common.handle_all_urls"
    );
    expect(statements[0].target.namespace).toBe("android_app");
  });

  it("targets the shipped applicationId (com.getfitwithus.app)", () => {
    expect(statements[0].target.package_name).toBe("com.getfitwithus.app");
  });

  it("carries the upload-key SHA-256 (dev/manual builds), uppercase colon format", () => {
    expect(statements[0].target.sha256_cert_fingerprints).toContain(
      UPLOAD_KEY_SHA256
    );
  });
});