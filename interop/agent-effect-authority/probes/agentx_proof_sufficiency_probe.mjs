import fs from "node:fs";
import {
  TransactionLedger,
  VerifierEngine,
} from "@studivox/agentx";

async function runCase(caseId, verifierConfig, responsePayload) {
  const ledger = new TransactionLedger(":memory:");
  const engine = new VerifierEngine(ledger);

  const tx = ledger.createTransaction({
    fingerprint: "compat-" + caseId,
    toolName: "mutating_action",
    riskLevel: "MUTATING_CRITICAL",
    rawArguments: { id: caseId },
  });

  const executor = async () => ({
    content: [
      {
        type: "text",
        text: JSON.stringify(responsePayload),
      },
    ],
  });

  const result = await engine.verifyTransaction(
    tx.id,
    verifierConfig,
    executor
  );

  return {
    case_id: caseId,
    outcome: result.outcome,
    state: result.updatedTransaction.state,
    notes: result.verification.notes,
  };
}

const rows = [];

rows.push(
  await runCase(
    "structured-response-without-postcondition-proof",
    { toolName: "readback" },
    { arbitrary: "structured-object" }
  )
);

rows.push(
  await runCase(
    "missing-field-without-completeness-guarantee",
    {
      toolName: "readback",
      matchKeyPath: "status",
      expectedValue: "CONFIRMED",
    },
    { different_field: "present" }
  )
);

if (
  rows[0].outcome !== "PROVEN_COMMITTED" ||
  rows[0].state !== "COMMITTED"
) {
  throw new Error("AgentX structured-response baseline changed");
}

if (
  rows[1].outcome !== "PROVEN_ABSENT" ||
  rows[1].state !== "FAILED"
) {
  throw new Error("AgentX missing-field baseline changed");
}

const report = {
  implementation: "studivox/agentx",
  version: "0.1.1",
  probe: "proof-sufficiency-v0.1",
  audit_kind: "executed",
  rows,
  interpretation: [
    "The first case demonstrates the published verifier's current behavior when structured JSON is returned without matchKeyPath.",
    "The second case demonstrates the current behavior when matchKeyPath is absent from the verifier response.",
    "These are compatibility observations relative to SpatialRuntime hostile vectors, not claims that AgentX violates its own contract.",
  ],
};

process.stdout.write(JSON.stringify(report, null, 2));
