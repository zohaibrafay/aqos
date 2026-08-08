"use client";

import { useState } from "react";

import { ErrorMessage } from "@/components/states";
import { Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { useLogin } from "@/hooks/useLogin";

/**
 * Sign in.
 *
 * The only form in Sprint 063 that sends anything, and it sends credentials to
 * the AQOS login endpoint and nothing else. There is no sign-up link and no
 * password-reset link, because neither endpoint exists.
 */
export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { pending, error, user, submit } = useLogin();

  return (
    <>
      <PageHeader title="Sign in" description="Use your AQOS account." />
      <div className="max-w-sm">
        <Card>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void submit(email, password);
            }}
          >
            <Field label="Email" htmlFor="email">
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>
            <Button type="submit" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          {error ? (
            <div className="mt-4">
              <ErrorMessage error={error} />
            </div>
          ) : null}
          {user ? (
            <p className="mt-4 text-sm text-emerald-300">
              Signed in as {user.display_name}.
            </p>
          ) : null}
        </Card>
      </div>
    </>
  );
}
