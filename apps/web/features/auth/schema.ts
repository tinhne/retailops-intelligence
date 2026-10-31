import { z } from "zod";

// Mirrors `LoginRequest` in apps/api/app/domains/identity/schemas.py.
export const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address.")
    .max(254, "Email addresses are at most 254 characters.")
    .regex(/^[^@\s]+@[^@\s]+$/, "Enter an email address like name@company.com"),
  password: z
    .string()
    .min(1, "Enter your password.")
    .max(256, "Passwords are at most 256 characters."),
});

export type LoginValues = z.infer<typeof loginSchema>;
