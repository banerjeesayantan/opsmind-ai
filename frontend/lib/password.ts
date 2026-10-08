/**
 * Mirrors the password rules enforced by the backend's UserCreate.validate_password
 * (app/schemas/auth.py). The backend remains the source of truth - this only lets the register
 * form tell users the rules up front instead of failing after submit. If the backend rules change,
 * update this list to match.
 */
export const PASSWORD_RULES: { id: string; label: string; test: (password: string) => boolean }[] = [
  { id: "length", label: "At least 8 characters", test: (p) => p.length >= 8 },
  { id: "upper", label: "One uppercase letter", test: (p) => /[A-Z]/.test(p) },
  { id: "lower", label: "One lowercase letter", test: (p) => /[a-z]/.test(p) },
  { id: "number", label: "One number", test: (p) => /[0-9]/.test(p) },
  { id: "special", label: "One special character (! @ # $ % ^ & * ( ) , . ? \" : { } | < >)", test: (p) => /[!@#$%^&*(),.?":{}|<>]/.test(p) },
];

export function unmetPasswordRules(password: string) {
  return PASSWORD_RULES.filter((rule) => !rule.test(password));
}
