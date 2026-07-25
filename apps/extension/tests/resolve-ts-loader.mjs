import { access } from "node:fs/promises";

export async function resolve(specifier, context, defaultResolve) {
  try {
    return await defaultResolve(specifier, context, defaultResolve);
  } catch (error) {
    if (!shouldTryTsResolution(specifier)) {
      throw error;
    }

    const candidate = new URL(`${specifier}.ts`, context.parentURL);
    try {
      await access(candidate);
      return {
        url: candidate.href,
        shortCircuit: true
      };
    } catch {
      throw error;
    }
  }
}

function shouldTryTsResolution(specifier) {
  return (specifier.startsWith("./") || specifier.startsWith("../")) && !specifier.endsWith(".js") && !specifier.endsWith(".mjs") && !specifier.endsWith(".ts");
}
