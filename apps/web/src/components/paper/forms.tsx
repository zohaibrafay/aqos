"use client";

import { useState } from "react";

import { backtestActions, paperActions } from "@/api/resources";
import type { AqosApiError } from "@/api/errors";
import { NotReadyPanel } from "@/components/backtests";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Button, Card, Field, Input, Select } from "@/components/ui";
import { ConfirmationDialog, toApiError } from "@/components/paper/actions";
import {
  SUPPORTED_STRATEGIES,
  parseNumber,
  validateDatasetName,
  validatePeriod,
} from "@/components/paper/validation";
import { SESSION_TYPES } from "@/components/paper/PaperSessionFilters";
import { getApiClient } from "@/lib/api";

/**
 * Forms that start something.
 *
 * A paper session and a historical backtest. Neither reaches a venue, and
 * neither takes a path, a URL or a module name — a dataset is a configured
 * name and a strategy is one of a fixed list.
 */

/** Session types that must name what drove the run. */
const MODEL_DRIVEN = "model_forward_test";
const STRATEGY_DRIVEN = "strategy_forward_test";

export function PaperSessionCreateForm({
  onCreated,
}: {
  readonly onCreated: (sessionId: string) => void;
}) {
  const [accountId, setAccountId] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<string>(SESSION_TYPES[0]);
  const [strategy, setStrategy] = useState("");
  const [modelId, setModelId] = useState("");
  const [modelVersion, setModelVersion] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<string | null>(null);
  const [error, setError] = useState<AqosApiError | null>(null);

  const check = (): string | null => {
    if (!accountId.trim()) {
      return "Enter the paper account this run belongs to.";
    }

    if (!name.trim()) {
      return "Give the run a name.";
    }

    // Mirrors the backend identity rule: an unattributed forward test cannot
    // be reproduced or compared later.
    if (type === MODEL_DRIVEN && !modelId.trim()) {
      return "A model forward test must name the model it tests.";
    }

    if (type === STRATEGY_DRIVEN && !strategy.trim()) {
      return "A strategy forward test must name the strategy it tests.";
    }

    return null;
  };

  const submit = async () => {
    const problem = check();

    if (problem) {
      setValidation(problem);

      return;
    }

    setValidation(null);
    setError(null);
    setBusy(true);

    try {
      // No `initial_balance`: the balance comes from the account, and stating
      // one here would let a run start from a figure it never had.
      const created = await paperActions.createSession(getApiClient(), {
        account_id: accountId.trim(),
        session_name: name.trim(),
        session_type: type,
        ...(strategy.trim() ? { strategy_name: strategy.trim() } : {}),
        ...(modelId.trim() ? { model_id: modelId.trim() } : {}),
        ...(modelVersion.trim() ? { model_version: modelVersion.trim() } : {}),
        ...(symbol.trim() ? { symbol: symbol.trim() } : {}),
        ...(timeframe.trim() ? { timeframe: timeframe.trim() } : {}),
      });

      onCreated(created.session.session_id);
    } catch (cause) {
      setError(toApiError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Start a simulated run">
      <p className="mb-3 text-xs text-muted">
        A paper session groups simulated activity. It can only be opened on a
        paper account.
      </p>

      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Field label="Paper account" htmlFor="new-account">
          <Input
            id="new-account"
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
          />
        </Field>
        <Field label="Run name" htmlFor="new-name">
          <Input
            id="new-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <Field label="Type" htmlFor="new-type">
          <Select
            id="new-type"
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            {SESSION_TYPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Strategy" htmlFor="new-strategy" hint="Optional">
          <Input
            id="new-strategy"
            value={strategy}
            onChange={(event) => setStrategy(event.target.value)}
          />
        </Field>
        <Field label="Model" htmlFor="new-model" hint="Optional">
          <Input
            id="new-model"
            value={modelId}
            onChange={(event) => setModelId(event.target.value)}
          />
        </Field>
        <Field label="Model version" htmlFor="new-model-version" hint="Optional">
          <Input
            id="new-model-version"
            value={modelVersion}
            onChange={(event) => setModelVersion(event.target.value)}
          />
        </Field>
        <Field label="Symbol" htmlFor="new-symbol" hint="Optional">
          <Input
            id="new-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          />
        </Field>
        <Field label="Timeframe" htmlFor="new-timeframe" hint="Optional">
          <Input
            id="new-timeframe"
            value={timeframe}
            onChange={(event) => setTimeframe(event.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create run"}
          </Button>
        </div>
      </form>

      {validation ? (
        <p role="alert" className="mt-3 text-sm text-rose-300">
          {validation}
        </p>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ApiErrorPanel error={error} />
        </div>
      ) : null}
    </Card>
  );
}

/**
 * Start a historical backtest.
 *
 * The strategy is chosen from a fixed list and the dataset is a configured
 * name. Neither field can express a path, a URL or a module, because neither
 * accepts free text that could become one.
 */
export function BacktestRunForm({
  onStarted,
}: {
  readonly onStarted: (backtestId: string) => void;
}) {
  const [strategy, setStrategy] = useState<string>(SUPPORTED_STRATEGIES[0]);
  const [dataset, setDataset] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [balance, setBalance] = useState("10000");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState<string | null>(null);
  const [error, setError] = useState<AqosApiError | null>(null);

  const check = (): string | null => {
    const datasetProblem = validateDatasetName(dataset);

    if (datasetProblem) {
      return datasetProblem;
    }

    if (!symbol.trim()) {
      return "Enter the symbol this dataset covers.";
    }

    if (!timeframe.trim()) {
      return "Enter the timeframe this dataset covers.";
    }

    return validatePeriod(start, end);
  };

  const submit = async () => {
    const problem = check();

    if (problem) {
      setValidation(problem);
      setConfirming(false);

      return;
    }

    setValidation(null);
    setError(null);
    setBusy(true);

    try {
      const result = await backtestActions.run(getApiClient(), {
        strategy_name: strategy,
        dataset: dataset.trim(),
        symbol: symbol.trim(),
        timeframe: timeframe.trim(),
        ...(start.trim() ? { period_start: start.trim() } : {}),
        ...(end.trim() ? { period_end: end.trim() } : {}),
        ...(parseNumber(balance) === null
          ? {}
          : { initial_balance: parseNumber(balance) as number }),
      });

      setConfirming(false);
      onStarted(result.backtest.backtest_id);
    } catch (cause) {
      setError(toApiError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Run a historical backtest">
      <p className="mb-3 text-xs text-muted">
        A backtest replays stored history. It runs while you wait, so there is
        nothing to queue and no venue involved.
      </p>

      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          const problem = check();

          setValidation(problem);

          if (!problem) {
            setConfirming(true);
          }
        }}
      >
        <Field label="Strategy" htmlFor="run-strategy">
          <Select
            id="run-strategy"
            value={strategy}
            onChange={(event) => setStrategy(event.target.value)}
          >
            {SUPPORTED_STRATEGIES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Dataset"
          htmlFor="run-dataset"
          hint="The configured dataset name, not a file path"
        >
          <Input
            id="run-dataset"
            value={dataset}
            onChange={(event) => setDataset(event.target.value)}
          />
        </Field>
        <Field label="Symbol" htmlFor="run-symbol">
          <Input
            id="run-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          />
        </Field>
        <Field label="Timeframe" htmlFor="run-timeframe">
          <Input
            id="run-timeframe"
            value={timeframe}
            onChange={(event) => setTimeframe(event.target.value)}
          />
        </Field>
        <Field label="Period start" htmlFor="run-start" hint="Optional ISO timestamp">
          <Input
            id="run-start"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </Field>
        <Field label="Period end" htmlFor="run-end" hint="Optional ISO timestamp">
          <Input
            id="run-end"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </Field>
        <Field label="Initial balance" htmlFor="run-balance">
          <Input
            id="run-balance"
            value={balance}
            onChange={(event) => setBalance(event.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            Review run
          </Button>
        </div>
      </form>

      {validation ? (
        <p role="alert" className="mt-3 text-sm text-rose-300">
          {validation}
        </p>
      ) : null}

      {confirming ? (
        <ConfirmationDialog
          title="Confirm backtest run"
          busy={busy}
          confirmLabel="Run backtest"
          onConfirm={() => void submit()}
          onCancel={() => setConfirming(false)}
        >
          <p className="mt-2 text-sm text-muted">
            {strategy} over {dataset} ({symbol} {timeframe}). This replays stored
            history and takes as long as the data does.
          </p>
        </ConfirmationDialog>
      ) : null}

      {error ? (
        <div className="mt-4">
          {/* A missing dataset directory or registry is reported as not ready. */}
          <NotReadyPanel error={error} />
        </div>
      ) : null}
    </Card>
  );
}
