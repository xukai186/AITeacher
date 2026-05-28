import "@testing-library/jest-dom";
import { afterEach } from "vitest";
import { setToken } from "../src/api/client";

afterEach(() => {
  setToken(null);
});
