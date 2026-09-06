import axios from "axios";

export const api = axios.create({
  baseURL: "http://localhost:8003",
  timeout: 13000,
});

export function getHealth() {
  return api.get("/health");
}
