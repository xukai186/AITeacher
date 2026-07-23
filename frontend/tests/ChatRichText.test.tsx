import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChatRichText from "../src/components/chat/ChatRichText";

describe("ChatRichText", () => {
  it("preserves newlines", () => {
    const { container } = render(<ChatRichText text={"第一行\n第二行"} />);
    expect(container.querySelectorAll("br").length).toBe(1);
    expect(screen.getByText("第一行", { exact: false })).toBeTruthy();
    expect(screen.getByText("第二行", { exact: false })).toBeTruthy();
  });

  it("renders bold markdown", () => {
    render(<ChatRichText text="这是 **重点** 内容" />);
    expect(screen.getByText("重点").tagName).toBe("STRONG");
  });

  it("renders list markers", () => {
    const { container } = render(<ChatRichText text={"- 第一点\n- 第二点"} />);
    expect(container.textContent).toContain("第一点");
    expect(container.textContent).toContain("•");
  });
});
