import { CopilotClient, approveAll } from "@github/copilot-sdk";

const chunks = [];
for await (const chunk of process.stdin) {
  chunks.push(chunk);
}

const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));

function modelIds(models) {
  return [...new Set(models.map((model) => model?.id).filter(Boolean))].sort();
}

try {
  const client = new CopilotClient({
    useLoggedInUser: true,
    logLevel: "error",
  });
  await client.start();

  try {
    if (input.action === "models") {
      const auth = await client.getAuthStatus();
      if (!auth?.isAuthenticated) {
        process.stdout.write(JSON.stringify({
          authenticated: false,
          authType: auth?.authType ?? "",
          login: auth?.login ?? "",
          models: [],
        }));
      } else {
        const models = await client.listModels();
        process.stdout.write(JSON.stringify({
          authenticated: Boolean(auth?.isAuthenticated),
          authType: auth?.authType ?? "",
          login: auth?.login ?? "",
          models: modelIds(models),
        }));
      }
    } else {
      const session = await client.createSession({
        model: input.model,
        onPermissionRequest: approveAll,
      });
      try {
        const response = await session.sendAndWait({
          prompt: `${input.systemPrompt}\n\nTrascrizione:\n${input.transcript}`,
        }, input.timeoutMs ?? 300000);

        const content = response?.data?.content ?? response?.message?.content ?? response?.content ?? "";
        process.stdout.write(JSON.stringify({ content }));
      } finally {
        await session.disconnect();
      }
    }
  } finally {
    await client.stop();
  }
} catch (error) {
  process.stderr.write(error?.stack || error?.message || String(error));
  process.exit(1);
}
